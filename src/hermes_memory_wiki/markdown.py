from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


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
