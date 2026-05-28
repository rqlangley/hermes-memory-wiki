from __future__ import annotations

import re

import pytest

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.ingest import ingest_source
from hermes_memory_wiki.markdown import HERMES_HUMAN_END, HERMES_HUMAN_START, parse_wiki_markdown
from hermes_memory_wiki.vault import initialize_vault


def _config(root):
    return MemoryWikiConfig(vault_path=root)


def test_ingest_local_file_creates_source_page_with_frontmatter_body_and_result(tmp_path):
    vault = tmp_path / "vault"
    initialize_vault(_config(vault))
    source_file = tmp_path / "My_Source-Note.txt"
    source_file.write_text("Line one\nLine two\n", encoding="utf-8")

    result = ingest_source(_config(vault), {"sourceType": "local-file", "inputPath": str(source_file)})

    assert result.created is True
    assert result.changed is True
    assert result.path == "sources/my-source-note.md"
    assert result.id == "source.my-source-note"
    assert result.title == "My Source Note"
    assert result.source_type == "local-file"
    assert result.bytes == source_file.stat().st_size

    page = vault / result.path
    assert page.is_file()
    doc = parse_wiki_markdown(page.read_text(encoding="utf-8"))
    assert doc.frontmatter["pageType"] == "source"
    assert doc.frontmatter["id"] == "source.my-source-note"
    assert doc.frontmatter["title"] == "My Source Note"
    assert doc.frontmatter["sourceType"] == "local-file"
    assert doc.frontmatter["sourcePath"] == str(source_file.resolve())
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", doc.frontmatter["ingestedAt"])
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", doc.frontmatter["updatedAt"])
    assert doc.frontmatter["status"] == "active"
    assert doc.body.startswith("# My Source Note\n")
    assert "## Source\n\n- Type: local-file\n- Path: " in doc.body
    assert "## Content\n\n```text\nLine one\nLine two\n```" in doc.body
    assert HERMES_HUMAN_START in doc.body
    assert HERMES_HUMAN_END in doc.body


def test_ingest_local_file_is_idempotent_and_preserves_existing_metadata_and_human_notes(tmp_path):
    vault = tmp_path / "vault"
    initialize_vault(_config(vault))
    source_file = tmp_path / "note.txt"
    source_file.write_text("same content\n", encoding="utf-8")

    first = ingest_source(_config(vault), {"sourceType": "local-file", "inputPath": str(source_file)})
    page = vault / first.path
    text = page.read_text(encoding="utf-8")
    text = text.replace("id: source.note", "id: source.custom-existing")
    text = text.replace("ingestedAt:", "customField: keep-me\ningestedAt:")
    text = text.replace(f"{HERMES_HUMAN_START}\n## Human Notes\n\n{HERMES_HUMAN_END}", f"{HERMES_HUMAN_START}\n## Human Notes\n\nKeep this note.\n{HERMES_HUMAN_END}")
    page.write_text(text, encoding="utf-8")
    before = parse_wiki_markdown(page.read_text(encoding="utf-8"))

    second = ingest_source(_config(vault), {"sourceType": "local-file", "inputPath": str(source_file)})

    after = parse_wiki_markdown(page.read_text(encoding="utf-8"))
    assert second.created is False
    assert second.changed is False
    assert second.id == "source.custom-existing"
    assert after.frontmatter["id"] == "source.custom-existing"
    assert after.frontmatter["ingestedAt"] == before.frontmatter["ingestedAt"]
    assert after.frontmatter["customField"] == "keep-me"
    assert "Keep this note." in after.body


def test_ingest_local_file_rejects_binary_looking_file(tmp_path):
    vault = tmp_path / "vault"
    initialize_vault(_config(vault))
    source_file = tmp_path / "binary.dat"
    source_file.write_bytes(b"hello\x00world")

    with pytest.raises(ValueError, match="binary"):
        ingest_source(_config(vault), {"sourceType": "local-file", "inputPath": str(source_file)})

    assert not (vault / "sources" / "binary.md").exists()


def test_ingest_conversation_summary_requires_title_and_body_and_records_optional_metadata(tmp_path):
    vault = tmp_path / "vault"
    initialize_vault(_config(vault))

    with pytest.raises(ValueError, match="title"):
        ingest_source(_config(vault), {"sourceType": "conversation-summary", "body": "Summary"})
    with pytest.raises(ValueError, match="body"):
        ingest_source(_config(vault), {"sourceType": "conversation-summary", "title": "Chat"})

    result = ingest_source(
        _config(vault),
        {
            "sourceType": "conversation-summary",
            "title": "Planning Chat",
            "body": "We planned the ingest feature.",
            "sessionId": "sess-123",
            "messageRange": "12-20",
            "sourcePath": "transcripts/chat.md",
        },
    )

    assert result.path == "sources/planning-chat.md"
    assert result.id == "source.planning-chat"
    assert result.source_type == "conversation-summary"
    doc = parse_wiki_markdown((vault / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["sourceType"] == "conversation-summary"
    assert doc.frontmatter["sessionId"] == "sess-123"
    assert doc.frontmatter["messageRange"] == "12-20"
    assert doc.frontmatter["sourcePath"] == "transcripts/chat.md"
    assert "- Session: sess-123" in doc.body
    assert "- Message range: 12-20" in doc.body
    assert "```text\nWe planned the ingest feature.\n```" in doc.body


def test_ingest_generic_text_requires_title_and_body(tmp_path):
    vault = tmp_path / "vault"
    initialize_vault(_config(vault))

    result = ingest_source(_config(vault), {"sourceType": "text", "title": "Pasted Note", "body": "A pasted source."})

    assert result.path == "sources/pasted-note.md"
    assert result.bytes == len("A pasted source.".encode("utf-8"))
    doc = parse_wiki_markdown((vault / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["sourceType"] == "text"
    assert doc.frontmatter["title"] == "Pasted Note"
    assert "- Type: text" in doc.body
    assert "```text\nA pasted source.\n```" in doc.body
