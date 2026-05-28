#!/usr/bin/env python3
"""Live OpenAI smoke workflow for the Hermes memory wiki plugin.

This script registers the plugin against a small fake Hermes context and drives the
basic wiki tool workflow in a temporary vault. Unlike `smoke_fake_hermes.py`, this
script intentionally uses the real OpenAI embeddings provider and therefore
requires `OPENAI_API_KEY` in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


def _bootstrap_checkout_imports() -> None:
    """Allow running this script directly from a source checkout."""

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.is_dir():
        sys.path.insert(0, str(src_path))


_bootstrap_checkout_imports()

from hermes_memory_wiki import plugin


REQUIRED_STEPS = [
    "register",
    "wiki_init",
    "wiki_apply",
    "wiki_compile",
    "wiki_reindex",
    "wiki_search",
    "wiki_get",
    "wiki_lint",
]


class FakeContext:
    """Minimal Hermes-like registration context for local smoke tests."""

    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}
        self.skills: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        toolset: str,
        schema: Mapping[str, Any],
        handler: Any,
        **kwargs: Any,
    ) -> None:
        self.tools[name] = {"toolset": toolset, "schema": dict(schema), "handler": handler, **kwargs}

    def register_skill(self, name: str, path: str | Path, **kwargs: Any) -> None:
        self.skills[name] = {"path": str(path), **kwargs}


def _decode_tool_response(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("tool response must be a JSON object")
    if not isinstance(payload.get("text"), str):
        raise TypeError("tool response missing string text")
    if not isinstance(payload.get("details"), dict):
        raise TypeError("tool response missing object details")
    return payload


def _compact_details(name: str, details: dict[str, Any]) -> dict[str, Any]:
    if name == "wiki_reindex":
        return {
            key: details.get(key)
            for key in [
                "embeddedCount",
                "skippedCount",
                "deletedCount",
                "provider",
                "model",
                "dimensions",
                "diagnostics",
            ]
        }
    if name == "wiki_search":
        results = details.get("results", [])
        return {
            "resultCount": len(results),
            "top": results[0] if results else None,
            "diagnostics": details.get("diagnostics"),
        }
    if name == "wiki_get":
        return {
            key: details.get(key)
            for key in ["found", "path", "id", "title", "totalLines", "truncated"]
        }
    if name == "wiki_lint":
        return {
            key: details.get(key)
            for key in ["issueCount", "errorCount", "warningCount", "updatedFileCount"]
        }
    if name == "wiki_compile":
        return {
            key: details.get(key)
            for key in ["pageCounts", "claimCount", "updatedFileCount"]
        }
    return {
        key: details.get(key)
        for key in ["vaultPath", "created", "path", "id", "updatedFileCount"]
        if key in details
    }


def _call_tool(ctx: FakeContext, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
    handler = ctx.tools[name]["handler"]
    payload = _decode_tool_response(handler(dict(args)))
    return {
        "name": name,
        "ok": True,
        "text": payload["text"],
        "details": _compact_details(name, payload["details"]),
    }


def _run(vault_path: Path) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for live OpenAI smoke workflow")

    ctx = FakeContext()
    plugin.register(ctx)
    base_args = {"vaultPath": str(vault_path)}
    steps: list[dict[str, Any]] = [
        {
            "name": "register",
            "ok": True,
            "toolCount": len(ctx.tools),
            "skillCount": len(ctx.skills),
        }
    ]

    steps.append(_call_tool(ctx, "wiki_init", base_args))
    steps.append(
        _call_tool(
            ctx,
            "wiki_apply",
            {
                **base_args,
                "op": "create_synthesis",
                "title": "Live OpenAI Smoke Synthesis",
                "body": (
                    "This synthetic page validates live OpenAI embedding integration "
                    "for hermes-memory-wiki before installation as a real Hermes plugin."
                ),
                "sourceIds": ["live-openai-smoke"],
                "claims": [
                    {
                        "id": "claim.live-openai-smoke",
                        "text": "Live OpenAI smoke testing can embed and retrieve synthetic wiki content.",
                        "confidence": 0.99,
                        "evidence": [
                            {
                                "sourceId": "live-openai-smoke",
                                "quote": "embed and retrieve synthetic wiki content",
                            }
                        ],
                    }
                ],
                "status": "stable",
            },
        )
    )
    steps.append(_call_tool(ctx, "wiki_compile", base_args))
    steps.append(_call_tool(ctx, "wiki_reindex", {**base_args, "force": True}))
    steps.append(
        _call_tool(
            ctx,
            "wiki_search",
            {
                **base_args,
                "query": "Can live OpenAI embeddings retrieve synthetic wiki content?",
                "searchMode": "hybrid",
                "maxResults": 3,
            },
        )
    )
    steps.append(_call_tool(ctx, "wiki_get", {**base_args, "lookup": "claim.live-openai-smoke"}))
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


def run_live_openai_smoke_workflow(vault_path: str | Path | None = None) -> dict[str, Any]:
    """Run the live plugin registration workflow and return a JSON-ready summary."""

    if vault_path is not None:
        return _run(Path(vault_path))
    with tempfile.TemporaryDirectory(prefix="hermes-memory-wiki-live-openai-") as tmpdir:
        return _run(Path(tmpdir) / "vault")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-path", type=Path, help="Vault path to use instead of a temporary directory.")
    args = parser.parse_args(argv)

    try:
        summary = run_live_openai_smoke_workflow(args.vault_path)
    except Exception as exc:  # pragma: no cover - exercised by manual CLI failures
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(summary, indent=2, default=_json_ready))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
