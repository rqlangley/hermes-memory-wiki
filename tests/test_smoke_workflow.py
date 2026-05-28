import json

from hermes_memory_wiki.vector_index import SearchDocument, VectorIndex
from scripts.smoke_fake_hermes import run_smoke_workflow


REQUIRED_STEPS = [
    "register",
    "wiki_init",
    "write_source_page",
    "write_entity_page",
    "write_concept_page",
    "wiki_apply",
    "wiki_compile",
    "wiki_lint",
    "wiki_reindex",
    "search_entity_name",
    "search_concept_name",
    "search_alias",
    "search_claim_text",
    "get_by_id",
    "get_by_path",
    "get_by_title",
    "get_by_alias",
    "assert_generated_outputs",
    "assert_no_structural_errors",
]


def test_fake_hermes_smoke_workflow_runs_offline(tmp_path):
    summary = run_smoke_workflow(vault_path=tmp_path / "vault")

    assert summary["ok"] is True
    assert summary["vaultPath"] == str(tmp_path / "vault")
    assert set(summary["registeredTools"]) >= {
        "wiki_init",
        "wiki_apply",
        "wiki_compile",
        "wiki_reindex",
        "wiki_search",
        "wiki_get",
        "wiki_lint",
    }
    assert set(summary["registeredSkills"]) >= {"wiki-maintainer", "wiki-authoring", "wiki-search"}

    steps = summary["steps"]
    assert [step["name"] for step in steps] == REQUIRED_STEPS
    for step in steps:
        assert step["ok"] is True
        if step["name"] != "register":
            assert isinstance(step["text"], str)
            assert step["text"]
            assert isinstance(step["details"], dict)

    for write_step_name, expected_path in {
        "write_source_page": "sources/openclaw-parity-notes.md",
        "write_entity_page": "entities/ada-lovelace.md",
        "write_concept_page": "concepts/analytical-engine.md",
    }.items():
        write_step = next(step for step in steps if step["name"] == write_step_name)
        assert write_step["path"] == expected_path

    apply_step = next(step for step in steps if step["name"] == "wiki_apply")
    assert apply_step["details"]["path"] == "syntheses/openclaw-parity-synthesis.md"

    compile_step = next(step for step in steps if step["name"] == "wiki_compile")
    page_counts = compile_step["details"]["pageCounts"]
    for kind in ("source", "entity", "concept", "synthesis"):
        assert page_counts[kind] >= 1
    assert compile_step["details"]["claimCount"] >= 3

    lint_step = next(step for step in steps if step["name"] == "wiki_lint")
    assert lint_step["details"]["errorCount"] == 0

    reindex_step = next(step for step in steps if step["name"] == "wiki_reindex")
    assert reindex_step["details"]["provider"] == "fake"
    assert reindex_step["details"]["embeddedCount"] > 0
    assert "offline smoke reindex stub used" in reindex_step["details"]["diagnostics"]

    expected_search_paths = {
        "search_entity_name": "entities/ada-lovelace.md",
        "search_concept_name": "concepts/analytical-engine.md",
        "search_alias": "entities/ada-lovelace.md",
        "search_claim_text": "concepts/analytical-engine.md",
    }
    for search_step_name, expected_path in expected_search_paths.items():
        search_step = next(step for step in steps if step["name"] == search_step_name)
        diagnostics = search_step["details"]["diagnostics"]
        assert diagnostics["requestedMode"] == "hybrid"
        assert diagnostics["effectiveMode"] in {"hybrid", "keyword"}
        assert "offline smoke search provider used" in diagnostics["messages"]
        assert any(result["path"] == expected_path for result in search_step["details"]["results"])

    expected_gets = {
        "get_by_id": ("entity.ada-lovelace", "entities/ada-lovelace.md"),
        "get_by_path": ("concepts/analytical-engine.md", "concepts/analytical-engine.md"),
        "get_by_title": ("OpenClaw Parity Synthesis", "syntheses/openclaw-parity-synthesis.md"),
        "get_by_alias": ("Enchantress of Numbers", "entities/ada-lovelace.md"),
    }
    for get_step_name, (lookup, expected_path) in expected_gets.items():
        get_step = next(step for step in steps if step["name"] == get_step_name)
        assert get_step["lookup"] == lookup
        assert get_step["details"]["found"] is True
        assert get_step["details"]["path"] == expected_path

    outputs_step = next(step for step in steps if step["name"] == "assert_generated_outputs")
    assert set(outputs_step["files"]) >= {
        "index.md",
        "entities/index.md",
        "concepts/index.md",
        "syntheses/index.md",
        "sources/index.md",
        "reports/open-questions.md",
        "reports/contradictions.md",
        "reports/low-confidence.md",
        "reports/claim-health.md",
        ".hermes-wiki/cache/agent-digest.json",
        ".hermes-wiki/cache/claims.jsonl",
        ".hermes-wiki/cache/lint-report.json",
    }

    structural_step = next(step for step in steps if step["name"] == "assert_no_structural_errors")
    assert structural_step["structuralErrors"] == []

    # The summary is meant for CLI/manual debugging and must remain JSON serializable.
    json.dumps(summary)


def test_fake_hermes_smoke_workflow_does_not_embed_with_existing_openai_index(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    index_path = vault_path / ".hermes-wiki" / "vector" / "index.sqlite"

    class ExistingOpenAIProvider:
        provider = "openai"
        model = "text-embedding-3-small"
        dimensions: int | None = 1536

        def embed_texts(self, texts):
            raise AssertionError("test fixture provider should not embed")

    provider = ExistingOpenAIProvider()
    document = SearchDocument(
        id="preexisting-openai-doc",
        page_path="syntheses/preexisting.md",
        kind="synthesis",
        title="Preexisting Vector Page",
        doc_type="page",
        text="offline smoke preexisting vector document",
        text_hash="preexisting-hash",
        metadata={},
    )
    index = VectorIndex(index_path)
    index.sync_documents_and_store_embeddings(
        provider,
        [document],
        [document],
        [[0.1] * 1536],
        embedded_at="2026-05-28T00:00:00+00:00",
    )

    class TripwireOpenAIProvider:
        provider = "openai"

        def __init__(self, embeddings_config, *, dimensions=None):
            self.model = embeddings_config.model
            self.dimensions = dimensions

        def embed_texts(self, texts):
            raise AssertionError("smoke workflow attempted live OpenAI/vector embedding")

    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-smoke-test-key")
    monkeypatch.setattr(
        "hermes_memory_wiki.vector_index.OpenAIEmbeddingProvider",
        TripwireOpenAIProvider,
    )

    summary = run_smoke_workflow(vault_path=vault_path)

    assert summary["ok"] is True
    reindex_step = next(step for step in summary["steps"] if step["name"] == "wiki_reindex")
    assert reindex_step["details"]["provider"] == "fake"
    assert reindex_step["details"]["embeddedCount"] > 0
    search_step = next(step for step in summary["steps"] if step["name"] == "search_entity_name")
    diagnostics = search_step["details"]["diagnostics"]
    assert diagnostics["requestedMode"] == "hybrid"
    assert diagnostics["effectiveMode"] in {"hybrid", "keyword"}
    assert "offline smoke search provider used" in diagnostics["messages"]
