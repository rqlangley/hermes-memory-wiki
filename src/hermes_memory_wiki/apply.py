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
from hermes_memory_wiki.vault import get_page


@dataclass(frozen=True)
class WikiMutation:
    """Normalized structured mutation."""

    type: str
    title: str = ""
    body: str = ""
    source_ids: list[str] = field(default_factory=list)
    entity_type: str = ""
    aliases: list[str] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    confidence: int | float | None = None
    status: str = "active"
    updated_at: str | None = None
    path: str | None = None
    id: str | None = None
    lookup: str | None = None
    update_fields: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ApplyResult:
    """Result of applying a wiki mutation."""

    path: str
    id: str
    created: bool


def normalize_mutation(raw: Mapping[str, Any]) -> WikiMutation:
    """Validate and normalize a raw structured wiki mutation."""
    mutation_type = _required_string(raw, "op")
    if mutation_type == "update_metadata":
        return _normalize_update_metadata(raw)
    if mutation_type == "upsert_entity":
        return _normalize_upsert_entity(raw)
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
        status=_optional_string(raw.get("status")) or "active",
    )


def apply_mutation(config: MemoryWikiConfig, mutation: WikiMutation) -> ApplyResult:
    """Apply a normalized wiki mutation to the configured vault."""
    if mutation.type == "update_metadata":
        return _apply_update_metadata(config, mutation)
    if mutation.type == "upsert_entity":
        return _apply_upsert_typed_page(config, mutation, page_type="entity")
    if mutation.type != "create_synthesis":
        raise ValueError(f"unsupported mutation type: {mutation.type}")
    return _apply_create_synthesis(config, mutation)


def _normalize_upsert_entity(raw: Mapping[str, Any]) -> WikiMutation:
    return WikiMutation(
        type="upsert_entity",
        title=_required_string(raw, "title"),
        body=_required_string(raw, "body"),
        source_ids=_required_string_list(raw, "sourceIds"),
        entity_type=_required_string(raw, "entityType"),
        aliases=_string_list(raw.get("aliases")),
        claims=_claims(raw.get("claims")),
        questions=_string_list(raw.get("questions")),
        contradictions=_string_list(raw.get("contradictions")),
        confidence=_optional_confidence(raw.get("confidence")),
        status=_optional_string(raw.get("status")) or "active",
        lookup=_optional_string(raw.get("lookup")),
    )



def _normalize_update_metadata(raw: Mapping[str, Any]) -> WikiMutation:
    update_fields = frozenset(
        key
        for key in (
            "sourceIds",
            "claims",
            "questions",
            "contradictions",
            "confidence",
            "status",
            "updatedAt",
        )
        if key in raw
    )
    return WikiMutation(
        type="update_metadata",
        lookup=_required_string(raw, "lookup"),
        title="",
        source_ids=_string_list(raw.get("sourceIds")) if "sourceIds" in raw else [],
        claims=_claims(raw.get("claims")) if "claims" in raw else [],
        questions=_string_list(raw.get("questions")) if "questions" in raw else [],
        contradictions=_string_list(raw.get("contradictions")) if "contradictions" in raw else [],
        confidence=_optional_confidence(raw.get("confidence")) if "confidence" in raw else None,
        status=_optional_string(raw.get("status")) or "",
        updated_at=_optional_string(raw.get("updatedAt")) if "updatedAt" in raw else None,
        update_fields=update_fields,
    )


def _apply_update_metadata(config: MemoryWikiConfig, mutation: WikiMutation) -> ApplyResult:
    lookup = mutation.lookup or ""
    page = get_page(config, lookup)
    if page is None:
        raise FileNotFoundError(f"wiki page not found for lookup: {lookup}")

    path = safe_join(config.vault_path, page.path)
    if not path.is_file():
        raise FileNotFoundError(f"wiki page not found at resolved path: {page.path}")

    doc = parse_wiki_markdown(path.read_text(encoding="utf-8"))
    frontmatter = dict(doc.frontmatter)


    if "sourceIds" in mutation.update_fields:
        frontmatter["sourceIds"] = mutation.source_ids
    if "claims" in mutation.update_fields:
        _set_or_remove(frontmatter, "claims", mutation.claims)
    if "questions" in mutation.update_fields:
        _set_or_remove(frontmatter, "questions", mutation.questions)
    if "contradictions" in mutation.update_fields:
        _set_or_remove(frontmatter, "contradictions", mutation.contradictions)
    if "status" in mutation.update_fields:
        _set_or_remove(frontmatter, "status", mutation.status)
    if "confidence" in mutation.update_fields:
        if mutation.confidence is None:
            frontmatter.pop("confidence", None)
        else:
            frontmatter["confidence"] = mutation.confidence

    if "updatedAt" in mutation.update_fields:
        if mutation.updated_at is None:
            frontmatter.pop("updatedAt", None)
        else:
            frontmatter["updatedAt"] = mutation.updated_at
    else:
        frontmatter["updatedAt"] = datetime.now(timezone.utc).isoformat()
    path.write_text(render_wiki_markdown(WikiMarkdown(frontmatter, doc.body)), encoding="utf-8")

    return ApplyResult(path=page.path, id=str(frontmatter.get("id") or page.id), created=False)


def _apply_create_synthesis(config: MemoryWikiConfig, mutation: WikiMutation) -> ApplyResult:
    slug = _slugify(mutation.title)
    relative_path = f"syntheses/{slug}.md"
    page_id = f"synthesis.{slug}"
    path = safe_join(config.vault_path, relative_path)
    display_path = to_display_path(config.vault_path, path)
    _validate_synthesis_path(display_path)

    created = not path.exists()
    existing_body = ""
    if path.exists():
        if not path.is_file():
            raise IsADirectoryError(f"wiki page path exists and is not a file: {path}")
        existing_doc = parse_wiki_markdown(path.read_text(encoding="utf-8"))
        existing_body = existing_doc.body
        page_id = _optional_string(existing_doc.frontmatter.get("id")) or page_id
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


def _apply_upsert_typed_page(config: MemoryWikiConfig, mutation: WikiMutation, *, page_type: str) -> ApplyResult:
    if mutation.lookup:
        page = get_page(config, mutation.lookup)
        if page is None:
            raise FileNotFoundError(f"wiki page not found for lookup: {mutation.lookup}")
        actual_page_type = getattr(page.page, "page_type", None)
        if actual_page_type != page_type:
            raise ValueError(f"lookup resolved to pageType {actual_page_type!r}; expected {page_type}")
        relative_path = page.path
        page_id = page.id
        path = safe_join(config.vault_path, relative_path)
        created = False
    else:
        slug = _slugify(mutation.title, fallback=page_type)
        directory = _page_type_directory(page_type)
        relative_path = f"{directory}/{slug}.md"
        page_id = f"{page_type}.{slug}"
        path = safe_join(config.vault_path, relative_path)
        created = not path.exists()

    display_path = to_display_path(config.vault_path, path)
    _validate_typed_page_path(display_path, page_type)

    if path.exists():
        if not path.is_file():
            raise IsADirectoryError(f"wiki page path exists and is not a file: {path}")
        existing_doc = parse_wiki_markdown(path.read_text(encoding="utf-8"))
        existing_body = existing_doc.body
        page_id = _optional_string(existing_doc.frontmatter.get("id")) or page_id
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_body = f"# {mutation.title}\n"

    frontmatter = {
        "id": page_id,
        "title": mutation.title,
        "pageType": page_type,
        "sourceIds": mutation.source_ids,
        "claims": mutation.claims,
        "status": mutation.status,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if page_type == "entity":
        frontmatter["entityType"] = mutation.entity_type
        if mutation.aliases:
            frontmatter["aliases"] = mutation.aliases
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


def _set_or_remove(frontmatter: dict[str, Any], key: str, value: Any) -> None:
    if value:
        frontmatter[key] = value
    else:
        frontmatter.pop(key, None)


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


def _validate_typed_page_path(display_path: str, page_type: str) -> None:
    path = PurePosixPath(display_path)
    directory = _page_type_directory(page_type)
    if len(path.parts) != 2 or path.parts[0] != directory or path.suffix != ".md" or not path.stem:
        raise ValueError(f"upsert_{page_type} path must match {directory}/<name>.md")


def _page_type_directory(page_type: str) -> str:
    if page_type == "entity":
        return "entities"
    if page_type == "concept":
        return "concepts"
    return f"{page_type}s"


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
            raise ValueError("claim must be an object")
        text = _optional_string(item.get("text"))
        if text is None:
            raise ValueError("claim text is required")
        claim: dict[str, Any] = {"text": text}
        for key in ("id", "status", "updatedAt"):
            if key in item:
                string_value = _optional_string(item.get(key))
                if string_value is not None:
                    claim[key] = string_value
        if "confidence" in item:
            try:
                claim["confidence"] = _optional_confidence(item.get("confidence"))
            except ValueError as exc:
                raise ValueError("claim confidence must be a number between 0 and 1") from exc
        if "evidence" in item:
            claim["evidence"] = _evidence_list(item.get("evidence"))
        claims.append(claim)
    return claims


def _evidence_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    evidence_items: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, Mapping):
            raise ValueError("evidence must be an object")
        evidence: dict[str, Any] = {}
        for key in ("kind", "sourceId", "path", "note", "text", "privacyTier", "updatedAt"):
            if key in item:
                value_text = item.get(key)
                if not isinstance(value_text, str):
                    raise ValueError(f"evidence {key} must be a string")
                if value_text.strip():
                    evidence[key] = value_text.strip()
        if "lines" in item:
            lines = item.get("lines")
            if not isinstance(lines, str):
                raise ValueError("evidence lines must be a string")
            if lines.strip():
                evidence["lines"] = lines.strip()
        for key in ("confidence", "weight"):
            if key in item:
                numeric_value = item.get(key)
                if isinstance(numeric_value, bool) or not isinstance(numeric_value, (int, float)) or not math.isfinite(numeric_value):
                    raise ValueError(f"evidence {key} must be a number")
                evidence[key] = numeric_value
        evidence_items.append(evidence)
    return evidence_items


def _slugify(title: str, *, fallback: str = "synthesis") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or fallback
