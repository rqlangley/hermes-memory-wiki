"""Compile deterministic wiki indexes and cache files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.schema import WikiClaim, WikiPageSummary
from hermes_memory_wiki.vault import METADATA_DIRECTORY, QUERY_DIRS, read_queryable_pages
from hermes_memory_wiki.vector_index import SearchDocument, build_search_documents


@dataclass
class CompileResult:
    vault_root: Path
    page_counts: dict[str, int]
    claim_count: int
    updated_files: list[Path]


def compile_vault(config: MemoryWikiConfig) -> CompileResult:
    """Generate deterministic Markdown indexes and JSON/JSONL cache files."""
    root = config.vault_path
    pages = sorted(read_queryable_pages(root), key=lambda page: page.path)
    page_counts = _page_counts(pages)
    claim_count = sum(len(page.claims) for page in pages)
    cache_dir = root / METADATA_DIRECTORY / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[Path, str] = {}
    outputs[root / "index.md"] = _render_root_index(page_counts, claim_count)
    for query_dir in QUERY_DIRS:
        directory = root / query_dir
        if directory.is_symlink():
            continue
        directory.mkdir(parents=True, exist_ok=True)
        directory_pages = [page for page in pages if _first_path_part(page.path) == query_dir]
        outputs[directory / "index.md"] = _render_directory_index(query_dir, directory_pages)

    outputs[cache_dir / "agent-digest.json"] = _json_text(_agent_digest(pages, page_counts, claim_count))
    outputs[cache_dir / "claims.jsonl"] = _jsonl_text(_claim_records(pages))
    outputs[cache_dir / "search-docs.jsonl"] = _jsonl_text(_search_document_records(build_search_documents(pages)))

    updated_files = _write_changed(outputs)
    if updated_files:
        _append_compile_log(root, updated_files)

    return CompileResult(
        vault_root=root,
        page_counts=page_counts,
        claim_count=claim_count,
        updated_files=updated_files,
    )


def _page_counts(pages: Sequence[WikiPageSummary]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in pages:
        counts[page.kind] = counts.get(page.kind, 0) + 1
    return dict(sorted(counts.items()))


def _render_root_index(page_counts: dict[str, int], claim_count: int) -> str:
    lines = [
        "# Memory Wiki Index",
        "",
        "## Counts",
        "",
        f"- Total pages: {sum(page_counts.values())}",
        f"- Total claims: {claim_count}",
    ]
    lines.extend(f"- {kind}: {count}" for kind, count in page_counts.items())
    lines.extend(
        [
            "",
            "## Directories",
            "",
            "- [Sources](sources/)",
            "- [Entities](entities/)",
            "- [Concepts](concepts/)",
            "- [Syntheses](syntheses/)",
            "- [Reports](reports/)",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_directory_index(query_dir: str, pages: Sequence[WikiPageSummary]) -> str:
    title = query_dir.replace("-", " ").title()
    lines = [f"# {title} Index", ""]
    if not pages:
        lines.append("No pages yet.")
        return "\n".join(lines) + "\n"

    by_kind: dict[str, list[WikiPageSummary]] = {}
    for page in pages:
        by_kind.setdefault(page.kind, []).append(page)

    for kind in sorted(by_kind):
        lines.extend([f"## {kind}", ""])
        for page in sorted(by_kind[kind], key=lambda item: (item.title.casefold(), item.path)):
            lines.append(f"- [{page.title}]({_basename(page.path)}) — {page.id}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _agent_digest(
    pages: Sequence[WikiPageSummary], page_counts: dict[str, int], claim_count: int
) -> dict[str, Any]:
    return {
        "version": 1,
        "pageCounts": page_counts,
        "claimCount": claim_count,
        "pages": [
            {
                "path": page.path,
                "id": page.id,
                "title": page.title,
                "kind": page.kind,
                "claimCount": len(page.claims),
            }
            for page in pages
        ],
    }


def _claim_records(pages: Sequence[WikiPageSummary]) -> Iterable[dict[str, Any]]:
    for page in pages:
        for ordinal, claim in enumerate(page.claims):
            yield {
                "pagePath": page.path,
                "pageId": page.id,
                "pageTitle": page.title,
                "claimId": claim.id or _fallback_claim_id(ordinal),
                "text": claim.text,
                "status": claim.status,
                "confidence": claim.confidence,
            }


def _search_document_records(docs: Sequence[SearchDocument]) -> Iterable[dict[str, Any]]:
    for doc in docs:
        yield {
            "id": doc.id,
            "pagePath": doc.page_path,
            "kind": doc.kind,
            "title": doc.title,
            "docType": doc.doc_type,
            "text": doc.text,
            "textHash": doc.text_hash,
            "metadata": doc.metadata,
        }


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _jsonl_text(records: Iterable[dict[str, Any]]) -> str:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    return "\n".join(lines) + ("\n" if lines else "")


def _write_changed(outputs: dict[Path, str]) -> list[Path]:
    updated: list[Path] = []
    for path in sorted(outputs):
        content = outputs[path]
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        updated.append(path)
    return updated


def _append_compile_log(root: Path, updated_files: Sequence[Path]) -> None:
    log_path = root / METADATA_DIRECTORY / "log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": "compile",
        "createdAt": datetime.now(UTC).isoformat(),
        "updatedFiles": [_display_path(root, path) for path in updated_files],
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _first_path_part(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if parts else ""


def _basename(path: str) -> str:
    return PurePosixPath(path).name


def _display_path(root: Path, path: Path) -> str:
    return "." if path == root else path.relative_to(root).as_posix()


def _fallback_claim_id(ordinal: int) -> str:
    return f"claim-{ordinal}"
