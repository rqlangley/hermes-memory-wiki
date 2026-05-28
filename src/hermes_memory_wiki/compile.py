"""Compile deterministic wiki indexes and cache files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.markdown import WikiMarkdown, parse_wiki_markdown, render_wiki_markdown
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary
from hermes_memory_wiki.vault import METADATA_DIRECTORY, QUERY_DIRS, read_queryable_pages
from hermes_memory_wiki.vector_index import SearchDocument, build_search_documents


COMPILE_PAGE_GROUPS = [
    {"kind": "source", "dir": "sources", "heading": "Sources"},
    {"kind": "entity", "dir": "entities", "heading": "Entities"},
    {"kind": "concept", "dir": "concepts", "heading": "Concepts"},
    {"kind": "synthesis", "dir": "syntheses", "heading": "Syntheses"},
    {"kind": "report", "dir": "reports", "heading": "Reports"},
]

REPORT_DEFINITIONS = [
    {"id": "report.open-questions", "title": "Open Questions", "path": "reports/open-questions.md", "slug": "open-questions"},
    {"id": "report.contradictions", "title": "Contradictions", "path": "reports/contradictions.md", "slug": "contradictions"},
    {"id": "report.low-confidence", "title": "Low Confidence", "path": "reports/low-confidence.md", "slug": "low-confidence"},
    {"id": "report.claim-health", "title": "Claim Health", "path": "reports/claim-health.md", "slug": "claim-health"},
]


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
    cache_dir = root / METADATA_DIRECTORY / "cache"
    _reject_symlink(root / METADATA_DIRECTORY, "Generated metadata directory")
    _reject_symlink(cache_dir, "Generated cache directory")
    cache_dir.mkdir(parents=True, exist_ok=True)

    updated_files: list[Path] = []
    report_outputs = _dashboard_outputs(root, pages)
    report_updated_files = _write_changed(report_outputs)
    updated_files.extend(report_updated_files)
    if report_updated_files:
        pages = sorted(read_queryable_pages(root), key=lambda page: page.path)

    page_counts = _page_counts(pages)
    claim_count = sum(len(page.claims) for page in pages)
    search_documents = build_search_documents(pages)

    outputs: dict[Path, str] = {}
    outputs[root / "index.md"] = _render_root_index(root / "index.md", page_counts, claim_count)
    for group in COMPILE_PAGE_GROUPS:
        query_dir = str(group["dir"])
        directory = root / query_dir
        if directory.is_symlink():
            continue
        directory.mkdir(parents=True, exist_ok=True)
        directory_pages = [page for page in pages if page.kind == group["kind"]]
        outputs[directory / "index.md"] = _render_directory_index(
            directory / "index.md", str(group["heading"]), str(group["dir"]), directory_pages
        )

    outputs[cache_dir / "agent-digest.json"] = _json_text(_agent_digest(pages, page_counts, claim_count))
    outputs[cache_dir / "claims.jsonl"] = _jsonl_text(_claim_records(pages, search_documents))
    outputs[cache_dir / "search-docs.jsonl"] = _jsonl_text(_search_document_records(search_documents))

    updated_files.extend(_write_changed(outputs))
    if updated_files:
        _append_compile_log(root, updated_files)

    return CompileResult(
        vault_root=root,
        page_counts=page_counts,
        claim_count=claim_count,
        updated_files=updated_files,
    )


def _page_counts(pages: Sequence[WikiPageSummary]) -> dict[str, int]:
    counts: dict[str, int] = {str(group["kind"]): 0 for group in COMPILE_PAGE_GROUPS}
    for page in pages:
        counts[page.kind] = counts.get(page.kind, 0) + 1
    return {str(group["kind"]): counts.get(str(group["kind"]), 0) for group in COMPILE_PAGE_GROUPS}


def _render_root_index(path: Path, page_counts: dict[str, int], claim_count: int) -> str:
    body_lines = [
        f"- Total pages: {sum(page_counts.values())}",
        f"- Total claims: {claim_count}",
    ]
    for group in COMPILE_PAGE_GROUPS:
        body_lines.append(f"- {group['heading']}: {page_counts[str(group['kind'])]}")
    body_lines.append("")
    body_lines.append("## Directories")
    body_lines.append("")
    body_lines.extend(f"- [{group['heading']}]({group['dir']}/)" for group in COMPILE_PAGE_GROUPS)
    original = _read_existing_or_default(path, "# Wiki Index\n")
    return _replace_managed_markdown(original, "index", "## Generated", "\n".join(body_lines))


def _render_directory_index(path: Path, title: str, marker_slug: str, pages: Sequence[WikiPageSummary]) -> str:
    heading = f"# {title} Index"
    if not pages:
        body = f"- No {title.lower()} yet."
    else:
        body = "\n".join(
            f"- [{page.title}]({_basename(page.path)})" for page in sorted(pages, key=lambda item: (item.title.casefold(), item.path))
        )
    original = _read_existing_or_default(path, f"{heading}\n")
    return _replace_managed_markdown(original, f"{marker_slug}:index", "## Generated", body)


def _agent_digest(
    pages: Sequence[WikiPageSummary], page_counts: dict[str, int], claim_count: int
) -> dict[str, Any]:
    return {
        "pageCounts": page_counts,
        "claimCount": claim_count,
        "claimHealth": _claim_health_summary(pages),
        "pages": [_digest_page(page) for page in pages],
    }


def _dashboard_outputs(root: Path, pages: Sequence[WikiPageSummary]) -> dict[Path, str]:
    source_pages = [page for page in pages if page.kind != "report"]
    outputs: dict[Path, str] = {}
    for definition in REPORT_DEFINITIONS:
        relative_path = str(definition["path"])
        slug = str(definition["slug"])
        title = str(definition["title"])
        page_id = str(definition["id"])
        body = _dashboard_body(slug, source_pages)
        outputs[root / relative_path] = _render_report_page(root / relative_path, page_id, title, slug, body)
    return outputs


def _render_report_page(path: Path, page_id: str, title: str, slug: str, generated_body: str) -> str:
    original = _read_existing_or_default(path, f"# {title}\n")
    parsed = parse_wiki_markdown(original)
    frontmatter = dict(parsed.frontmatter)
    frontmatter.update(
        {
            "id": page_id,
            "title": title,
            "pageType": "report",
            "status": _nonempty_string(frontmatter.get("status")) or "active",
            "updatedAt": _nonempty_string(frontmatter.get("updatedAt")) or datetime.now(UTC).isoformat(),
        }
    )
    body = parsed.body if parsed.body.strip() else f"# {title}\n"
    body = _replace_managed_markdown(body, slug, "## Generated", generated_body)
    return render_wiki_markdown(WikiMarkdown(frontmatter=frontmatter, body=body))


def _dashboard_body(slug: str, pages: Sequence[WikiPageSummary]) -> str:
    if slug == "open-questions":
        matches = [page for page in pages if page.questions]
        if not matches:
            return "- No open questions right now."
        lines = [f"- Pages with open questions: {len(matches)}", ""]
        for page in sorted(matches, key=lambda item: (item.title.casefold(), item.path)):
            lines.append(f"- {_page_link(page)}: {' | '.join(page.questions)}")
        return "\n".join(lines)

    if slug == "contradictions":
        matches = [page for page in pages if page.contradictions]
        contested_claims = [record for record in _claim_health_records(pages) if _is_contested_status(record["status"])]
        if not matches and not contested_claims:
            return "- No contradictions flagged right now."
        lines = [f"- Contradiction note clusters: {len(matches)}", f"- Competing claim clusters: {len(contested_claims)}"]
        if matches:
            lines.extend(["", "### Page Notes"])
            for page in sorted(matches, key=lambda item: (item.title.casefold(), item.path)):
                lines.append(f"- {_page_link(page)}: {' | '.join(page.contradictions)}")
        if contested_claims:
            lines.extend(["", "### Claim Clusters"])
            for claim in contested_claims:
                lines.append(f"- {_format_claim_health_line(claim)}")
        return "\n".join(lines)

    if slug == "low-confidence":
        page_matches = [page for page in pages if isinstance(page.confidence, (int, float)) and page.confidence < 0.5]
        claim_matches = [
            record
            for record in _claim_health_records(pages)
            if isinstance(record["confidence"], (int, float)) and record["confidence"] < 0.5
        ]
        if not page_matches and not claim_matches:
            return "- No low-confidence pages or claims right now."
        lines = [f"- Low-confidence pages: {len(page_matches)}", f"- Low-confidence claims: {len(claim_matches)}"]
        if page_matches:
            lines.extend(["", "### Pages"])
            for page in sorted(page_matches, key=lambda item: (float(item.confidence), item.title.casefold(), item.path)):
                lines.append(f"- {_page_link(page)}: confidence {float(page.confidence):.2f}")
        if claim_matches:
            lines.extend(["", "### Claims"])
            for claim in claim_matches:
                lines.append(f"- {_format_claim_health_line(claim)}")
        return "\n".join(lines)

    if slug == "claim-health":
        records = _claim_health_records(pages)
        missing_evidence = [record for record in records if record["missingEvidence"]]
        contested = [record for record in records if _is_contested_status(record["status"])]
        unknown = [record for record in records if record["freshnessLevel"] == "unknown"]
        if not missing_evidence and not contested and not unknown:
            return "- No claim health issues right now."
        lines = [
            f"- Claims missing evidence: {len(missing_evidence)}",
            f"- Contested claims: {len(contested)}",
            f"- Stale or unknown claims: {len(unknown)}",
        ]
        if missing_evidence:
            lines.extend(["", "### Missing Evidence"])
            lines.extend(f"- {_format_claim_health_line(record)}" for record in missing_evidence)
        if contested:
            lines.extend(["", "### Contested Claims"])
            lines.extend(f"- {_format_claim_health_line(record)}" for record in contested)
        if unknown:
            lines.extend(["", "### Stale Claims"])
            lines.extend(f"- {_format_claim_health_line(record)}" for record in unknown)
        return "\n".join(lines)

    raise ValueError(f"Unsupported dashboard slug: {slug}")


def _digest_page(page: WikiPageSummary) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": page.path,
        "id": page.id,
        "title": page.title,
        "kind": page.kind,
        "claimCount": len(page.claims),
        "aliases": page.aliases,
        "sourceIds": page.source_ids,
        "questions": page.questions,
        "contradictions": page.contradictions,
    }
    optional_fields = {
        "pageType": page.page_type,
        "entityType": page.entity_type,
        "canonicalId": page.canonical_id,
        "status": page.status,
        "confidence": page.confidence if isinstance(page.confidence, (int, float)) else None,
        "privacyTier": page.privacy_tier,
        "updatedAt": page.updated_at,
        "sourceType": page.source_type,
        "provenanceMode": page.provenance_mode,
        "sourcePath": page.source_path,
        "lastRefreshedAt": page.last_refreshed_at,
    }
    for key, value in optional_fields.items():
        if value is not None:
            record[key] = value
    if page.person_card is not None:
        record["personCard"] = {
            "name": page.person_card.name,
            "role": page.person_card.role,
            "bestUsedFor": list(page.person_card.best_used_for),
            "topics": list(page.person_card.topics),
            "routing": dict(page.person_card.routing),
            "routes": list(page.person_card.routes),
        }
    if page.claims:
        record["topClaims"] = [_claim_digest_record(claim) for claim in page.claims[:5]]
    return record


def _claim_digest_record(claim: WikiClaim) -> dict[str, Any]:
    record: dict[str, Any] = {
        "text": claim.text,
        "status": claim.status,
        "confidence": claim.confidence,
        "evidenceCount": len(claim.evidence),
        "missingEvidence": len(claim.evidence) == 0,
        "evidence": [_evidence_record(evidence) for evidence in claim.evidence],
        "freshnessLevel": _claim_freshness_level(claim),
    }
    if claim.id:
        record["id"] = claim.id
    return record


def _claim_health_summary(pages: Sequence[WikiPageSummary]) -> dict[str, Any]:
    records = _claim_health_records(pages)
    freshness = {"fresh": 0, "aging": 0, "stale": 0, "unknown": 0}
    for record in records:
        freshness[str(record["freshnessLevel"])] += 1
    return {
        "freshness": freshness,
        "contested": sum(1 for record in records if _is_contested_status(record["status"])),
        "lowConfidence": sum(
            1 for record in records if isinstance(record["confidence"], (int, float)) and record["confidence"] < 0.5
        ),
        "missingEvidence": sum(1 for record in records if record["missingEvidence"]),
    }


def _claim_health_records(pages: Sequence[WikiPageSummary]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page in sorted(pages, key=lambda item: item.path):
        for claim in page.claims:
            records.append(
                {
                    "pagePath": page.path,
                    "pageTitle": page.title,
                    "claimId": claim.id,
                    "text": claim.text,
                    "status": claim.status,
                    "confidence": claim.confidence,
                    "evidenceCount": len(claim.evidence),
                    "missingEvidence": len(claim.evidence) == 0,
                    "freshnessLevel": _claim_freshness_level(claim),
                }
            )
    return sorted(records, key=lambda item: (str(item["pagePath"]), str(item.get("claimId") or ""), str(item["text"])))


def _evidence_record(evidence: WikiEvidence) -> dict[str, Any]:
    return {
        "kind": evidence.kind,
        "sourceId": evidence.source_id,
        "path": evidence.path,
        "lines": evidence.lines,
        "weight": evidence.weight,
        "confidence": evidence.confidence,
        "privacyTier": evidence.privacy_tier,
        "updatedAt": evidence.updated_at,
        "note": evidence.note,
        "text": evidence.text,
    }


def _claim_records(pages: Sequence[WikiPageSummary], search_documents: Sequence[SearchDocument]) -> Iterable[dict[str, Any]]:
    claim_documents = _claim_document_map(search_documents)
    for page in pages:
        for ordinal, claim in enumerate(page.claims):
            claim_document = claim_documents.get((page.path, ordinal))
            yield {
                "pagePath": page.path,
                "pageId": page.id,
                "pageTitle": page.title,
                "claimId": claim.id or _fallback_claim_id_from_document(claim_document, ordinal),
                "claimDocumentId": claim_document.id if claim_document else None,
                "text": claim.text,
                "status": claim.status,
                "confidence": claim.confidence,
                "evidence": [_evidence_record(evidence) for evidence in claim.evidence],
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
        _reject_symlink(path.parent, "Generated output directory")
        _reject_symlink(path, "Generated output path")
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        updated.append(path)
    return updated


def _append_compile_log(root: Path, updated_files: Sequence[Path]) -> None:
    log_path = root / METADATA_DIRECTORY / "log.jsonl"
    _reject_symlink(log_path.parent, "Generated log directory")
    _reject_symlink(log_path, "Generated log path")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": "compile",
        "createdAt": datetime.now(UTC).isoformat(),
        "updatedFiles": [_display_path(root, path) for path in updated_files],
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _read_existing_or_default(path: Path, default: str) -> str:
    _reject_symlink(path, "Generated output path")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return default


def _replace_managed_markdown(original: str, marker_slug: str, heading: str, body: str) -> str:
    generated_block = _render_generated_block(marker_slug, heading, body)
    marker_pattern = re.compile(
        rf"<!--\s*(?:hermes|hermes-wiki|openclaw):wiki:{re.escape(marker_slug)}:start\s*-->\n?.*?"
        rf"<!--\s*(?:hermes|hermes-wiki|openclaw):wiki:{re.escape(marker_slug)}:end\s*-->\n?",
        flags=re.DOTALL,
    )
    generic_pattern = re.compile(
        r"<!--\s*(?:hermes:wiki:generated|hermes-wiki:generated|openclaw:wiki:generated):start\s*-->\n?.*?"
        r"<!--\s*(?:hermes:wiki:generated|hermes-wiki:generated|openclaw:wiki:generated):end\s*-->\n?",
        flags=re.DOTALL,
    )
    for pattern in (marker_pattern, generic_pattern):
        if pattern.search(original):
            return _ensure_trailing_newline(pattern.sub(generated_block, original, count=1))
    return _ensure_trailing_newline(f"{original.rstrip()}\n\n{generated_block.rstrip()}\n")


def _render_generated_block(marker_slug: str, heading: str, body: str) -> str:
    generated_body = body.strip()
    return (
        f"<!-- hermes:wiki:{marker_slug}:start -->\n"
        f"{heading}\n\n"
        f"{generated_body}\n"
        f"<!-- hermes:wiki:{marker_slug}:end -->\n"
    )


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else f"{text}\n"


def _page_link(page: WikiPageSummary) -> str:
    return f"[{page.title}](../{page.path})"


def _format_claim_health_line(claim: dict[str, Any]) -> str:
    details = [
        f"status {claim['status']}",
        f"confidence {float(claim['confidence']):.2f}" if isinstance(claim.get("confidence"), (int, float)) else None,
        "missing evidence" if claim.get("missingEvidence") else f"{claim['evidenceCount']} evidence",
        str(claim["freshnessLevel"]),
    ]
    detail_text = ", ".join(detail for detail in details if detail)
    claim_identity = f"`{claim['claimId']}`: {claim['text']}" if claim.get("claimId") else str(claim["text"])
    return f"[{claim['pageTitle']}](../{claim['pagePath']}): {claim_identity} ({detail_text})"


def _claim_freshness_level(claim: WikiClaim) -> str:
    return "fresh" if claim.updated_at else "unknown"


def _is_contested_status(status: Any) -> bool:
    normalized = _nonempty_string(status)
    return normalized in {"contested", "contradicted", "conflicting", "deprecated", "superseded"}


def _nonempty_string(value: Any) -> str | None:
    if value is None:
        return None
    text = value.strip() if isinstance(value, str) else str(value).strip()
    return text or None


def _basename(path: str) -> str:
    return PurePosixPath(path).name


def _display_path(root: Path, path: Path) -> str:
    return "." if path == root else path.relative_to(root).as_posix()


def _claim_document_map(search_documents: Sequence[SearchDocument]) -> dict[tuple[str, int], SearchDocument]:
    claim_documents: dict[tuple[str, int], SearchDocument] = {}
    for document in search_documents:
        if document.doc_type != "claim":
            continue
        ordinal = document.metadata.get("claim_ordinal")
        if isinstance(ordinal, int):
            claim_documents[(document.page_path, ordinal)] = document
    return claim_documents


def _fallback_claim_id_from_document(claim_document: SearchDocument | None, ordinal: int) -> str:
    if claim_document is not None:
        prefix = f"claim:{claim_document.page_path}:"
        if claim_document.id.startswith(prefix):
            claim_part = claim_document.id.removeprefix(prefix).replace(":", "-", 1)
            return f"claim-{claim_part}"
    return f"claim-{ordinal}"


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink: {path}")
