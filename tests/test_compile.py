from __future__ import annotations

import json

import pytest

from hermes_memory_wiki.compile import compile_vault
from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.vault import initialize_vault


def _config(root):
    return MemoryWikiConfig(vault_path=root)


def _write(root, relative_path, content):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _page(
    *,
    page_id,
    title,
    page_type,
    entity_type=None,
    claims=(),
    questions=(),
    contradictions=(),
    confidence=None,
):
    entity_type_line = f"entityType: {entity_type}\n" if entity_type else ""
    confidence_line = f"confidence: {confidence}\n" if confidence is not None else ""
    question_lines = ""
    if questions:
        question_lines = "questions:\n" + "".join(f"  - {item}\n" for item in questions)
    contradiction_lines = ""
    if contradictions:
        contradiction_lines = "contradictions:\n" + "".join(f"  - {item}\n" for item in contradictions)
    claim_lines = ""
    if claims:
        claim_lines = "claims:\n"
        for claim in claims:
            if len(claim) == 2:
                claim_id, text = claim
                claim_lines += f"  - id: {claim_id}\n    text: {text}\n"
            else:
                claim_id, text, status, claim_confidence, source_id, evidence_path = claim
                claim_lines += (
                    f"  - id: {claim_id}\n"
                    f"    text: {text}\n"
                    f"    status: {status}\n"
                    f"    confidence: {claim_confidence}\n"
                    f"    evidence:\n"
                    f"      - kind: source\n"
                    f"        sourceId: {source_id}\n"
                    f"        path: {evidence_path}\n"
                    f"        lines: 1-3\n"
                    f"        weight: 1\n"
                    f"        confidence: 0.9\n"
                )
    return f"""---
id: {page_id}
title: {title}
pageType: {page_type}
{entity_type_line}{confidence_line}{question_lines}{contradiction_lines}{claim_lines}---
# {title}

Body for {title}.
"""


def _page_with_anonymous_claim(*, page_id, title, page_type, claim_text, entity_type=None):
    entity_type_line = f"entityType: {entity_type}\n" if entity_type else ""
    return f"""---
id: {page_id}
title: {title}
pageType: {page_type}
{entity_type_line}
claims:
  - text: {claim_text}
---
# {title}

Body for {title}.
"""


def _seed_vault(root):
    initialize_vault(_config(root))
    _write(
        root,
        "sources/ada-notes.md",
        _page(page_id="source.ada-notes", title="Ada Notes", page_type="source"),
    )
    _write(
        root,
        "entities/ada.md",
        _page(
            page_id="entity.ada",
            title="Ada Lovelace",
            page_type="entity",
            entity_type="person",
            claims=(("claim:ada-1", "Ada wrote notes.", "active", 0.8, "source.ada-notes", "sources/ada-notes.md"),),
            questions=("Which notes should be canonical?",),
        ),
    )
    _write(
        root,
        "entities/babbage.md",
        _page(
            page_id="entity.babbage",
            title="Charles Babbage",
            page_type="entity",
            entity_type="person",
        ),
    )
    _write(
        root,
        "concepts/engine.md",
        _page(
            page_id="concept:engine",
            title="Analytical Engine",
            page_type="concept",
            claims=(("claim:engine-1", "The engine was programmable."),),
            contradictions=("Some sources call the design non-programmable.",),
            confidence=0.4,
        ),
    )
    _write(
        root,
        "syntheses/programming.md",
        _page(page_id="synthesis.programming", title="Programming Synthesis", page_type="synthesis"),
    )


def _jsonl(path):
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _compile_log_entries(root):
    return [
        json.loads(line)
        for line in (root / ".hermes-wiki" / "log.jsonl").read_text(encoding="utf-8").splitlines()
        if line and json.loads(line).get("event") == "compile"
    ]


def test_root_index_includes_page_counts(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    result = compile_vault(_config(root))

    index = (root / "index.md").read_text(encoding="utf-8")
    assert result.vault_root == root
    assert result.page_counts == {"concept": 1, "entity": 2, "report": 4, "source": 1, "synthesis": 1}
    assert result.claim_count == 2
    assert "# Wiki Index" in index
    assert "- Total pages: 9" in index
    assert "- Total claims: 2" in index
    assert "- Concepts: 1" in index
    assert "- Entities: 2" in index
    assert "- Reports: 4" in index
    assert "- Sources: 1" in index
    assert "- Syntheses: 1" in index


def test_directory_indexes_list_pages_by_kind(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    entities_index = (root / "entities" / "index.md").read_text(encoding="utf-8")
    concepts_index = (root / "concepts" / "index.md").read_text(encoding="utf-8")
    assert (root / "sources" / "index.md").exists()
    assert (root / "syntheses" / "index.md").exists()
    assert (root / "reports" / "index.md").exists()
    assert "[Ada Lovelace](ada.md)" in entities_index
    assert "[Charles Babbage](babbage.md)" in entities_index
    assert "[Analytical Engine](engine.md)" in concepts_index


def test_compile_generates_openclaw_like_reports(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    expected = {
        "reports/open-questions.md": ("report.open-questions", "Open Questions", "Which notes should be canonical?"),
        "reports/contradictions.md": ("report.contradictions", "Contradictions", "Some sources call the design non-programmable."),
        "reports/low-confidence.md": ("report.low-confidence", "Low Confidence", "confidence 0.40"),
        "reports/claim-health.md": ("report.claim-health", "Claim Health", "Claims missing evidence: 1"),
    }
    for relative_path, (page_id, title, expected_text) in expected.items():
        text = (root / relative_path).read_text(encoding="utf-8")
        assert "pageType: report" in text
        assert f"id: {page_id}" in text
        assert f"title: {title}" in text
        assert "<!-- hermes:wiki:" in text
        assert expected_text in text


def test_agent_digest_json_includes_pages_and_claim_counts(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    digest = json.loads((root / ".hermes-wiki" / "cache" / "agent-digest.json").read_text(encoding="utf-8"))
    assert digest["pageCounts"] == {"concept": 1, "entity": 2, "report": 4, "source": 1, "synthesis": 1}
    assert digest["claimCount"] == 2
    pages = {page["path"]: page for page in digest["pages"]}
    assert pages["entities/ada.md"]["claimCount"] == 1
    assert pages["entities/ada.md"]["questions"] == ["Which notes should be canonical?"]
    assert pages["entities/ada.md"]["entityType"] == "person"
    assert pages["concepts/engine.md"]["confidence"] == 0.4
    assert digest["claimHealth"]["missingEvidence"] == 1


def test_claims_jsonl_contains_one_claim_per_line(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    claims = _jsonl(root / ".hermes-wiki" / "cache" / "claims.jsonl")
    assert claims == [
        {
            "pagePath": "concepts/engine.md",
            "pageId": "concept:engine",
            "pageTitle": "Analytical Engine",
            "claimId": "claim:engine-1",
            "claimDocumentId": "claim:concepts/engine.md:claim:engine-1",
            "text": "The engine was programmable.",
            "status": None,
            "confidence": None,
            "evidence": [],
        },
        {
            "pagePath": "entities/ada.md",
            "pageId": "entity.ada",
            "pageTitle": "Ada Lovelace",
            "claimId": "claim:ada-1",
            "claimDocumentId": "claim:entities/ada.md:claim:ada-1",
            "text": "Ada wrote notes.",
            "status": "active",
            "confidence": 0.8,
            "evidence": [
                {
                    "kind": "source",
                    "sourceId": "source.ada-notes",
                    "path": "sources/ada-notes.md",
                    "lines": ["1-3"],
                    "weight": 1,
                    "confidence": 0.9,
                    "privacyTier": None,
                    "updatedAt": None,
                    "note": None,
                    "text": None,
                }
            ],
        },
    ]


def test_generated_blocks_are_replaced_without_overwriting_human_notes(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)
    _write(
        root,
        "reports/open-questions.md",
        """---
id: wrong
title: Old
pageType: concept
---
# Old

<!-- hermes:wiki:open-questions:start -->
stale generated content
<!-- hermes:wiki:open-questions:end -->

## Human Notes

Keep this analyst note.
""",
    )

    compile_vault(_config(root))

    report = (root / "reports" / "open-questions.md").read_text(encoding="utf-8")
    assert "id: report.open-questions" in report
    assert "pageType: report" in report
    assert "stale generated content" not in report
    assert "Which notes should be canonical?" in report
    assert "Keep this analyst note." in report


def test_search_docs_jsonl_contains_page_and_claim_documents(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    docs = _jsonl(root / ".hermes-wiki" / "cache" / "search-docs.jsonl")
    assert [doc["id"] for doc in docs] == [
        "page:concepts/engine.md",
        "claim:concepts/engine.md:claim:engine-1",
        "page:entities/ada.md",
        "claim:entities/ada.md:claim:ada-1",
        "page:entities/babbage.md",
        "page:reports/claim-health.md",
        "page:reports/contradictions.md",
        "page:reports/low-confidence.md",
        "page:reports/open-questions.md",
        "page:sources/ada-notes.md",
        "page:syntheses/programming.md",
    ]
    assert {doc["docType"] for doc in docs} == {"page", "claim"}
    assert all("textHash" in doc for doc in docs)


def test_compile_is_idempotent_if_nothing_changed(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)
    first = compile_vault(_config(root))
    tracked = [root / "index.md", root / "entities" / "index.md", root / ".hermes-wiki" / "cache" / "agent-digest.json"]
    first_contents = {path: path.read_text(encoding="utf-8") for path in tracked}
    first_log_count = len(_compile_log_entries(root))

    second = compile_vault(_config(root))

    assert first.updated_files
    assert second.updated_files == []
    assert {path: path.read_text(encoding="utf-8") for path in tracked} == first_contents
    assert len(_compile_log_entries(root)) == first_log_count


def test_compile_appends_log_when_files_update(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)
    compile_vault(_config(root))
    first_entries = _compile_log_entries(root)
    _write(root, "reports/weekly.md", _page(page_id="report:weekly", title="Weekly Report", page_type="report"))

    result = compile_vault(_config(root))

    entries = _compile_log_entries(root)
    assert len(entries) == len(first_entries) + 1
    assert entries[-1]["event"] == "compile"
    assert "reports/index.md" in entries[-1]["updatedFiles"]
    assert ".hermes-wiki/cache/agent-digest.json" in entries[-1]["updatedFiles"]
    assert root / "reports" / "index.md" in result.updated_files


def test_compile_rejects_root_index_symlink_without_overwriting_target(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)
    target = tmp_path / "outside-index.md"
    target.write_text("outside content", encoding="utf-8")
    (root / "index.md").unlink()
    (root / "index.md").symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        compile_vault(_config(root))

    assert target.read_text(encoding="utf-8") == "outside content"


def test_compile_rejects_cache_directory_symlink_without_overwriting_target(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)
    outside_cache = tmp_path / "outside-cache"
    outside_cache.mkdir()
    (root / ".hermes-wiki" / "cache").rmdir()
    (root / ".hermes-wiki" / "cache").symlink_to(outside_cache, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        compile_vault(_config(root))

    assert list(outside_cache.iterdir()) == []


def test_compile_rejects_log_symlink_without_overwriting_target(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)
    target = tmp_path / "outside-log.jsonl"
    target.write_text("outside log\n", encoding="utf-8")
    log_path = root / ".hermes-wiki" / "log.jsonl"
    log_path.unlink()
    log_path.symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        compile_vault(_config(root))

    assert target.read_text(encoding="utf-8") == "outside log\n"


def test_anonymous_claims_correlate_with_search_documents(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "entities/anonymous.md",
        _page_with_anonymous_claim(
            page_id="entity.anonymous",
            title="Anonymous Person",
            page_type="entity",
            entity_type="person",
            claim_text="This claim has no explicit ID.",
        ),
    )

    compile_vault(_config(root))

    claims = _jsonl(root / ".hermes-wiki" / "cache" / "claims.jsonl")
    docs = _jsonl(root / ".hermes-wiki" / "cache" / "search-docs.jsonl")
    claim_doc = next(doc for doc in docs if doc["docType"] == "claim")
    assert len(claims) == 1
    assert claims[0]["claimId"] != "claim-0"
    assert claims[0]["claimDocumentId"] == claim_doc["id"]
    assert claims[0]["claimId"] in claim_doc["text"]
    assert claim_doc["metadata"]["claim_ordinal"] == 0
