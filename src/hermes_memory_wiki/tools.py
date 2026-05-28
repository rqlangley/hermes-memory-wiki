"""Hermes tool registration for the memory wiki plugin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from hermes_memory_wiki.apply import apply_mutation, normalize_mutation
from hermes_memory_wiki.compile import compile_vault
from hermes_memory_wiki.config import MemoryWikiConfig, load_config
from hermes_memory_wiki.hybrid_search import search_wiki
from hermes_memory_wiki.lint import lint_vault
from hermes_memory_wiki.vault import METADATA_DIRECTORY, get_page, initialize_vault, read_queryable_pages
from hermes_memory_wiki.vector_index import reindex_vault

TOOLSET = "memory_wiki"
STATUS_DIRECTORIES = [
    "entities",
    "concepts",
    "syntheses",
    "sources",
    "reports",
    "_attachments",
    "_views",
    METADATA_DIRECTORY,
    f"{METADATA_DIRECTORY}/locks",
    f"{METADATA_DIRECTORY}/cache",
    f"{METADATA_DIRECTORY}/vector",
]

JsonDict = dict[str, Any]
Handler = Callable[[Mapping[str, Any] | None], str]
HermesHandler = Callable[..., str]


def register(ctx: Any) -> None:
    """Register all memory wiki tools with a Hermes plugin context."""
    for spec in _tool_specs():
        ctx.register_tool(**spec)


def _tool_specs() -> list[JsonDict]:
    return [
        _spec("wiki_init", "Initialize the configured memory wiki vault.", _schema(_vault_path_property()), wiki_init),
        _spec("wiki_status", "Report basic memory wiki vault status.", _schema(_vault_path_property()), wiki_status),
        _spec(
            "wiki_search",
            "Search memory wiki pages and claims.",
            _schema(
                {
                    **_vault_path_property(),
                    "query": {"type": "string", "minLength": 1},
                    "maxResults": {"type": "integer", "minimum": 1, "default": 10},
                    "mode": {"type": "string", "enum": ["auto", "find-person", "route-question", "source-evidence", "raw-claim"], "default": "auto"},
                    "searchMode": {"type": "string", "enum": ["keyword", "vector", "hybrid"]},
                },
                required=["query"],
            ),
            wiki_search,
        ),
        _spec(
            "wiki_get",
            "Read a memory wiki page by path, id, title, or claim id.",
            _schema(
                {
                    **_vault_path_property(),
                    "lookup": {"type": "string", "minLength": 1},
                    "fromLine": {"type": "integer", "minimum": 1, "default": 1},
                    "lineCount": {"type": "integer", "minimum": 1, "default": 200},
                },
                required=["lookup"],
            ),
            wiki_get,
        ),
        _spec(
            "wiki_apply",
            "Apply a structured memory wiki mutation.",
            _schema(
                {
                    **_vault_path_property(),
                    "op": {"type": "string", "enum": ["create_synthesis", "update_metadata"]},
                    "lookup": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "sourceIds": {"type": "array", "items": {"type": "string"}},
                    "claims": {"type": "array", "items": _claim_schema()},
                    "questions": {"type": "array", "items": {"type": "string"}},
                    "contradictions": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "status": {"type": "string"},
                },
                required=["op"],
            ),
            wiki_apply,
        ),
        _spec("wiki_compile", "Compile deterministic wiki indexes and caches.", _schema(_vault_path_property()), wiki_compile),
        _spec(
            "wiki_reindex",
            "Rebuild or update the memory wiki vector index.",
            _schema({**_vault_path_property(), "force": {"type": "boolean", "default": False}}),
            wiki_reindex,
        ),
        _spec("wiki_lint", "Lint memory wiki structural health.", _schema(_vault_path_property()), wiki_lint),
    ]


def _spec(name: str, description: str, schema: JsonDict, handler: Handler) -> JsonDict:
    return {
        "name": name,
        "toolset": TOOLSET,
        "description": description,
        "schema": schema,
        "handler": _accept_runtime_kwargs(handler),
    }


def _accept_runtime_kwargs(handler: Handler) -> HermesHandler:
    def wrapped(args: Mapping[str, Any] | None = None, **_kwargs: Any) -> str:
        return handler(args)

    return wrapped


def _schema(properties: JsonDict, *, required: list[str] | None = None) -> JsonDict:
    schema: JsonDict = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


def _claim_schema() -> JsonDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["text"],
        "properties": {
            "id": {"type": "string"},
            "text": {"type": "string", "minLength": 1},
            "status": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "updatedAt": {"type": "string"},
            "evidence": {"type": "array", "items": _evidence_schema()},
        },
    }


def _evidence_schema() -> JsonDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {"type": "string"},
            "sourceId": {"type": "string"},
            "path": {"type": "string"},
            "lines": {"type": "string"},
            "confidence": {"type": "number"},
            "weight": {"type": "number"},
            "privacyTier": {"type": "string"},
            "updatedAt": {"type": "string"},
            "note": {"type": "string"},
            "text": {"type": "string"},
        },
    }


def _vault_path_property() -> JsonDict:
    return {"vaultPath": {"type": "string", "description": "Override memory wiki vault path."}}


def wiki_init(args: Mapping[str, Any] | None = None) -> str:
    config = _config(args)
    result = initialize_vault(config)
    details = {
        "vaultPath": str(result.root),
        "created": result.created,
        "createdDirectories": _paths(result.created_directories),
        "createdFiles": _paths(result.created_files),
    }
    return _response(
        f"Initialized memory wiki vault at {result.root} ({'created' if result.created else 'already up to date'}).",
        details,
    )


def wiki_status(args: Mapping[str, Any] | None = None) -> str:
    config = _config(args)
    root = config.vault_path
    metadata_dir = root / METADATA_DIRECTORY
    cache_dir = metadata_dir / "cache"
    vector_dir = metadata_dir / "vector"
    pages = read_queryable_pages(root) if root.is_dir() else []
    details = {
        "vaultPath": str(root),
        "exists": root.exists(),
        "initialized": metadata_dir.is_dir(),
        "pageCount": len(pages),
        "directories": {relative: (root / relative).is_dir() for relative in STATUS_DIRECTORIES},
        "cache": {"exists": cache_dir.is_dir(), "path": str(cache_dir)},
        "vector": {"exists": vector_dir.is_dir(), "path": str(vector_dir)},
        "cacheExists": cache_dir.is_dir(),
        "vectorExists": vector_dir.is_dir(),
    }
    return _response(f"Memory wiki status for {root}: {len(pages)} queryable pages.", details)


def wiki_search(args: Mapping[str, Any] | None = None) -> str:
    raw = _args(args)
    query = str(raw["query"])
    results, diagnostics = search_wiki(
        _config(raw),
        query,
        max_results=int(raw.get("maxResults", 10)),
        mode=str(raw.get("mode", "auto")),
        search_mode=raw.get("searchMode"),
        provider=None,
    )
    result_details = [_search_result(result) for result in results]
    details = {
        "query": query,
        "results": result_details,
        "diagnostics": {
            "requestedMode": diagnostics.requested_mode,
            "effectiveMode": diagnostics.effective_mode,
            "vectorAvailable": diagnostics.vector_available,
            "messages": list(diagnostics.messages),
        },
    }
    noun = "result" if len(result_details) == 1 else "results"
    return _response(f"Found {len(result_details)} {noun} for {query!r}.", details)


def wiki_get(args: Mapping[str, Any] | None = None) -> str:
    raw = _args(args)
    lookup = str(raw["lookup"])
    result = get_page(
        _config(raw),
        lookup,
        from_line=int(raw.get("fromLine", 1)),
        line_count=int(raw.get("lineCount", 200)),
    )
    if result is None:
        return _response(f"No memory wiki page found for {lookup!r}.", {"lookup": lookup, "found": False})
    page = getattr(result, "page", None)
    details = {
        "found": True,
        "path": result.path,
        "id": result.id,
        "title": result.title,
        "kind": result.kind,
        "pageType": getattr(page, "page_type", None),
        "entityType": getattr(page, "entity_type", None),
        "aliases": list(getattr(page, "aliases", [])),
        "sourceIds": list(getattr(page, "source_ids", [])),
        "claimCount": len(getattr(page, "claims", [])),
        "questions": list(getattr(page, "questions", [])),
        "contradictions": list(getattr(page, "contradictions", [])),
        "confidence": getattr(page, "confidence", None),
        "status": getattr(page, "status", None),
        "updatedAt": getattr(page, "updated_at", None),
        "content": result.content,
        "fromLine": result.from_line,
        "lineCount": result.line_count,
        "totalLines": result.total_lines,
        "truncated": result.truncated,
    }
    return _response(f"Read memory wiki page {result.title} ({result.path}).", details)


def wiki_apply(args: Mapping[str, Any] | None = None) -> str:
    raw = _args(args)
    config = _config(raw)
    initialize_vault(config)
    mutation = normalize_mutation(raw)
    result = apply_mutation(config, mutation)
    compile_result = compile_vault(config)
    details = {
        "path": result.path,
        "id": result.id,
        "created": result.created,
        "op": getattr(mutation, "type", raw.get("op")),
        "compile": {
            "pageCounts": dict(compile_result.page_counts),
            "claimCount": compile_result.claim_count,
            "updatedFiles": _paths(compile_result.updated_files),
            "updatedFileCount": len(compile_result.updated_files),
        },
    }
    return _response(f"Applied memory wiki mutation to {result.path}.", details)


def wiki_compile(args: Mapping[str, Any] | None = None) -> str:
    result = compile_vault(_config(args))
    details = {
        "vaultPath": str(result.vault_root),
        "pageCounts": dict(result.page_counts),
        "claimCount": result.claim_count,
        "updatedFiles": _paths(result.updated_files),
        "updatedFileCount": len(result.updated_files),
    }
    return _response(f"Compiled memory wiki at {result.vault_root}.", details)


def wiki_reindex(args: Mapping[str, Any] | None = None) -> str:
    raw = _args(args)
    result = reindex_vault(_config(raw), force=bool(raw.get("force", False)))
    details = {
        "embeddedCount": result.embedded_count,
        "skippedCount": result.skipped_count,
        "deletedCount": result.deleted_count,
        "documentCount": getattr(result, "document_count", result.embedded_count + result.skipped_count),
        "provider": result.provider,
        "model": result.model,
        "dimensions": result.dimensions,
        "diagnostics": list(result.diagnostics),
    }
    return _response(f"Reindexed memory wiki embeddings: {result.embedded_count} embedded, {result.skipped_count} skipped.", details)


def wiki_lint(args: Mapping[str, Any] | None = None) -> str:
    result = lint_vault(_config(args))
    details = {
        "vaultPath": str(result.vault_root),
        "issueCount": result.issue_count,
        "errorCount": result.error_count,
        "warningCount": result.warning_count,
        "categoryCounts": _issue_counts(result.issues, "category"),
        "severityCounts": _issue_counts(result.issues, "severity"),
        "markdownPath": str(result.markdown_path),
        "jsonPath": str(result.json_path),
        "updatedFiles": _paths(result.updated_files),
        "updatedFileCount": len(result.updated_files),
    }
    return _response(f"Linted memory wiki: {result.issue_count} issues ({result.error_count} errors).", details)


def _config(args: Mapping[str, Any] | None) -> MemoryWikiConfig:
    raw = _args(args)
    vault_path = raw.get("vaultPath")
    if vault_path is not None:
        return MemoryWikiConfig(vault_path=Path(str(vault_path)).expanduser())
    return load_config()


def _args(args: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return args or {}


def _response(text: str, details: JsonDict) -> str:
    return json.dumps({"text": text, "details": details}, default=str)


def _paths(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths]


def _search_result(result: Any) -> JsonDict:
    metadata = dict(result.metadata)
    return {
        "corpus": result.corpus,
        "path": result.path,
        "title": result.title,
        "kind": result.kind,
        "id": _metadata_value(metadata, "id", "page_id"),
        "pageType": _metadata_value(metadata, "pageType", "page_type"),
        "entityType": _metadata_value(metadata, "entityType", "entity_type"),
        "sourceIds": _metadata_list(metadata, "sourceIds", "source_ids", "page_source_ids"),
        "claimCount": _metadata_value(metadata, "claimCount", "claim_count"),
        "confidence": _metadata_value(metadata, "confidence"),
        "status": _metadata_value(metadata, "status"),
        "updatedAt": _metadata_value(metadata, "updatedAt", "updated_at"),
        "score": result.score,
        "snippet": result.snippet,
        "searchMode": result.search_mode,
        "matchedClaimId": result.matched_claim_id,
        "metadata": metadata,
    }


def _metadata_value(metadata: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _metadata_list(metadata: Mapping[str, Any], *keys: str) -> list[Any]:
    value = _metadata_value(metadata, *keys)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _issue_counts(issues: list[Any], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        value = getattr(issue, field_name, None)
        if value is None and isinstance(issue, Mapping):
            value = issue.get(field_name)
        if value:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
    return counts
