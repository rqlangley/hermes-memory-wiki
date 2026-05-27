from __future__ import annotations

import re

import pytest

from hermes_memory_wiki.apply import apply_mutation, normalize_mutation
from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.markdown import (
    HERMES_GENERATED_END,
    HERMES_GENERATED_START,
    HERMES_HUMAN_END,
    HERMES_HUMAN_START,
    parse_wiki_markdown,
)
from hermes_memory_wiki.vault import initialize_vault


def _config(root):
    return MemoryWikiConfig(vault_path=root)


def _base_raw(**overrides):
    raw = {
        "type": "create_synthesis",
        "title": "Project Alpha: Memory & RAG!",
        "body": "Project Alpha uses retrieval augmented memory.",
        "sourceIds": ["source.chat-1", "source.note-2"],
        "claims": [
            {
                "id": "claim.alpha-memory",
                "text": "Project Alpha uses memory wiki synthesis pages.",
                "status": "supported",
            }
        ],
        "status": "draft",
    }
    raw.update(overrides)
    return raw


@pytest.mark.parametrize("missing", ["title", "body", "sourceIds"])
def test_normalize_create_synthesis_requires_title_body_and_source_ids(missing):
    raw = _base_raw()
    raw.pop(missing)

    with pytest.raises(ValueError, match=missing):
        normalize_mutation(raw)


def test_create_synthesis_writes_deterministic_syntheses_path_and_default_id(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")

    mutation = normalize_mutation(_base_raw())
    result = apply_mutation(config, mutation)

    assert result.created is True
    assert result.path == "syntheses/project-alpha-memory-rag.md"
    assert result.id == "synthesis.project-alpha-memory-rag"
    assert (config.vault_path / result.path).is_file()

    doc = parse_wiki_markdown((config.vault_path / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["id"] == "synthesis.project-alpha-memory-rag"
    assert doc.frontmatter["title"] == "Project Alpha: Memory & RAG!"
    assert doc.frontmatter["pageType"] == "synthesis"


def test_create_synthesis_frontmatter_contains_claims_source_ids_status_and_updated_at(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")

    result = apply_mutation(config, normalize_mutation(_base_raw()))

    doc = parse_wiki_markdown((config.vault_path / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["sourceIds"] == ["source.chat-1", "source.note-2"]
    assert doc.frontmatter["claims"] == [
        {
            "id": "claim.alpha-memory",
            "text": "Project Alpha uses memory wiki synthesis pages.",
            "status": "supported",
        }
    ]
    assert doc.frontmatter["status"] == "draft"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", doc.frontmatter["updatedAt"])


def test_create_synthesis_writes_generated_summary_and_human_notes_blocks(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")

    result = apply_mutation(config, normalize_mutation(_base_raw()))

    body = parse_wiki_markdown((config.vault_path / result.path).read_text(encoding="utf-8")).body
    assert body.startswith("# Project Alpha: Memory & RAG!\n")
    assert HERMES_GENERATED_START in body
    assert "## Summary" in body
    assert "Project Alpha uses retrieval augmented memory." in body
    assert HERMES_GENERATED_END in body
    assert f"{HERMES_HUMAN_START}\n## Human Notes\n\n{HERMES_HUMAN_END}" in body


def test_create_synthesis_preserves_human_notes_on_update(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    first = apply_mutation(config, normalize_mutation(_base_raw()))
    page_path = config.vault_path / first.path
    original = page_path.read_text(encoding="utf-8")
    page_path.write_text(
        original.replace(
            f"{HERMES_HUMAN_START}\n## Human Notes\n\n{HERMES_HUMAN_END}",
            f"{HERMES_HUMAN_START}\n## Human Notes\n\nKeep this hand-written note.\n{HERMES_HUMAN_END}",
        ),
        encoding="utf-8",
    )

    updated = apply_mutation(
        config,
        normalize_mutation(
            _base_raw(
                body="Updated generated summary.",
                status="published",
                claims=[{"text": "Updated claim."}],
            )
        ),
    )

    assert updated.created is False
    assert updated.path == first.path
    doc = parse_wiki_markdown(page_path.read_text(encoding="utf-8"))
    assert "Updated generated summary." in doc.body
    assert "Project Alpha uses retrieval augmented memory." not in doc.body
    assert "Keep this hand-written note." in doc.body
    assert doc.frontmatter["status"] == "published"


def test_create_synthesis_rejects_explicit_path_outside_vault(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))

    mutation = normalize_mutation(_base_raw(path="../outside.md"))

    with pytest.raises(ValueError, match="outside vault"):
        apply_mutation(_config(tmp_path / "vault"), mutation)
