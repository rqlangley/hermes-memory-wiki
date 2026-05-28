"""Lint wiki structural health and provenance issues."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.markdown import WikiMarkdownError
from hermes_memory_wiki.schema import WikiPageSummary, to_page_summary
from hermes_memory_wiki.vault import METADATA_DIRECTORY, list_wiki_markdown_files
from hermes_memory_wiki.vector_index import SearchDocument, build_search_documents

LOW_CONFIDENCE_THRESHOLD = 0.5
STALE_AFTER = timedelta(days=365)


@dataclass(frozen=True)
class LintIssue:
    severity: str
    category: str
    code: str
    message: str
    path: str | None = None
    page_id: str | None = None
    claim_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LintResult:
    vault_root: Path
    issues: list[LintIssue]
    markdown_path: Path
    json_path: Path
    updated_files: list[Path]

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def issue_count(self) -> int:
        return len(self.issues)


@dataclass(frozen=True)
class _ReadResult:
    pages: list[WikiPageSummary]
    issues: list[LintIssue]


def lint_vault(config: MemoryWikiConfig) -> LintResult:
    """Lint a memory wiki vault and write deterministic Markdown/JSON reports."""
    root = config.vault_path
    read_result = _read_pages_with_schema_issues(root)
    pages = sorted(read_result.pages, key=lambda page: page.path)

    issues: list[LintIssue] = []
    issues.extend(read_result.issues)
    issues.extend(_duplicate_id_issues(pages))
    issues.extend(_page_health_issues(pages))
    issues.extend(_broken_link_issues(pages))
    issues.extend(_vector_index_issues(root, pages))

    cache_dir = root / METADATA_DIRECTORY / "cache"
    _reject_symlink(root / METADATA_DIRECTORY, "Generated metadata directory")
    _reject_symlink(cache_dir, "Generated cache directory")
    cache_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = cache_dir / "lint-report.md"
    json_path = cache_dir / "lint-report.json"
    outputs = {
        markdown_path: _render_markdown(issues),
        json_path: _render_json(issues),
    }
    updated_files = _write_changed(outputs)

    return LintResult(
        vault_root=root,
        issues=issues,
        markdown_path=markdown_path,
        json_path=json_path,
        updated_files=updated_files,
    )


def _read_pages_with_schema_issues(root: Path) -> _ReadResult:
    pages: list[WikiPageSummary] = []
    issues: list[LintIssue] = []
    for relative_path in list_wiki_markdown_files(root):
        raw = (root / relative_path).read_text(encoding="utf-8")
        try:
            summary = to_page_summary(relative_path, raw)
        except WikiMarkdownError as error:
            issues.append(
                LintIssue(
                    severity="error",
                    category="schema",
                    code="invalid-markdown",
                    message=f"Invalid wiki markdown: {error}",
                    path=relative_path,
                )
            )
            continue
        if summary is not None:
            page_type = summary.page_type
            if not page_type:
                issues.append(
                    LintIssue(
                        severity="error",
                        category="schema",
                        code="missing-page-type",
                        message=f"Missing pageType; expected {summary.kind} for {relative_path}.",
                        path=relative_path,
                        page_id=summary.id,
                        details={"expected": summary.kind},
                    )
                )
            elif page_type != summary.kind:
                issues.append(
                    LintIssue(
                        severity="error",
                        category="schema",
                        code="page-type-mismatch",
                        message=f"pageType {page_type!r} must match directory-derived kind {summary.kind!r}.",
                        path=relative_path,
                        page_id=summary.id,
                        details={"expected": summary.kind, "actual": page_type},
                    )
                )
            pages.append(summary)
    return _ReadResult(pages=pages, issues=issues)


def _duplicate_id_issues(pages: Sequence[WikiPageSummary]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    paths_by_id: dict[str, list[str]] = {}
    for page in pages:
        paths_by_id.setdefault(page.id, []).append(page.path)
    for page_id, paths in sorted(paths_by_id.items()):
        if len(paths) > 1:
            sorted_paths = sorted(paths)
            issues.append(
                LintIssue(
                    severity="error",
                    category="schema",
                    code="duplicate-id",
                    message=f"Duplicate page id {page_id}: {', '.join(sorted_paths)}",
                    details={"id": page_id, "paths": sorted_paths},
                )
            )

    claim_refs_by_id: dict[str, list[tuple[str, str]]] = {}
    for page in pages:
        for claim in page.claims:
            if claim.id:
                claim_refs_by_id.setdefault(claim.id, []).append((page.path, page.id))
    for claim_id, refs in sorted(claim_refs_by_id.items()):
        if len(refs) > 1:
            paths = sorted(path for path, _ in refs)
            issues.append(
                LintIssue(
                    severity="error",
                    category="schema",
                    code="duplicate-claim-id",
                    message=f"Duplicate claim id {claim_id}: {', '.join(paths)}",
                    claim_id=claim_id,
                    details={"id": claim_id, "paths": paths},
                )
            )
    return issues


def _page_health_issues(pages: Sequence[WikiPageSummary]) -> list[LintIssue]:
    now = datetime.now(UTC)
    issues: list[LintIssue] = []
    for page in pages:
        if _is_low_confidence(page.confidence):
            issues.append(
                LintIssue(
                    severity="issue",
                    category="low-confidence",
                    code="low-confidence",
                    message=f"Page confidence is below {LOW_CONFIDENCE_THRESHOLD}.",
                    path=page.path,
                    page_id=page.id,
                    details={"confidence": page.confidence},
                )
            )
        for claim in page.claims:
            if not claim.evidence:
                issues.append(
                    LintIssue(
                        severity="warning",
                        category="provenance",
                        code="missing-claim-evidence",
                        message=f"Claim has no evidence: {claim.text}",
                        path=page.path,
                        page_id=page.id,
                        claim_id=claim.id,
                    )
                )
            if _is_low_confidence(claim.confidence):
                issues.append(
                    LintIssue(
                        severity="issue",
                        category="low-confidence",
                        code="low-confidence",
                        message=f"Claim confidence is below {LOW_CONFIDENCE_THRESHOLD}: {claim.text}",
                        path=page.path,
                        page_id=page.id,
                        claim_id=claim.id,
                        details={"confidence": claim.confidence},
                    )
                )

        for contradiction in page.contradictions:
            issues.append(
                LintIssue(
                    severity="issue",
                    category="contradiction",
                    code="contradiction",
                    message=f"Open contradiction: {contradiction}",
                    path=page.path,
                    page_id=page.id,
                )
            )
        for question in page.questions:
            issues.append(
                LintIssue(
                    severity="issue",
                    category="open-question",
                    code="open-question",
                    message=f"Open question: {question}",
                    path=page.path,
                    page_id=page.id,
                )
            )
        if _is_stale(page.updated_at, now):
            issues.append(
                LintIssue(
                    severity="issue",
                    category="stale",
                    code="stale-updated-at",
                    message=f"Page updatedAt is older than {STALE_AFTER.days} days: {page.updated_at}",
                    path=page.path,
                    page_id=page.id,
                    details={"updatedAt": page.updated_at},
                )
            )
    return issues


def _broken_link_issues(pages: Sequence[WikiPageSummary]) -> list[LintIssue]:
    page_ids = {page.id for page in pages}
    page_paths = {page.path for page in pages}
    issues: list[LintIssue] = []
    for page in pages:
        for source_id in page.source_ids:
            if source_id not in page_ids:
                issues.append(_broken_link_issue(page, None, source_id))
        for claim in page.claims:
            for evidence in claim.evidence:
                if evidence.source_id and evidence.source_id not in page_ids:
                    issues.append(_broken_link_issue(page, claim.id, evidence.source_id))
                if evidence.path and evidence.path not in page_paths:
                    issues.append(_broken_link_issue(page, claim.id, evidence.path))
    return issues


def _broken_link_issue(
    page: WikiPageSummary, claim_id: str | None, target: str
) -> LintIssue:
    return LintIssue(
        severity="issue",
        category="broken-link",
        code="broken-source-link",
        message=f"Broken source link: {target}",
        path=page.path,
        page_id=page.id,
        claim_id=claim_id,
        details={"target": target},
    )


def _vector_index_issues(root: Path, pages: Sequence[WikiPageSummary]) -> list[LintIssue]:
    metadata_dir = root / METADATA_DIRECTORY
    vector_dir = metadata_dir / "vector"
    db_path = vector_dir / "index.sqlite"
    for path in (metadata_dir, vector_dir, db_path):
        if path.is_symlink():
            return [_unsafe_vector_index_issue(root, path)]
    if not db_path.exists():
        return []
    try:
        stored = _stored_vector_documents(db_path)
    except sqlite3.Error as error:
        return [
            LintIssue(
                severity="warning",
                category="vector-index",
                code="stale-vector-index",
                message=f"Vector index could not be inspected: {error}",
                details={"indexPath": db_path.relative_to(root).as_posix()},
            )
        ]

    current_docs = {doc.id: doc for doc in build_search_documents(pages)}
    issues_by_location: dict[str, LintIssue] = {}
    for doc_id, doc in sorted(current_docs.items()):
        stored_hash = stored.get(doc_id)
        if stored_hash is None:
            issues_by_location.setdefault(
                doc.page_path,
                _vector_issue(doc, "One or more documents are missing from vector index."),
            )
        elif stored_hash != doc.text_hash:
            issues_by_location.setdefault(
                doc.page_path,
                _vector_issue(doc, "One or more document text hashes differ from vector index."),
            )
    for doc_id in sorted(set(stored) - set(current_docs)):
        issues_by_location.setdefault(
            doc_id,
            LintIssue(
                severity="warning",
                category="vector-index",
                code="stale-vector-index",
                message="Vector index contains a document that is no longer in the wiki.",
                details={"documentId": doc_id},
            ),
        )
    return list(issues_by_location.values())


def _stored_vector_documents(db_path: Path) -> dict[str, str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT id, text_hash FROM documents ORDER BY id").fetchall()
    return {str(doc_id): str(text_hash) for doc_id, text_hash in rows}


def _unsafe_vector_index_issue(root: Path, path: Path) -> LintIssue:
    return LintIssue(
        severity="warning",
        category="vector-index",
        code="stale-vector-index",
        message="Vector index was not inspected because its metadata path is a symlink.",
        details={"indexPath": path.relative_to(root).as_posix()},
    )


def _vector_issue(doc: SearchDocument, message: str) -> LintIssue:
    return LintIssue(
        severity="warning",
        category="vector-index",
        code="stale-vector-index",
        message=message,
        path=doc.page_path,
        details={"documentId": doc.id, "documentType": doc.doc_type},
    )


def _is_low_confidence(value: Any) -> bool:
    try:
        return float(value) < LOW_CONFIDENCE_THRESHOLD
    except (TypeError, ValueError):
        return False


def _is_stale(value: str | None, now: datetime) -> bool:
    if not value:
        return False
    try:
        updated_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return now - updated_at.astimezone(UTC) > STALE_AFTER


def _render_json(issues: Sequence[LintIssue]) -> str:
    payload = {
        "version": 1,
        "summary": {
            "issueCount": len(issues),
            "errorCount": sum(1 for issue in issues if issue.severity == "error"),
            "warningCount": sum(1 for issue in issues if issue.severity == "warning"),
        },
        "issues": [_issue_payload(issue) for issue in issues],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _render_markdown(issues: Sequence[LintIssue]) -> str:
    lines = [
        "# Memory Wiki Lint Report",
        "",
        "## Summary",
        "",
        f"- Total issues: {len(issues)}",
        f"- Errors: {sum(1 for issue in issues if issue.severity == 'error')}",
        f"- Warnings: {sum(1 for issue in issues if issue.severity == 'warning')}",
        "",
        "## Issues",
        "",
    ]
    if not issues:
        lines.append("No lint issues found.")
        return "\n".join(lines) + "\n"
    for issue in issues:
        location = issue.path or "vault"
        if issue.claim_id:
            location = f"{location}#{issue.claim_id}"
        lines.append(f"- **{issue.severity}** `{issue.code}` ({issue.category}) — {location}: {issue.message}")
    return "\n".join(lines) + "\n"


def _issue_payload(issue: LintIssue) -> dict[str, Any]:
    return {key: value for key, value in asdict(issue).items() if value not in (None, {}, [])}


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


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink: {path}")
