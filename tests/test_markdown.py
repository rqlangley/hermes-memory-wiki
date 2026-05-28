import pytest

from hermes_memory_wiki.markdown import (
    HERMES_GENERATED_END,
    HERMES_GENERATED_START,
    HERMES_HUMAN_END,
    HERMES_HUMAN_START,
    WikiMarkdown,
    WikiMarkdownError,
    ensure_human_notes_block,
    parse_wiki_markdown,
    render_wiki_markdown,
    replace_managed_block,
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


def test_replace_managed_block_replaces_hermes_generated_block():
    original = f"""# Note

{HERMES_GENERATED_START}
## Old Heading

Old generated text.
{HERMES_GENERATED_END}
"""

    replaced = replace_managed_block(original, "New Heading", "New generated text.")

    assert replaced == f"""# Note

{HERMES_GENERATED_START}
## New Heading

New generated text.
{HERMES_GENERATED_END}
"""
    assert "Old generated text." not in replaced


def test_replace_managed_block_preserves_hermes_human_block():
    original = f"""{HERMES_GENERATED_START}
## Managed

Old generated text.
{HERMES_GENERATED_END}

{HERMES_HUMAN_START}
## Human Notes

Keep my handwritten note.
{HERMES_HUMAN_END}
"""

    replaced = replace_managed_block(original, "Managed", "New generated text.")

    assert f"""{HERMES_HUMAN_START}
## Human Notes

Keep my handwritten note.
{HERMES_HUMAN_END}""" in replaced
    assert "New generated text." in replaced
    assert "Old generated text." not in replaced


def test_managed_helpers_recognize_openclaw_generated_and_human_markers():
    original = """Intro text.

<!-- openclaw:wiki:generated:start -->
## Old Managed

Old OpenClaw generated text.
<!-- openclaw:wiki:generated:end -->

<!-- openclaw:human:start -->
OpenClaw human note.
<!-- openclaw:human:end -->
"""

    replaced = replace_managed_block(original, "New Managed", "New Hermes generated text.")

    assert "<!-- openclaw:wiki:generated:start -->" not in replaced
    assert HERMES_GENERATED_START in replaced
    assert "Old OpenClaw generated text." not in replaced
    assert "New Hermes generated text." in replaced
    assert "<!-- openclaw:human:start -->\nOpenClaw human note.\n<!-- openclaw:human:end -->" in replaced
    assert ensure_human_notes_block(original) == original


def test_emitted_markers_use_approved_hermes_wiki_constants():
    body = replace_managed_block("# Note\n", "Managed", "Generated text.")
    body = ensure_human_notes_block(body)

    assert "<!-- hermes:wiki:generated:start -->" in body
    assert "<!-- hermes:wiki:generated:end -->" in body
    assert "<!-- hermes:human:start -->" in body
    assert "<!-- hermes:human:end -->" in body
    assert "hermes-wiki:" not in body


def test_ensure_human_notes_block_adds_missing_human_notes_block():
    body = f"""{HERMES_GENERATED_START}
## Managed

Generated text.
{HERMES_GENERATED_END}
"""

    ensured = ensure_human_notes_block(body)

    assert ensured == f"""{HERMES_GENERATED_START}
## Managed

Generated text.
{HERMES_GENERATED_END}

{HERMES_HUMAN_START}
## Human Notes

{HERMES_HUMAN_END}
"""


def test_replace_managed_block_never_deletes_text_outside_generated_block():
    original = f"""Preface paragraph.

{HERMES_GENERATED_START}
## Managed

Old generated text.
{HERMES_GENERATED_END}

Appendix paragraph.
"""

    replaced = replace_managed_block(original, "Managed", "New generated text.")

    assert replaced.startswith("Preface paragraph.\n\n")
    assert replaced.endswith("\n\nAppendix paragraph.\n")
    assert "New generated text." in replaced
    assert "Old generated text." not in replaced
