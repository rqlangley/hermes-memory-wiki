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
        "op": "create_synthesis",
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


def test_normalize_create_synthesis_accepts_op_discriminator():
    mutation = normalize_mutation(_base_raw())

    assert mutation.type == "create_synthesis"


def test_normalize_create_synthesis_rejects_missing_op():
    raw = _base_raw()
    raw.pop("op")

    with pytest.raises(ValueError, match="op"):
        normalize_mutation(raw)


def test_normalize_create_synthesis_rejects_unsupported_op():
    with pytest.raises(ValueError, match="unsupported mutation op: delete_page"):
        normalize_mutation(_base_raw(op="delete_page"))


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


def test_create_synthesis_defaults_status_to_active(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    raw = _base_raw()
    raw.pop("status")

    result = apply_mutation(config, normalize_mutation(raw))

    doc = parse_wiki_markdown((config.vault_path / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["status"] == "active"


def test_create_synthesis_frontmatter_contains_questions_contradictions_and_confidence(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")

    result = apply_mutation(
        config,
        normalize_mutation(
            _base_raw(
                questions=["How will Project Alpha validate memory quality?"],
                contradictions=["One source says RAG is not in scope."],
                confidence=0.72,
            )
        ),
    )

    doc = parse_wiki_markdown((config.vault_path / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["questions"] == ["How will Project Alpha validate memory quality?"]
    assert doc.frontmatter["contradictions"] == ["One source says RAG is not in scope."]
    assert doc.frontmatter["confidence"] == 0.72


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True, "0.72"])
def test_normalize_create_synthesis_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError, match="confidence"):
        normalize_mutation(_base_raw(confidence=confidence))


@pytest.mark.parametrize("confidence", [0, 1, 0.72])
def test_normalize_create_synthesis_accepts_valid_confidence(confidence):
    mutation = normalize_mutation(_base_raw(confidence=confidence))

    assert mutation.confidence == confidence


def test_create_synthesis_ignores_public_path_and_id_overrides(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")

    result = apply_mutation(config, normalize_mutation(_base_raw(path="syntheses/custom.md", id="custom.id")))

    assert result.path == "syntheses/project-alpha-memory-rag.md"
    assert result.id == "synthesis.project-alpha-memory-rag"
    assert not (config.vault_path / "syntheses" / "custom.md").exists()


def test_create_synthesis_preserves_existing_id_when_overwriting(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    first = apply_mutation(config, normalize_mutation(_base_raw()))
    page_path = config.vault_path / first.path
    text = page_path.read_text(encoding="utf-8").replace("id: synthesis.project-alpha-memory-rag", "id: synthesis.existing")
    page_path.write_text(text, encoding="utf-8")

    result = apply_mutation(config, normalize_mutation(_base_raw(body="Updated.")))

    assert result.created is False
    assert result.id == "synthesis.existing"
    doc = parse_wiki_markdown(page_path.read_text(encoding="utf-8"))
    assert doc.frontmatter["id"] == "synthesis.existing"


@pytest.mark.parametrize(
    "claims,match",
    [
        ([{"id": "missing-text"}], "claim text is required"),
        ([{"text": "Bad confidence", "confidence": 2}], "claim confidence"),
        ([{"text": "Bad evidence", "evidence": [{"kind": 42}]}], "evidence kind"),
        ([{"text": "Bad evidence", "evidence": [{"sourceId": 42}]}], "evidence sourceId"),
        ([{"text": "Bad evidence", "evidence": [{"lines": [1, 2]}]}], "evidence lines"),
    ],
)
def test_normalize_create_synthesis_rejects_malformed_claims_and_evidence(claims, match):
    with pytest.raises(ValueError, match=match):
        normalize_mutation(_base_raw(claims=claims))


def test_normalize_create_synthesis_accepts_structured_claim_evidence_fields():
    mutation = normalize_mutation(
        _base_raw(
            claims=[
                {
                    "id": "claim.one",
                    "text": "A supported claim.",
                    "confidence": 0.5,
                    "evidence": [{"kind": "source", "sourceId": "source.one", "lines": "1-3"}],
                }
            ]
        )
    )

    assert mutation.claims[0]["evidence"][0] == {"kind": "source", "sourceId": "source.one", "lines": "1-3"}


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


def _update_raw(**overrides):
    raw = {
        "op": "update_metadata",
        "lookup": "synthesis.project-alpha-memory-rag",
        "sourceIds": [" source.chat-3 ", "source.note-4"],
        "claims": [{"id": "claim.updated", "text": "Updated metadata claim."}],
        "status": "published",
        "confidence": 0.9,
    }
    raw.update(overrides)
    return raw


def _create_page(config):
    return apply_mutation(config, normalize_mutation(_base_raw(confidence=0.4)))


def test_normalize_update_metadata_requires_lookup():
    raw = _update_raw()
    raw.pop("lookup")

    with pytest.raises(ValueError, match="lookup"):
        normalize_mutation(raw)


def test_update_metadata_missing_page_raises_clear_error(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    mutation = normalize_mutation(_update_raw(lookup="missing.page"))

    with pytest.raises(FileNotFoundError, match=r"wiki page not found.*missing\.page"):
        apply_mutation(config, mutation)


def test_update_metadata_replaces_normalized_source_ids(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)

    result = apply_mutation(
        config,
        normalize_mutation(_update_raw(sourceIds=[" source.new ", "", 42])),
    )

    assert result.created is False
    assert result.path == created.path
    doc = parse_wiki_markdown((config.vault_path / created.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["sourceIds"] == ["source.new", "42"]


def test_update_metadata_empty_claims_removes_claims_field(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)

    apply_mutation(config, normalize_mutation(_update_raw(claims=[])))

    doc = parse_wiki_markdown((config.vault_path / created.path).read_text(encoding="utf-8"))
    assert "claims" not in doc.frontmatter


def test_update_metadata_confidence_null_removes_confidence(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)

    apply_mutation(config, normalize_mutation(_update_raw(confidence=None)))

    doc = parse_wiki_markdown((config.vault_path / created.path).read_text(encoding="utf-8"))
    assert "confidence" not in doc.frontmatter

def test_update_metadata_preserves_body(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)
    page_path = config.vault_path / created.path
    original_body = parse_wiki_markdown(page_path.read_text(encoding="utf-8")).body

    apply_mutation(config, normalize_mutation(_update_raw()))

    updated_body = parse_wiki_markdown(page_path.read_text(encoding="utf-8")).body
    assert updated_body == original_body


def test_update_metadata_ignores_unsupported_title_changes(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)

    apply_mutation(config, normalize_mutation(_update_raw(title="Renamed Synthesis")))

    doc = parse_wiki_markdown((config.vault_path / created.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["title"] == "Project Alpha: Memory & RAG!"


def test_update_metadata_changes_updated_at(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)
    page_path = config.vault_path / created.path
    page_path.write_text(
        re.sub(
            r"updatedAt: .+",
            "updatedAt: 2000-01-01T00:00:00+00:00",
            page_path.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )

    apply_mutation(config, normalize_mutation(_update_raw()))

    doc = parse_wiki_markdown(page_path.read_text(encoding="utf-8"))
    assert doc.frontmatter["updatedAt"] != "2000-01-01T00:00:00+00:00"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", doc.frontmatter["updatedAt"])


def test_update_metadata_accepts_explicit_updated_at(tmp_path):
    initialize_vault(_config(tmp_path / "vault"))
    config = _config(tmp_path / "vault")
    created = _create_page(config)
    page_path = config.vault_path / created.path

    apply_mutation(config, normalize_mutation(_update_raw(updatedAt="2026-05-28T12:00:00Z")))

    doc = parse_wiki_markdown(page_path.read_text(encoding="utf-8"))
    assert doc.frontmatter["updatedAt"] == "2026-05-28T12:00:00Z"
