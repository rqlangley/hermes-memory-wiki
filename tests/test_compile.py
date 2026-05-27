from __future__ import annotations

import json

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


def _page(*, page_id, title, page_type, claims=()):
    claim_lines = ""
    if claims:
        claim_lines = "claims:\n"
        for claim_id, text in claims:
            claim_lines += f"  - id: {claim_id}\n    text: {text}\n"
    return f"""---
id: {page_id}
title: {title}
pageType: {page_type}
{claim_lines}---
# {title}

Body for {title}.
"""


def _seed_vault(root):
    initialize_vault(_config(root))
    _write(
        root,
        "entities/ada.md",
        _page(
            page_id="person:ada",
            title="Ada Lovelace",
            page_type="person",
            claims=(("claim:ada-1", "Ada wrote notes."),),
        ),
    )
    _write(
        root,
        "entities/babbage.md",
        _page(
            page_id="person:babbage",
            title="Charles Babbage",
            page_type="person",
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
        ),
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
    assert result.page_counts == {"concept": 1, "person": 2}
    assert result.claim_count == 2
    assert "# Memory Wiki Index" in index
    assert "- Total pages: 3" in index
    assert "- Total claims: 2" in index
    assert "- concept: 1" in index
    assert "- person: 2" in index


def test_directory_indexes_list_pages_by_kind(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    entities_index = (root / "entities" / "index.md").read_text(encoding="utf-8")
    concepts_index = (root / "concepts" / "index.md").read_text(encoding="utf-8")
    assert "## person" in entities_index
    assert "- [Ada Lovelace](ada.md) — person:ada" in entities_index
    assert "- [Charles Babbage](babbage.md) — person:babbage" in entities_index
    assert "## concept" in concepts_index
    assert "- [Analytical Engine](engine.md) — concept:engine" in concepts_index


def test_agent_digest_json_includes_pages_and_claim_counts(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    digest = json.loads((root / ".hermes-wiki" / "cache" / "agent-digest.json").read_text(encoding="utf-8"))
    assert digest["pageCounts"] == {"concept": 1, "person": 2}
    assert digest["claimCount"] == 2
    assert digest["pages"] == [
        {"path": "concepts/engine.md", "id": "concept:engine", "title": "Analytical Engine", "kind": "concept", "claimCount": 1},
        {"path": "entities/ada.md", "id": "person:ada", "title": "Ada Lovelace", "kind": "person", "claimCount": 1},
        {"path": "entities/babbage.md", "id": "person:babbage", "title": "Charles Babbage", "kind": "person", "claimCount": 0},
    ]


def test_claims_jsonl_contains_one_claim_per_line(tmp_path):
    root = tmp_path / "vault"
    _seed_vault(root)

    compile_vault(_config(root))

    claims = _jsonl(root / ".hermes-wiki" / "cache" / "claims.jsonl")
    assert claims == [
        {"pagePath": "concepts/engine.md", "pageId": "concept:engine", "pageTitle": "Analytical Engine", "claimId": "claim:engine-1", "text": "The engine was programmable.", "status": None, "confidence": None},
        {"pagePath": "entities/ada.md", "pageId": "person:ada", "pageTitle": "Ada Lovelace", "claimId": "claim:ada-1", "text": "Ada wrote notes.", "status": None, "confidence": None},
    ]


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
