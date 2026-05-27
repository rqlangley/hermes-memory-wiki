from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from hermes_memory_wiki.markdown import (
    HERMES_GENERATED_END,
    HERMES_GENERATED_START,
    OPENCLAW_GENERATED_END,
    OPENCLAW_GENERATED_START,
    parse_wiki_markdown,
)
from hermes_memory_wiki.schema import WikiPageSummary

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9@._-]+", flags=re.IGNORECASE)
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

_CONTESTED_STATUSES = {"contested", "contradicted", "retracted", "deprecated", "inactive", "superseded"}


@dataclass
class WikiSearchResult:
    corpus: str
    path: str
    title: str
    kind: str
    score: float
    snippet: str
    search_mode: str
    matched_claim_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

def build_query_tokens(query: str) -> list[str]:
    """Return stable, unique keyword tokens for a free-text query."""
    tokens: list[str] = []
    seen: set[str] = set()
    for raw_token in _TOKEN_SPLIT_RE.split(query.lower()):
        token = raw_token.strip()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def build_page_search_text(page: WikiPageSummary) -> str:
    """Build deterministic searchable text from structured wiki page metadata."""
    values: list[str] = []

    _append_text(values, page.title)
    _append_text(values, page.path)
    _append_text(values, page.id)
    _append_text(values, page.kind)
    _append_text(values, _body_without_generated_blocks(page.body))
    _append_many(values, page.aliases)
    _append_many(values, page.source_ids)
    _append_many(values, page.questions)
    _append_many(values, page.contradictions)
    _append_text(values, page.person)
    _append_text(values, page.role)
    _append_many(values, page.best_used_for)
    _append_many(values, page.routes)
    _append_many(values, page.topics)
    _append_any(values, page.routing)

    if page.person_card is not None:
        _append_text(values, page.person_card.name)
        _append_text(values, page.person_card.role)
        _append_many(values, page.person_card.best_used_for)
        _append_many(values, page.person_card.topics)
        _append_any(values, page.person_card.routing)
        _append_many(values, page.person_card.routes)

    for claim in page.claims:
        _append_text(values, claim.text)
        _append_text(values, claim.id)
        for evidence in claim.evidence:
            _append_text(values, evidence.kind)
            _append_text(values, evidence.source_id)
            _append_text(values, evidence.path)
            _append_many(values, evidence.lines)
            _append_text(values, evidence.note)
            _append_text(values, evidence.text)

    return "\n".join(values)


def build_snippet(raw: str, query: str) -> str:
    """Build a deterministic one-line snippet from raw wiki markdown."""
    lines = [line.strip() for line in _build_snippet_search_text(raw).splitlines() if line.strip()]
    if not lines:
        return ""

    query_lower = query.lower().strip()
    tokens = build_query_tokens(query_lower)
    lowered_lines = [(line, line.lower()) for line in lines]

    if query_lower:
        for line, lowered in lowered_lines:
            if query_lower in lowered:
                return line

    if tokens:
        for line, lowered in lowered_lines:
            if all(token in lowered for token in tokens):
                return line

        scored = [(_token_hit_count(lowered, tokens), line) for line, lowered in lowered_lines]
        best_count, best_line = max(scored, key=lambda item: item[0])
        if best_count > 0:
            return best_line

    for line in lines:
        if line != "---":
            return line
    return ""


def score_page(page: WikiPageSummary, query: str, mode: str = "auto") -> float:
    """Score a page for keyword search using OpenClaw-like deterministic weights."""
    score, _claim = _score_page_with_claim(page, query, mode)
    return score


def keyword_search(
    pages: Sequence[WikiPageSummary], query: str, *, max_results: int = 10, mode: str = "auto"
) -> list[WikiSearchResult]:
    """Return keyword-ranked wiki pages with snippets and matched claim metadata."""
    results: list[WikiSearchResult] = []
    for page in pages:
        score, matched_claim = _score_page_with_claim(page, query, mode)
        if score <= 0:
            continue

        metadata: dict[str, Any] = {
            "id": page.id,
            "sourceIds": list(page.source_ids),
            "claimCount": len(page.claims),
        }
        matched_claim_id = None
        if matched_claim is not None:
            matched_claim_id = matched_claim.id
            metadata["matchedClaim"] = {
                "id": matched_claim.id,
                "status": matched_claim.status,
                "confidence": matched_claim.confidence,
                "text": matched_claim.text,
            }
            snippet = matched_claim.text
        else:
            snippet = build_snippet(page.body, query)

        results.append(
            WikiSearchResult(
                corpus="wiki",
                path=page.path,
                title=page.title,
                kind=page.kind,
                score=score,
                snippet=snippet,
                search_mode=mode,
                matched_claim_id=matched_claim_id,
                metadata=metadata,
            )
        )

    results.sort(key=lambda result: (-result.score, result.path))
    return results[:max_results]


def _score_page_with_claim(page: WikiPageSummary, query: str, mode: str) -> tuple[float, Any | None]:
    del mode  # Task 4.2 accepts mode but intentionally does not add mode-specific boosts.
    query_lower = query.lower().strip()
    tokens = build_query_tokens(query)
    if not query_lower and not tokens:
        return 0.0, None

    search_text = build_page_search_text(page).lower()
    if not _matches_text(search_text, query_lower, tokens):
        return 0.0, None

    score = 1.0
    score += _metadata_score(page, query_lower)
    score += _body_occurrence_score(page.body, query_lower, tokens)
    score += _token_boost_score(page, tokens)

    scored_claims = [(_score_claim(claim, query_lower, tokens), claim) for claim in page.claims]
    matching_claims = [(claim_score, claim) for claim_score, claim in scored_claims if claim_score > 0]
    matched_claim = None
    if matching_claims:
        matching_claims.sort(key=lambda item: item[0], reverse=True)
        best_claim_score, matched_claim = matching_claims[0]
        score += best_claim_score
        score += min(10.0, sum(claim_score for claim_score, _claim in matching_claims[1:]))

    return float(score), matched_claim


def _metadata_score(page: WikiPageSummary, query_lower: str) -> float:
    score = 0.0
    title = page.title.lower()
    path = page.path.lower()
    page_id = page.id.lower()
    if query_lower and query_lower == title:
        score += 50
    elif query_lower and query_lower in title:
        score += 20
    if query_lower and query_lower in path:
        score += 10
    if query_lower and query_lower in page_id:
        score += 20
    if query_lower and any(query_lower in source_id.lower() for source_id in page.source_ids):
        score += 12
    return score


def _score_claim(claim: Any, query_lower: str, tokens: list[str]) -> float:
    claim_text = (claim.text or "").lower()
    claim_id = (claim.id or "").lower()
    matched = False
    score = 0.0
    if query_lower and query_lower in claim_text:
        score += 25
        matched = True
    elif tokens and all(token in claim_text for token in tokens):
        score += 18
        matched = True
    if query_lower and query_lower in claim_id:
        score += 10
        matched = True
    if not matched:
        return 0.0

    confidence = _numeric_confidence(claim.confidence)
    if confidence is not None:
        score += round(confidence * 10)
    status = (claim.status or "").lower()
    score += -6 if status in _CONTESTED_STATUSES else 4
    score += _freshness_score(claim)
    return score


def _numeric_confidence(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _freshness_score(claim: Any) -> int:
    raw = claim.raw if isinstance(claim.raw, dict) else {}
    freshness = str(raw.get("freshnessLevel") or raw.get("freshness") or "unknown").lower()
    return {"fresh": 8, "aging": 4, "stale": -2}.get(freshness, -4)


def _body_occurrence_score(body: str, query_lower: str, tokens: list[str]) -> float:
    body_lower = _body_without_generated_blocks(body).lower()
    count = body_lower.count(query_lower) if query_lower else 0
    if count == 0 and tokens:
        count = sum(body_lower.count(token) for token in tokens)
    return float(min(10, count))


def _token_boost_score(page: WikiPageSummary, tokens: list[str]) -> float:
    score = 0.0
    title = page.title.lower()
    path_and_id = f"{page.path}\n{page.id}".lower()
    metadata = "\n".join(
        [*page.source_ids, *page.aliases, *page.questions, *page.contradictions, *page.best_used_for, *page.routes, *page.topics]
    ).lower()
    body = _body_without_generated_blocks(page.body).lower()
    for token in tokens:
        if token in title:
            score += 8
        if token in path_and_id:
            score += 6
        if token in metadata:
            score += 4
        if token in body:
            score += 1
    return score


def _matches_text(text: str, query_lower: str, tokens: list[str]) -> bool:
    return bool((query_lower and query_lower in text) or (tokens and all(token in text for token in tokens)))


def _build_snippet_search_text(raw: str) -> str:
    body = parse_wiki_markdown(raw).body
    return _body_without_generated_blocks(body)


def _body_without_generated_blocks(body: str) -> str:
    return _GENERATED_BLOCK_RE.sub("", body)


def _token_hit_count(line: str, tokens: list[str]) -> int:
    return sum(1 for token in tokens if token in line)


def _append_many(values: list[str], items: list[Any]) -> None:
    for item in items:
        _append_text(values, item)


def _append_any(values: list[str], value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _append_text(values, key)
            _append_any(values, item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _append_any(values, item)
        return
    if isinstance(value, set):
        for item in sorted(value, key=lambda item: str(item)):
            _append_any(values, item)
        return
    _append_text(values, value)


def _append_text(values: list[str], value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        values.append(text)
