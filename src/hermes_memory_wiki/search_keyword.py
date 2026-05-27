from __future__ import annotations

import re
from typing import Any

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
