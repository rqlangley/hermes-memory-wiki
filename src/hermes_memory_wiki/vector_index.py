from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from hermes_memory_wiki.markdown import (
    HERMES_GENERATED_END,
    HERMES_GENERATED_START,
    OPENCLAW_GENERATED_END,
    OPENCLAW_GENERATED_START,
    parse_wiki_markdown,
)
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary

_GENERATED_BLOCK_RE = re.compile(
    r"(?:"
    + re.escape(HERMES_GENERATED_START)
    + r"\n?.*?"
    + re.escape(HERMES_GENERATED_END)
    + r"\n?)|(?:"
    + re.escape(OPENCLAW_GENERATED_START)
    + r"\n?.*?"
    + re.escape(OPENCLAW_GENERATED_END)
    + r"\n?)",
    flags=re.DOTALL,
)


@dataclass
class SearchDocument:
    id: str
    page_path: str
    kind: str
    title: str
    doc_type: Literal["page", "claim"]
    text: str
    text_hash: str
    metadata: dict[str, Any]


def build_search_documents(pages: Sequence[WikiPageSummary]) -> list[SearchDocument]:
    """Convert wiki page summaries into deterministic page and claim search documents."""
    documents: list[SearchDocument] = []
    for page in pages:
        page_text = _build_page_text(page)
        documents.append(
            SearchDocument(
                id=f"page:{page.path}",
                page_path=page.path,
                kind=page.kind,
                title=page.title,
                doc_type="page",
                text=page_text,
                text_hash=_text_hash(page_text),
                metadata={
                    "page_id": page.id,
                    "source_ids": list(page.source_ids),
                    "aliases": list(page.aliases),
                    "claim_count": len(page.claims),
                    "question_count": len(page.questions),
                    "contradiction_count": len(page.contradictions),
                },
            )
        )

        for ordinal, claim in enumerate(page.claims):
            claim_id = _claim_document_id(page, claim, ordinal)
            claim_text = _build_claim_text(page, claim, ordinal)
            documents.append(
                SearchDocument(
                    id=claim_id,
                    page_path=page.path,
                    kind=page.kind,
                    title=page.title,
                    doc_type="claim",
                    text=claim_text,
                    text_hash=_text_hash(claim_text),
                    metadata={
                        "page_id": page.id,
                        "claim_id": claim.id,
                        "claim_ordinal": ordinal,
                        "status": claim.status,
                        "confidence": claim.confidence,
                        "page_source_ids": list(page.source_ids),
                        "evidence": [_evidence_metadata(evidence) for evidence in claim.evidence],
                    },
                )
            )
    return documents


def _build_page_text(page: WikiPageSummary) -> str:
    lines = [
        f"Title: {page.title}",
        f"Path: {page.path}",
        f"Kind: {page.kind}",
        f"Aliases: {_join_values(page.aliases)}",
        f"Source IDs: {_join_values(page.source_ids)}",
        "Claims:",
    ]
    lines.extend(_claim_summary_lines(page.claims))
    lines.append("Questions:")
    lines.extend(_bullet_lines(page.questions))
    lines.append("Contradictions:")
    lines.extend(_bullet_lines(page.contradictions))
    lines.extend(["Body:", _clean_body(page.body)])
    return "\n".join(lines).strip()


def _build_claim_text(page: WikiPageSummary, claim: WikiClaim, ordinal: int) -> str:
    display_claim_id = claim.id or _fallback_claim_id(claim, ordinal)
    lines = [
        f"Page: {page.title}",
        f"Path: {page.path}",
        f"Claim ID: {display_claim_id}",
        f"Claim: {claim.text}",
        f"Status: {_format_optional(claim.status)}",
        f"Confidence: {_format_optional(claim.confidence)}",
        f"Page Source IDs: {_join_values(page.source_ids)}",
        "Evidence:",
    ]
    lines.extend(_evidence_lines(claim.evidence))
    return "\n".join(lines).strip()


def _claim_summary_lines(claims: Sequence[WikiClaim]) -> list[str]:
    if not claims:
        return []
    lines: list[str] = []
    for ordinal, claim in enumerate(claims):
        if claim.id:
            lines.append(f"- {claim.id}: {claim.text}")
        else:
            lines.append(f"- {_fallback_claim_id(claim, ordinal)}: {claim.text}")
    return lines


def _bullet_lines(values: Sequence[Any]) -> list[str]:
    return [f"- {value}" for value in values]


def _evidence_lines(evidence_items: Sequence[WikiEvidence]) -> list[str]:
    lines: list[str] = []
    for evidence in evidence_items:
        fields = [
            f"source_id={_format_optional(evidence.source_id)}",
            f"kind={_format_optional(evidence.kind)}",
            f"note={_format_optional(evidence.note)}",
            f"path={_format_optional(evidence.path)}",
            f"lines={_join_values(evidence.lines, separator=',')}",
            f"confidence={_format_optional(evidence.confidence)}",
            f"text={_format_optional(evidence.text)}",
        ]
        lines.append(f"- {'; '.join(fields)}")
    return lines


def _evidence_metadata(evidence: WikiEvidence) -> dict[str, Any]:
    return {
        "kind": evidence.kind,
        "source_id": evidence.source_id,
        "path": evidence.path,
        "lines": list(evidence.lines),
        "confidence": evidence.confidence,
        "note": evidence.note,
        "text": evidence.text,
    }


def _claim_document_id(page: WikiPageSummary, claim: WikiClaim, ordinal: int) -> str:
    if claim.id:
        claim_part = claim.id
    else:
        claim_part = f"{ordinal}:{_stable_short_hash(claim.text)}"
    return f"claim:{page.path}:{claim_part}"


def _fallback_claim_id(claim: WikiClaim, ordinal: int) -> str:
    return f"claim-{ordinal}-{_stable_short_hash(claim.text)}"


def _clean_body(body: str) -> str:
    parsed_body = parse_wiki_markdown(body).body
    return _GENERATED_BLOCK_RE.sub("", parsed_body).strip()


def _join_values(values: Sequence[Any], *, separator: str = ", ") -> str:
    return separator.join(str(value) for value in values)


def _format_optional(value: Any) -> str:
    return "" if value is None else str(value)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_short_hash(text: str) -> str:
    return _text_hash(text)[:12]
