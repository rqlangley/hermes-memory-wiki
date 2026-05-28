"""Deterministic source ingestion for Hermes memory wiki vaults."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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


SUPPORTED_SOURCE_TYPES = {"local-file", "conversation-summary", "text"}


@dataclass(frozen=True)
class IngestResult:
    """Result of ingesting a source into the wiki vault."""

    path: str
    id: str
    title: str
    source_type: str
    bytes: int
    created: bool
    changed: bool


def ingest_source(config: MemoryWikiConfig, raw: Mapping[str, Any]) -> IngestResult:
    """Ingest a deterministic source page into ``sources/<slug>.md``.

    Supported source types are ``local-file``, ``conversation-summary``, and
    ``text``. This function does not call an LLM and never accepts an arbitrary
    output path from callers.
    """
    source_type = _required_string(raw, "sourceType")
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"unsupported sourceType: {source_type}")

    if source_type == "local-file":
        title, content, source_path, byte_count = _local_file_payload(raw)
    elif source_type == "conversation-summary":
        title = _required_string(raw, "title")
        content = _required_string(raw, "body")
        source_path = _optional_string(raw.get("sourcePath"))
        byte_count = len(content.encode("utf-8"))
    else:
        title = _required_string(raw, "title")
        content = _required_string(raw, "body")
        source_path = _optional_string(raw.get("sourcePath"))
        byte_count = len(content.encode("utf-8"))

    slug = _slugify(title)
    relative_path = f"sources/{slug}.md"
    path = safe_join(config.vault_path, relative_path)
    display_path = to_display_path(config.vault_path, path)
    page_id = f"source.{slug}"
    created = not path.exists()

    existing_doc: WikiMarkdown | None = None
    existing_text: str | None = None
    if path.exists():
        if not path.is_file():
            raise IsADirectoryError(f"wiki source path exists and is not a file: {path}")
        existing_text = path.read_text(encoding="utf-8")
        existing_doc = parse_wiki_markdown(existing_text)
        page_id = _optional_string(existing_doc.frontmatter.get("id")) or page_id

    now = datetime.now(timezone.utc).isoformat()
    frontmatter = dict(existing_doc.frontmatter) if existing_doc else {}
    ingested_at = _optional_string(frontmatter.get("ingestedAt")) or now
    existing_updated_at = _optional_string(frontmatter.get("updatedAt")) or now

    frontmatter.update(
        {
            "id": page_id,
            "title": title,
            "pageType": "source",
            "sourceType": source_type,
            "ingestedAt": ingested_at,
            "updatedAt": existing_updated_at,
            "status": "active",
        }
    )
    if source_path is not None:
        frontmatter["sourcePath"] = source_path
    else:
        frontmatter.pop("sourcePath", None)
    _set_optional(frontmatter, "sessionId", raw.get("sessionId"))
    _set_optional(frontmatter, "messageRange", raw.get("messageRange"))

    base_body = existing_doc.body if existing_doc else f"# {title}\n"
    if existing_doc is None or not base_body.lstrip().startswith("#"):
        base_body = f"# {title}\n{base_body}"
    managed_body = _managed_source_body(source_type, content, source_path, raw)
    body = replace_managed_block(base_body, "Source", managed_body)
    body = ensure_human_notes_block(body)

    candidate = render_wiki_markdown(WikiMarkdown(frontmatter, body))
    if existing_text == candidate:
        return IngestResult(
            path=display_path,
            id=page_id,
            title=title,
            source_type=source_type,
            bytes=byte_count,
            created=False,
            changed=False,
        )

    frontmatter["updatedAt"] = now
    final_text = render_wiki_markdown(WikiMarkdown(frontmatter, body))
    changed = existing_text != final_text
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(final_text, encoding="utf-8")

    return IngestResult(
        path=display_path,
        id=page_id,
        title=title,
        source_type=source_type,
        bytes=byte_count,
        created=created,
        changed=changed,
    )


def _local_file_payload(raw: Mapping[str, Any]) -> tuple[str, str, str, int]:
    input_path = Path(_required_string(raw, "inputPath")).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"local source file not found: {input_path}")
    with input_path.open("rb") as handle:
        prefix = handle.read(4096)
    if b"\x00" in prefix:
        raise ValueError(f"local source file appears binary: {input_path}")
    data = input_path.read_bytes()
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"local source file is not valid UTF-8 text: {input_path}") from exc
    title = _optional_string(raw.get("title")) or _title_from_path(input_path)
    return title, content, str(input_path), len(data)


def _managed_source_body(source_type: str, content: str, source_path: str | None, raw: Mapping[str, Any]) -> str:
    lines = [f"- Type: {source_type}"]
    if source_path:
        lines.append(f"- Path: {source_path}")
    session_id = _optional_string(raw.get("sessionId"))
    if session_id:
        lines.append(f"- Session: {session_id}")
    message_range = _optional_string(raw.get("messageRange"))
    if message_range:
        lines.append(f"- Message range: {message_range}")
    return f"\n".join(lines) + f"\n\n## Content\n\n{_fenced_text(content)}"


def _fenced_text(content: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", content)), default=0)
    fence = "`" * max(3, longest + 1)
    text = content if content.endswith("\n") else f"{content}\n"
    return f"{fence}text\n{text}{fence}"


def _title_from_path(path: Path) -> str:
    words = re.sub(r"[-_]+", " ", path.stem).strip()
    return words.title() or "Source"


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "source"


def _required_string(raw: Mapping[str, Any], key: str) -> str:
    value = _optional_string(raw.get(key))
    if value is None:
        raise ValueError(f"{key} is required")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    return text or None


def _set_optional(frontmatter: dict[str, Any], key: str, value: Any) -> None:
    text = _optional_string(value)
    if text is None:
        frontmatter.pop(key, None)
    else:
        frontmatter[key] = text
