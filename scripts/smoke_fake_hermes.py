#!/usr/bin/env python3
"""Offline smoke workflow for the Hermes memory wiki plugin.

This script registers the plugin against a small fake Hermes context and drives the
basic wiki tool workflow in a temporary vault. It is intentionally deterministic and
never calls a live embedding/network provider.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterator, Mapping, Sequence

from hermes_memory_wiki import plugin, tools


class FakeContext:
    """Minimal Hermes-like registration context for local smoke tests."""

    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}
        self.skills: dict[str, dict[str, Any]] = {}

    def register_tool(self, name: str, toolset: str, schema: Mapping[str, Any], handler: Any, **kwargs: Any) -> None:
        self.tools[name] = {"toolset": toolset, "schema": dict(schema), "handler": handler, **kwargs}

    def register_skill(self, name: str, path: str | Path, **kwargs: Any) -> None:
        self.skills[name] = {"path": str(path), **kwargs}


class _OfflineSmokeEmbeddingProvider:
    """Deterministic no-network embedding provider for smoke workflow search."""

    provider = "fake"
    model = "offline-smoke"
    dimensions: int | None = 3

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [
                float(len(text) % 7),
                float(sum(ord(char) for char in text) % 11),
                float(text.lower().count("claim") + 1),
            ]
            for text in texts
        ]


@contextmanager
def _offline_tools() -> Iterator[None]:
    """Patch tool-level embedding paths so smoke runs without OpenAI/network."""

    original_reindex = tools.reindex_vault
    original_search_wiki = tools.search_wiki
    offline_provider = _OfflineSmokeEmbeddingProvider()

    def fake_reindex_vault(config: Any, *, force: bool = False) -> Any:
        result = original_reindex(config, offline_provider, force=force)
        result.diagnostics.append("offline smoke reindex stub used")
        result.diagnostics.append(f"force={force}")
        return result

    def offline_search_wiki(config: Any, query: str, **kwargs: Any) -> Any:
        results, diagnostics = original_search_wiki(
            config,
            query,
            **{**kwargs, "provider": offline_provider},
        )
        diagnostics.messages.append("offline smoke search provider used")
        return results, diagnostics

    tools.reindex_vault = fake_reindex_vault
    tools.search_wiki = offline_search_wiki
    try:
        yield
    finally:
        tools.reindex_vault = original_reindex
        tools.search_wiki = original_search_wiki


def _decode_tool_response(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("tool response must be a JSON object")
    if not isinstance(payload.get("text"), str):
        raise TypeError("tool response missing string text")
    if not isinstance(payload.get("details"), dict):
        raise TypeError("tool response missing object details")
    return payload


def _call_tool(
    ctx: FakeContext,
    name: str,
    args: Mapping[str, Any],
    *,
    step_name: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    handler = ctx.tools[name]["handler"]
    payload = _decode_tool_response(handler(dict(args)))
    step = {"name": step_name or name, "ok": True, "text": payload["text"], "details": payload["details"]}
    if extra:
        step.update(dict(extra))
    return step


def _write_page(vault_path: Path, relative_path: str, content: str) -> dict[str, Any]:
    path = vault_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    return {
        "ok": True,
        "text": f"Wrote {relative_path}.",
        "details": {"path": relative_path, "bytes": path.stat().st_size},
        "path": relative_path,
    }


def _assert_generated_outputs(vault_path: Path) -> dict[str, Any]:
    expected = [
        "index.md",
        "entities/index.md",
        "concepts/index.md",
        "syntheses/index.md",
        "sources/index.md",
        "reports/open-questions.md",
        "reports/contradictions.md",
        "reports/low-confidence.md",
        "reports/claim-health.md",
        ".hermes-wiki/cache/agent-digest.json",
        ".hermes-wiki/cache/claims.jsonl",
        ".hermes-wiki/cache/lint-report.json",
    ]
    files = [relative_path for relative_path in expected if (vault_path / relative_path).is_file()]
    missing = sorted(set(expected) - set(files))
    if missing:
        raise AssertionError(f"Missing generated smoke outputs: {', '.join(missing)}")
    return {
        "name": "assert_generated_outputs",
        "ok": True,
        "text": "Generated reports and digests exist.",
        "details": {"files": files},
        "files": files,
    }


def _assert_no_structural_errors(vault_path: Path) -> dict[str, Any]:
    lint_path = vault_path / ".hermes-wiki" / "cache" / "lint-report.json"
    payload = json.loads(lint_path.read_text(encoding="utf-8"))
    structural_errors = [
        issue
        for issue in payload.get("issues", [])
        if issue.get("severity") == "error" and issue.get("category") == "structure"
    ]
    if structural_errors:
        raise AssertionError(f"Structural lint errors found: {structural_errors}")
    return {
        "name": "assert_no_structural_errors",
        "ok": True,
        "text": "No structural lint errors found.",
        "details": {"structuralErrors": structural_errors},
        "structuralErrors": structural_errors,
    }


def _run(vault_path: Path) -> dict[str, Any]:
    ctx = FakeContext()
    plugin.register(ctx)

    steps: list[dict[str, Any]] = [
        {
            "name": "register",
            "ok": True,
            "toolCount": len(ctx.tools),
            "skillCount": len(ctx.skills),
        }
    ]
    base_args = {"vaultPath": str(vault_path)}

    steps.append(_call_tool(ctx, "wiki_init", base_args))
    source_id = "source.openclaw-parity-notes"
    steps.append(
        {
            "name": "write_source_page",
            **_write_page(
                vault_path,
                "sources/openclaw-parity-notes.md",
                f"""
                ---
                id: {source_id}
                title: OpenClaw Parity Notes
                pageType: source
                sourceType: hand-written-smoke
                status: active
                confidence: 1.0
                ---
                # OpenClaw Parity Notes

                These hand-written source notes stand in for deferred source ingest.
                They state that Ada Lovelace is associated with the Analytical Engine
                and that source-backed claims should preserve evidence links.
                """,
            ),
        }
    )
    steps.append(
        {
            "name": "write_entity_page",
            **_write_page(
                vault_path,
                "entities/ada-lovelace.md",
                f"""
                ---
                id: entity.ada-lovelace
                title: Ada Lovelace
                pageType: entity
                entityType: person
                aliases:
                  - Enchantress of Numbers
                  - Countess Lovelace
                sourceIds:
                  - {source_id}
                confidence: 0.95
                status: active
                claims:
                  - id: claim.ada-associated-analytical-engine
                    text: Ada Lovelace is associated with the Analytical Engine.
                    status: active
                    confidence: 0.9
                    evidence:
                      - kind: source
                        sourceId: {source_id}
                        path: sources/openclaw-parity-notes.md
                        lines: "5-7"
                        weight: 1
                        note: Hand-written smoke source page.
                ---
                # Ada Lovelace

                Ada Lovelace is represented as an OpenClaw-compatible person entity.
                """,
            ),
        }
    )
    steps.append(
        {
            "name": "write_concept_page",
            **_write_page(
                vault_path,
                "concepts/analytical-engine.md",
                f"""
                ---
                id: concept.analytical-engine
                title: Analytical Engine
                pageType: concept
                aliases:
                  - Babbage Engine
                sourceIds:
                  - {source_id}
                confidence: 0.9
                status: active
                claims:
                  - id: claim.analytical-engine-source-backed-claims
                    text: The Analytical Engine page demonstrates source-backed claim parity.
                    status: active
                    confidence: 0.86
                    evidence:
                      - kind: source
                        sourceId: {source_id}
                        path: sources/openclaw-parity-notes.md
                        lines: "6-8"
                        weight: 1
                        note: Concept claim evidence for parity smoke.
                ---
                # Analytical Engine

                A concept page used by the fake Hermes parity smoke workflow.
                """,
            ),
        }
    )
    steps.append(
        _call_tool(
            ctx,
            "wiki_apply",
            {
                **base_args,
                "op": "create_synthesis",
                "title": "OpenClaw Parity Synthesis",
                "body": "Ada Lovelace and the Analytical Engine are connected by source-backed claims.",
                "sourceIds": [source_id],
                "claims": [
                    {
                        "id": "claim.openclaw-parity-synthesis",
                        "text": "The fake Hermes smoke workflow validates OpenClaw parity end to end.",
                        "status": "active",
                        "confidence": 0.92,
                        "evidence": [
                            {
                                "kind": "source",
                                "sourceId": source_id,
                                "path": "sources/openclaw-parity-notes.md",
                                "lines": "1-8",
                                "weight": 1,
                            }
                        ],
                    }
                ],
                "status": "active",
                "confidence": 0.9,
            },
        )
    )
    steps.append(_call_tool(ctx, "wiki_compile", base_args))
    steps.append(_call_tool(ctx, "wiki_lint", base_args))
    with _offline_tools():
        steps.append(_call_tool(ctx, "wiki_reindex", {**base_args, "force": True}))
        for step_name, query in [
            ("search_entity_name", "Ada Lovelace"),
            ("search_concept_name", "Analytical Engine"),
            ("search_alias", "Enchantress of Numbers"),
            ("search_claim_text", "source-backed claim parity"),
        ]:
            steps.append(
                _call_tool(
                    ctx,
                    "wiki_search",
                    {**base_args, "query": query, "searchMode": "hybrid"},
                    step_name=step_name,
                    extra={"query": query},
                )
            )
    for step_name, lookup in [
        ("get_by_id", "entity.ada-lovelace"),
        ("get_by_path", "concepts/analytical-engine.md"),
        ("get_by_title", "OpenClaw Parity Synthesis"),
        ("get_by_alias", "Enchantress of Numbers"),
    ]:
        steps.append(
            _call_tool(
                ctx,
                "wiki_get",
                {**base_args, "lookup": lookup},
                step_name=step_name,
                extra={"lookup": lookup},
            )
        )
    steps.append(_assert_generated_outputs(vault_path))
    steps.append(_assert_no_structural_errors(vault_path))

    return {
        "ok": True,
        "vaultPath": str(vault_path),
        "registeredTools": sorted(ctx.tools),
        "registeredSkills": sorted(ctx.skills),
        "steps": steps,
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def run_smoke_workflow(vault_path: str | Path | None = None) -> dict[str, Any]:
    """Run the offline plugin registration workflow and return a JSON-ready summary."""

    if vault_path is not None:
        return _run(Path(vault_path))
    with tempfile.TemporaryDirectory(prefix="hermes-memory-wiki-smoke-") as tmpdir:
        return _run(Path(tmpdir) / "vault")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-path", type=Path, help="Vault path to use instead of a temporary directory.")
    args = parser.parse_args(argv)

    try:
        summary = run_smoke_workflow(args.vault_path)
    except Exception as exc:  # pragma: no cover - exercised by manual CLI failures
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(summary, indent=2, default=_json_ready))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
