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
from types import SimpleNamespace
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

    provider = "offline-smoke"
    model = "offline-smoke"
    dimensions: int | None = 3

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text) % 7), float(text.count(" ") + 1), 1.0] for text in texts]


@contextmanager
def _offline_tools() -> Iterator[None]:
    """Patch tool-level embedding paths so smoke runs without OpenAI/network."""

    original_reindex = tools.reindex_vault
    original_search_wiki = tools.search_wiki
    offline_provider = _OfflineSmokeEmbeddingProvider()

    def fake_reindex_vault(config: Any, *, force: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            embedded_count=0,
            skipped_count=0,
            deleted_count=0,
            provider="fake",
            model="offline-smoke",
            dimensions=3,
            diagnostics=["offline smoke reindex stub used", f"force={force}"],
        )

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


def _call_tool(ctx: FakeContext, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
    handler = ctx.tools[name]["handler"]
    payload = _decode_tool_response(handler(dict(args)))
    return {"name": name, "ok": True, "text": payload["text"], "details": payload["details"]}


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
    steps.append(
        _call_tool(
            ctx,
            "wiki_apply",
            {
                **base_args,
                "op": "create_synthesis",
                "title": "Offline Smoke Synthesis",
                "body": "This page is created by the offline fake Hermes smoke workflow.",
                "sourceIds": ["smoke.source"],
                "claims": [
                    {
                        "id": "claim.offline-smoke",
                        "text": "The offline smoke workflow created this synthesis.",
                        "confidence": 1.0,
                        "evidence": [{"sourceId": "smoke.source", "quote": "offline smoke"}],
                    }
                ],
                "status": "stable",
            },
        )
    )
    steps.append(_call_tool(ctx, "wiki_compile", base_args))
    with _offline_tools():
        steps.append(_call_tool(ctx, "wiki_reindex", {**base_args, "force": True}))
        steps.append(_call_tool(ctx, "wiki_search", {**base_args, "query": "offline smoke", "searchMode": "hybrid"}))
    steps.append(_call_tool(ctx, "wiki_get", {**base_args, "lookup": "synthesis.offline-smoke-synthesis"}))
    steps.append(_call_tool(ctx, "wiki_lint", base_args))

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
