from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import yaml


HERMES_GENERATED_START = "<!-- hermes:wiki:generated:start -->"
HERMES_GENERATED_END = "<!-- hermes:wiki:generated:end -->"
HERMES_HUMAN_START = "<!-- hermes:human:start -->"
HERMES_HUMAN_END = "<!-- hermes:human:end -->"

OPENCLAW_GENERATED_START = "<!-- openclaw:wiki:generated:start -->"
OPENCLAW_GENERATED_END = "<!-- openclaw:wiki:generated:end -->"
OPENCLAW_HUMAN_START = "<!-- openclaw:human:start -->"
OPENCLAW_HUMAN_END = "<!-- openclaw:human:end -->"

_GENERATED_MARKER_PAIRS = (
    (HERMES_GENERATED_START, HERMES_GENERATED_END),
    (OPENCLAW_GENERATED_START, OPENCLAW_GENERATED_END),
)
_HUMAN_MARKER_PAIRS = (
    (HERMES_HUMAN_START, HERMES_HUMAN_END),
    (OPENCLAW_HUMAN_START, OPENCLAW_HUMAN_END),
)


@dataclass
class WikiMarkdown:
    frontmatter: dict[str, Any]
    body: str


class WikiMarkdownError(ValueError):
    """Raised when wiki markdown cannot be parsed or rendered safely."""


def parse_wiki_markdown(text: str) -> WikiMarkdown:
    """Parse a markdown document into YAML frontmatter and body."""
    if not _starts_with_frontmatter(text):
        return WikiMarkdown(frontmatter={}, body=text)

    closing_delimiter_start = _find_closing_frontmatter_delimiter(text)
    if closing_delimiter_start is None:
        return WikiMarkdown(frontmatter={}, body=text)

    opening_delimiter_end = text.find("\n") + 1
    yaml_text = text[opening_delimiter_end:closing_delimiter_start]
    closing_delimiter_end = text.find("\n", closing_delimiter_start)
    body_start = len(text) if closing_delimiter_end == -1 else closing_delimiter_end + 1

    try:
        loaded = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise WikiMarkdownError(f"Invalid YAML frontmatter: {exc}") from exc

    if loaded is None:
        frontmatter: dict[str, Any] = {}
    elif isinstance(loaded, dict):
        frontmatter = loaded
    else:
        raise WikiMarkdownError("Invalid YAML frontmatter: expected a mapping")

    return WikiMarkdown(frontmatter=frontmatter, body=text[body_start:])


def render_wiki_markdown(doc: WikiMarkdown) -> str:
    """Render wiki markdown with YAML frontmatter and a trailing newline."""
    body = _ensure_trailing_newline(doc.body)
    if not doc.frontmatter:
        return body

    yaml_text = yaml.safe_dump(
        doc.frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{yaml_text}---\n{body}"


def replace_managed_block(original: str, heading: str, body: str) -> str:
    """Replace the generated wiki block while preserving all surrounding text."""
    generated_block = _render_generated_block(heading, body)
    match = _find_marker_block(original, _GENERATED_MARKER_PAIRS)
    if match is None:
        return _append_block(original, generated_block)

    replaced = f"{original[: match.start()]}{generated_block}{original[match.end():]}"
    return _ensure_trailing_newline(replaced)


def ensure_human_notes_block(body: str) -> str:
    """Append an empty human notes block unless one already exists."""
    if _find_marker_block(body, _HUMAN_MARKER_PAIRS) is not None:
        return body

    human_block = f"{HERMES_HUMAN_START}\n## Human Notes\n\n{HERMES_HUMAN_END}\n"
    return _append_block(body, human_block)


def _starts_with_frontmatter(text: str) -> bool:
    return text == "---" or text.startswith("---\n")


def _find_closing_frontmatter_delimiter(text: str) -> int | None:
    search_from = text.find("\n") + 1
    if search_from == 0:
        return None

    delimiter = "\n---\n"
    index = text.find(delimiter, search_from - 1)
    if index != -1:
        return index + 1

    ending_delimiter = "\n---"
    if text.endswith(ending_delimiter):
        return len(text) - len("---")

    return None


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else f"{text}\n"


def _render_generated_block(heading: str, body: str) -> str:
    heading_line = heading if heading.lstrip().startswith("#") else f"## {heading}"
    generated_body = body.strip()
    if generated_body:
        return (
            f"{HERMES_GENERATED_START}\n"
            f"{heading_line}\n\n"
            f"{generated_body}\n"
            f"{HERMES_GENERATED_END}\n"
        )

    return f"{HERMES_GENERATED_START}\n{heading_line}\n\n{HERMES_GENERATED_END}\n"


def _find_marker_block(text: str, marker_pairs: tuple[tuple[str, str], ...]) -> re.Match[str] | None:
    matches: list[re.Match[str]] = []
    for start, end in marker_pairs:
        pattern = re.compile(
            rf"{re.escape(start)}\n?.*?{re.escape(end)}\n?",
            flags=re.DOTALL,
        )
        matches.extend(pattern.finditer(text))

    return min(matches, key=lambda match: match.start(), default=None)


def _append_block(text: str, block: str) -> str:
    if not text.strip():
        return _ensure_trailing_newline(block.strip("\n"))

    return f"{text.rstrip()}\n\n{block.strip()}\n"
