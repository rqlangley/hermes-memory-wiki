"""Structured wiki mutations for Hermes memory wiki pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from pathlib import PurePosixPath
import re
from typing import Any, Mapping

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.markdown import (
    WikiMarkdown,
    ensure_human_notes_block,
    parse_wiki_markdown,
    render_wiki_markdown,
    replace_managed_block,
)
from hermes_memory_wiki.paths import safe_join, to_display_path


@dataclass(frozen=True)
class WikiMutation:
    """Normalized structured mutation."""

    type: str
    title: str
    body: str
    source_ids: list[str]
    claims: list[dict[str, Any]] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    confidence: int | float | None = None
    status: str = "draft"
    path: str | None = None
    id: str | None = None


@dataclass(frozen=True)
class ApplyResult:
    """Result of applying a wiki mutation."""

    path: str
    id: str
    created: bool


def normalize_mutation(raw: Mapping[str, Any]) -> WikiMutation:
    """Validate and normalize a raw structured wiki mutation."""
    mutation_type = _required_string(raw, "op")
    if mutation_type != "create_synthesis":
        raise ValueError(f"unsupported mutation op: {mutation_type}")

    title = _required_string(raw, "title")
    body = _required_string(raw, "body")
    source_ids = _required_string_list(raw, "sourceIds")

    return WikiMutation(
        type=mutation_type,
        title=title,
        body=body,
        source_ids=source_ids,
        claims=_claims(raw.get("claims")),
        questions=_string_list(raw.get("questions")),
        contradictions=_string_list(raw.get("contradictions")),
        confidence=_optional_confidence(raw.get("confidence")),
        status=_optional_string(raw.get("status")) or "draft",
        path=_optional_string(raw.get("path")),
        id=_optional_string(raw.get("id")),
    )


def apply_mutation(config: MemoryWikiConfig, mutation: WikiMutation) -> ApplyResult:
    """Apply a normalized wiki mutation to the configured vault."""
    if mutation.type != "create_synthesis":
        raise ValueError(f"unsupported mutation type: {mutation.type}")
    return _apply_create_synthesis(config, mutation)


def _apply_create_synthesis(config: MemoryWikiConfig, mutation: WikiMutation) -> ApplyResult:
    slug = _slugify(mutation.title)
    relative_path = mutation.path or f"syntheses/{slug}.md"
    page_id = mutation.id or f"synthesis.{PurePosixPath(relative_path).stem}"
    path = safe_join(config.vault_path, relative_path)
    display_path = to_display_path(config.vault_path, path)
    _validate_synthesis_path(display_path)

    created = not path.exists()
    existing_body = ""
    if path.exists():
        if not path.is_file():
            raise IsADirectoryError(f"wiki page path exists and is not a file: {path}")
        existing_body = parse_wiki_markdown(path.read_text(encoding="utf-8")).body
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_body = f"# {mutation.title}\n"

    frontmatter = {
        "id": page_id,
        "title": mutation.title,
        "pageType": "synthesis",
        "sourceIds": mutation.source_ids,
        "claims": mutation.claims,
        "status": mutation.status,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if mutation.questions:
        frontmatter["questions"] = mutation.questions
    if mutation.contradictions:
        frontmatter["contradictions"] = mutation.contradictions
    if mutation.confidence is not None:
        frontmatter["confidence"] = mutation.confidence
    body = replace_managed_block(existing_body, "Summary", mutation.body)
    body = ensure_human_notes_block(body)
    path.write_text(render_wiki_markdown(WikiMarkdown(frontmatter, body)), encoding="utf-8")

    return ApplyResult(path=display_path, id=page_id, created=created)


def _required_string(raw: Mapping[str, Any], key: str) -> str:
    value = _optional_string(raw.get(key))
    if value is None:
        raise ValueError(f"{key} is required")
    return value


def _required_string_list(raw: Mapping[str, Any], key: str) -> list[str]:
    if key not in raw:
        raise ValueError(f"{key} is required")
    values = _string_list(raw.get(key))
    if not values:
        raise ValueError(f"{key} is required")
    return values


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    return text or None


def _optional_confidence(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be a number between 0 and 1")
    if not math.isfinite(value) or value < 0 or value > 1:
        raise ValueError("confidence must be a number between 0 and 1")
    return value


def _validate_synthesis_path(display_path: str) -> None:
    path = PurePosixPath(display_path)
    if len(path.parts) != 2 or path.parts[0] != "syntheses" or path.suffix != ".md" or not path.stem:
        raise ValueError("create_synthesis path must match syntheses/<name>.md")


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            text = _optional_string(item)
            if text:
                items.append(text)
        return items
    text = _optional_string(value)
    return [text] if text else []


def _claims(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    claims: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, Mapping):
            continue
        claims.append(dict(item))
    return claims


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "synthesis"
