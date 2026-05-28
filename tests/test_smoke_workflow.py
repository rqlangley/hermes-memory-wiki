import json

from hermes_memory_wiki.vector_index import SearchDocument, VectorIndex
from scripts.smoke_fake_hermes import run_smoke_workflow


REQUIRED_STEPS = [
    "register",
    "wiki_init",
    "wiki_apply",
    "wiki_compile",
    "wiki_reindex",
    "wiki_search",
    "wiki_get",
    "wiki_lint",
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

    reindex_step = next(step for step in steps if step["name"] == "wiki_reindex")
    assert reindex_step["details"]["provider"] == "fake"
    assert "offline smoke reindex stub used" in reindex_step["details"]["diagnostics"]

    search_step = next(step for step in steps if step["name"] == "wiki_search")
    diagnostics = search_step["details"]["diagnostics"]
    assert diagnostics["requestedMode"] == "hybrid"
    assert diagnostics["effectiveMode"] in {"hybrid", "keyword"}
    assert "offline smoke search provider used" in diagnostics["messages"]
    assert search_step["details"]["results"]

    get_step = next(step for step in steps if step["name"] == "wiki_get")
    assert get_step["details"]["found"] is True
    assert get_step["details"]["path"] == "syntheses/offline-smoke-synthesis.md"

    lint_step = next(step for step in steps if step["name"] == "wiki_lint")
    assert "issueCount" in lint_step["details"]

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
    search_step = next(step for step in summary["steps"] if step["name"] == "wiki_search")
    diagnostics = search_step["details"]["diagnostics"]
    assert diagnostics["requestedMode"] == "hybrid"
    assert diagnostics["effectiveMode"] == "keyword"
    assert diagnostics["vectorAvailable"] is False
    assert "offline smoke search provider used" in diagnostics["messages"]
