from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal, Mapping

from hermes_memory_wiki.markdown import parse_wiki_markdown


@dataclass(frozen=True)
class WikiEvidence:
    kind: str | None = None
    source_id: str | None = None
    path: str | None = None
    lines: str | None = None
    confidence: Any = None
    weight: Any = None
    privacy_tier: str | None = None
    updated_at: str | None = None
    note: str | None = None
    text: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WikiClaim:
    text: str
    id: str | None = None
    status: str | None = None
    confidence: Any = None
    evidence: list[WikiEvidence] = field(default_factory=list)
    updated_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PersonCard:
    name: str | None = None
    role: str | None = None
    best_used_for: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    routing: dict[str, Any] = field(default_factory=dict)
    routes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WikiPageSummary:
    path: str
    kind: str
    id: str
    title: str
    page_type: str | None = None
    entity_type: str | None = None
    canonical_id: str | None = None
    source_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    claims: list[WikiClaim] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    status: str | None = None
    confidence: Any = None
    privacy_tier: str | None = None
    updated_at: str | None = None
    body: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
    person: str | None = None
    role: str | None = None
    best_used_for: list[str] = field(default_factory=list)
    not_enough_for: list[str] = field(default_factory=list)
    routing: dict[str, Any] = field(default_factory=dict)
    routes: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    person_card: PersonCard | None = None
    relationships: list[Any] = field(default_factory=list)
    source_type: str | None = None
    provenance_mode: str | None = None
    source_path: str | None = None
    bridge_relative_path: str | None = None
    bridge_workspace_dir: str | None = None
    unsafe_local_configured_path: str | None = None
    unsafe_local_relative_path: str | None = None
    last_refreshed_at: str | None = None


PageKind = Literal["entity", "concept", "synthesis", "source", "report"]


def infer_page_kind(relative_path: str) -> PageKind | None:
    """Infer OpenClaw broad page kind from the queryable directory."""
    normalized = relative_path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    first_segment = parts[0] if parts else ""
    if first_segment == "sources":
        return "source"
    if first_segment == "entities":
        return "entity"
    if first_segment == "concepts":
        return "concept"
    if first_segment == "syntheses":
        return "synthesis"
    if first_segment == "reports":
        return "report"
    return None


def page_kind_from_path(path: str, frontmatter: Mapping[str, Any]) -> str:
    """Return OpenClaw directory-derived broad page kind."""
    return infer_page_kind(path) or "page"


def to_page_summary(relative_path: str, raw: str) -> WikiPageSummary | None:
    """Parse raw wiki markdown into a normalized page summary."""
    doc = parse_wiki_markdown(raw)
    frontmatter = dict(doc.frontmatter)
    kind = page_kind_from_path(relative_path, frontmatter)
    title = _first_nonempty_string(frontmatter.get("title"), _extract_h1(doc.body), _title_from_path(relative_path))
    page_id = _first_nonempty_string(frontmatter.get("id"), f"{kind}:{_stem_slug(relative_path)}")

    person_card_mapping = _dict_mapping(frontmatter.get("personCard"))
    if person_card_mapping:
        best_used_for = _string_list(person_card_mapping.get("bestUsedFor"))
        topics = _string_list(person_card_mapping.get("topics"))
        routing = _dict_mapping(person_card_mapping.get("routing"))
        routes = _string_list(person_card_mapping.get("routes"))
        person = _optional_string(person_card_mapping.get("name"))
        role = _optional_string(person_card_mapping.get("role"))
    else:
        best_used_for = _string_list(frontmatter.get("bestUsedFor"))
        topics = _string_list(frontmatter.get("topics"))
        routing = _dict_mapping(frontmatter.get("routing"))
        routes = _string_list(frontmatter.get("routes"))
        person = _optional_string(frontmatter.get("person"))
        role = _optional_string(frontmatter.get("role"))
    not_enough_for = _string_list(frontmatter.get("notEnoughFor"))
    person_card = None
    if any([person, role, best_used_for, topics, routing, routes]):
        person_card = PersonCard(
            name=person,
            role=role,
            best_used_for=best_used_for,
            topics=topics,
            routing=routing,
            routes=routes,
        )

    return WikiPageSummary(
        path=relative_path,
        kind=kind,
        id=page_id,
        title=title,
        page_type=_optional_string(frontmatter.get("pageType")),
        entity_type=_optional_string(frontmatter.get("entityType")),
        canonical_id=_optional_string(frontmatter.get("canonicalId")),
        source_ids=_string_list(frontmatter.get("sourceIds")),
        aliases=_string_list(frontmatter.get("aliases")),
        claims=_claims(frontmatter.get("claims")),
        questions=_text_list(frontmatter.get("questions")),
        contradictions=_text_list(frontmatter.get("contradictions")),
        status=_optional_string(frontmatter.get("status")),
        confidence=frontmatter.get("confidence"),
        privacy_tier=_optional_string(frontmatter.get("privacyTier")),
        updated_at=_optional_string(frontmatter.get("updatedAt")),
        relationships=_list_value(frontmatter.get("relationships")),
        not_enough_for=not_enough_for,
        source_type=_optional_string(frontmatter.get("sourceType")),
        provenance_mode=_optional_string(frontmatter.get("provenanceMode")),
        source_path=_optional_string(frontmatter.get("sourcePath")),
        bridge_relative_path=_optional_string(frontmatter.get("bridgeRelativePath")),
        bridge_workspace_dir=_optional_string(frontmatter.get("bridgeWorkspaceDir")),
        unsafe_local_configured_path=_optional_string(frontmatter.get("unsafeLocalConfiguredPath")),
        unsafe_local_relative_path=_optional_string(frontmatter.get("unsafeLocalRelativePath")),
        last_refreshed_at=_optional_string(frontmatter.get("lastRefreshedAt")),
        body=doc.body,
        frontmatter=frontmatter,
        person=person,
        role=role,
        best_used_for=best_used_for,
        routing=routing,
        routes=routes,
        topics=topics,
        person_card=person_card,
    )


def _dict_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _first_nonempty_string(*values: Any) -> str:
    for value in values:
        text = _optional_string(value)
        if text:
            return text
    return ""


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    return text or None


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


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    items: list[str] = []
    for item in values:
        if isinstance(item, Mapping):
            text = _optional_string(item.get("text") or item.get("question") or item.get("claim"))
        else:
            text = _optional_string(item)
        if text:
            items.append(text)
    return items


def _claims(value: Any) -> list[WikiClaim]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    claims: list[WikiClaim] = []
    for item in values:
        if not isinstance(item, Mapping):
            continue
        text = _optional_string(item.get("text") or item.get("claim"))
        if not text:
            continue
        raw = dict(item)
        claims.append(
            WikiClaim(
                text=text,
                id=_optional_string(item.get("id")),
                status=_optional_string(item.get("status")),
                confidence=item.get("confidence"),
                evidence=_evidence_list(item.get("evidence")),
                updated_at=_optional_string(item.get("updatedAt")),
                raw=raw,
            )
        )
    return claims


def _evidence_list(value: Any) -> list[WikiEvidence]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    evidence_items: list[WikiEvidence] = []
    for item in values:
        if not isinstance(item, Mapping):
            continue
        raw = dict(item)
        evidence_items.append(
            WikiEvidence(
                kind=_optional_string(item.get("kind")),
                source_id=_optional_string(item.get("sourceId")),
                path=_optional_string(item.get("path")),
                lines=_optional_string(item.get("lines")),
                confidence=item.get("confidence"),
                weight=item.get("weight"),
                privacy_tier=_optional_string(item.get("privacyTier")),
                updated_at=_optional_string(item.get("updatedAt")),
                note=_optional_string(item.get("note")),
                text=_optional_string(item.get("text")),
                raw=raw,
            )
        )
    return evidence_items


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _extract_h1(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _stem_slug(path: str) -> str:
    stem = PurePosixPath(path).stem.strip()
    return stem or "page"


def _title_from_path(path: str) -> str:
    stem = _stem_slug(path)
    return stem.replace("-", " ").replace("_", " ").strip().title()
