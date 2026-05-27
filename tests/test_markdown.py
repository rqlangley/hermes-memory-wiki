import pytest

from hermes_memory_wiki.markdown import (
    WikiMarkdown,
    WikiMarkdownError,
    parse_wiki_markdown,
    render_wiki_markdown,
)


def test_parse_markdown_with_yaml_frontmatter():
    text = """---
title: Project Alpha
tags:
  - memory
  - wiki
count: 2
---
# Project Alpha

Body text.
"""

    doc = parse_wiki_markdown(text)

    assert doc.frontmatter == {
        "title": "Project Alpha",
        "tags": ["memory", "wiki"],
        "count": 2,
    }
    assert doc.body == "# Project Alpha\n\nBody text.\n"


def test_parse_markdown_without_frontmatter():
    text = "# Plain Note\n\nNo metadata here.\n"

    doc = parse_wiki_markdown(text)

    assert doc.frontmatter == {}
    assert doc.body == text


def test_render_frontmatter_and_body_with_trailing_newline():
    doc = WikiMarkdown({"title": "Project Alpha", "tags": ["memory", "wiki"]}, "# Heading")

    rendered = render_wiki_markdown(doc)

    assert rendered.endswith("\n")
    assert rendered == "---\ntitle: Project Alpha\ntags:\n- memory\n- wiki\n---\n# Heading\n"


def test_render_preserves_unknown_frontmatter_fields():
    doc = WikiMarkdown(
        {
            "title": "Known Field",
            "custom_nested": {"enabled": True, "threshold": 3},
            "unknown_list": ["one", "two"],
        },
        "Body\n",
    )

    parsed = parse_wiki_markdown(render_wiki_markdown(doc))

    assert parsed.frontmatter["custom_nested"] == {"enabled": True, "threshold": 3}
    assert parsed.frontmatter["unknown_list"] == ["one", "two"]
    assert parsed.body == "Body\n"


def test_body_excludes_frontmatter_delimiters():
    text = "---\ntitle: Delimited\n---\nBody starts here.\n---\nThis delimiter-like line is body.\n"

    doc = parse_wiki_markdown(text)

    assert doc.body == "Body starts here.\n---\nThis delimiter-like line is body.\n"
    assert "title: Delimited" not in doc.body


def test_invalid_yaml_raises_clear_wiki_markdown_error():
    text = "---\ntitle: [broken\n---\nBody\n"

    with pytest.raises(WikiMarkdownError, match="Invalid YAML frontmatter"):
        parse_wiki_markdown(text)
