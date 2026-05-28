from __future__ import annotations

import sqlite3
from dataclasses import replace

from hermes_memory_wiki.config import EmbeddingConfig, MemoryWikiConfig
from hermes_memory_wiki.embeddings import FakeEmbeddingProvider
from hermes_memory_wiki.vector_index import VectorIndex, reindex_vault
from hermes_memory_wiki.vault import METADATA_DIRECTORY, initialize_vault


class CountingFakeEmbeddingProvider(FakeEmbeddingProvider):
    def __init__(self, *, model: str = "fake-embedding", dimensions: int = 8) -> None:
        super().__init__(model=model, dimensions=dimensions)
        self.calls: list[list[str]] = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return super().embed_texts(texts)


class RaisingFakeEmbeddingProvider(CountingFakeEmbeddingProvider):
    def embed_texts(self, texts):
        self.calls.append(list(texts))
        raise RuntimeError("upstream timeout")


def _config(vault_path) -> MemoryWikiConfig:
    return MemoryWikiConfig(vault_path=vault_path)


def _index(config: MemoryWikiConfig) -> VectorIndex:
    return VectorIndex(config.vault_path / METADATA_DIRECTORY / "vector" / "index.sqlite")


def _write_page(root, relative_path: str, *, title: str, body: str = "Body text.", claim: str | None = None) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    claims = ""
    if claim is not None:
        claims = f"claims:\n  - id: claim-main\n    text: {claim}\n"
    path.write_text(
        f"---\ntitle: {title}\n{claims}---\n# {title}\n\n{body}\n",
        encoding="utf-8",
    )


def _embedded_ids(config: MemoryWikiConfig, provider: FakeEmbeddingProvider) -> list[str]:
    return [item.document.id for item in _index(config).load_embeddings(provider)]


def _index_rows(config: MemoryWikiConfig) -> dict[str, list[tuple]]:
    db_path = config.vault_path / METADATA_DIRECTORY / "vector" / "index.sqlite"
    with sqlite3.connect(db_path) as connection:
        return {
            "documents": connection.execute(
                "SELECT id, page_path, kind, title, doc_type, text, text_hash, metadata_json "
                "FROM documents ORDER BY id"
            ).fetchall(),
            "embeddings": connection.execute(
                "SELECT document_id, provider, model, dimensions, embedding_json, embedded_at, text_hash "
                "FROM embeddings ORDER BY document_id"
            ).fetchall(),
        }


def test_reindex_embeds_all_docs_on_first_run(tmp_path) -> None:
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/search.md", title="Search", claim="Search uses vectors.")
    provider = CountingFakeEmbeddingProvider(dimensions=6)

    result = reindex_vault(config, provider)

    assert result.embedded_count == 2
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert result.provider == "fake"
    assert result.model == "fake-embedding"
    assert result.dimensions == 6
    assert result.diagnostics == []
    assert len(provider.calls) == 1
    assert _embedded_ids(config, provider) == [
        "claim:concepts/search.md:claim-main",
        "page:concepts/search.md",
    ]


def test_reindex_second_run_skips_unchanged_docs(tmp_path) -> None:
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/search.md", title="Search", claim="Search uses vectors.")
    provider = CountingFakeEmbeddingProvider()
    reindex_vault(config, provider)

    result = reindex_vault(config, provider)

    assert result.embedded_count == 0
    assert result.skipped_count == 2
    assert result.deleted_count == 0
    assert result.diagnostics == []
    assert len(provider.calls) == 1


def test_force_reindex_reembeds_unchanged_docs(tmp_path) -> None:
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/search.md", title="Search", claim="Search uses vectors.")
    provider = CountingFakeEmbeddingProvider()
    reindex_vault(config, provider)

    result = reindex_vault(config, provider, force=True)

    assert result.embedded_count == 2
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert len(provider.calls) == 2
    assert len(provider.calls[-1]) == 2


def test_reindex_changed_page_text_reembeds_only_changed_docs(tmp_path) -> None:
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/search.md", title="Search", body="Original body.", claim="Stable claim.")
    _write_page(tmp_path, "concepts/other.md", title="Other", body="Other body.")
    provider = CountingFakeEmbeddingProvider()
    reindex_vault(config, provider)

    _write_page(tmp_path, "concepts/search.md", title="Search", body="Changed body.", claim="Stable claim.")
    result = reindex_vault(config, provider)

    assert result.embedded_count == 1
    assert result.skipped_count == 2
    assert result.deleted_count == 0
    assert len(provider.calls) == 2
    assert provider.calls[-1][0].startswith("Title: Search")
    assert "Changed body." in provider.calls[-1][0]


def test_reindex_counts_deleted_documents(tmp_path) -> None:
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/keep.md", title="Keep")
    _write_page(tmp_path, "concepts/remove.md", title="Remove")
    provider = CountingFakeEmbeddingProvider()
    reindex_vault(config, provider)

    (tmp_path / "concepts" / "remove.md").unlink()
    result = reindex_vault(config, provider)

    assert result.embedded_count == 0
    assert result.skipped_count == 1
    assert result.deleted_count == 1
    assert _embedded_ids(config, provider) == ["page:concepts/keep.md"]


def test_missing_api_key_returns_diagnostic_without_corrupting_index(tmp_path, monkeypatch) -> None:
    missing_env = "HERMES_MEMORY_WIKI_TEST_MISSING_OPENAI_API_KEY"
    monkeypatch.delenv(missing_env, raising=False)
    config = replace(
        _config(tmp_path),
        embeddings=EmbeddingConfig(api_key_env=missing_env),
    )
    initialize_vault(config)
    _write_page(tmp_path, "concepts/search.md", title="Search")
    previous_provider = CountingFakeEmbeddingProvider(model="previous", dimensions=4)
    previous_result = reindex_vault(config, previous_provider)
    assert previous_result.embedded_count == 1
    previous_embeddings = _index(config).load_embeddings(previous_provider)

    result = reindex_vault(config)

    assert result.embedded_count == 0
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536
    assert len(result.diagnostics) == 1
    assert missing_env in result.diagnostics[0]
    assert _index(config).load_embeddings(previous_provider) == previous_embeddings


def test_default_openai_reindex_reports_missing_openai_api_key_without_live_call(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/offline.md", title="Offline", body="offline body")

    result = reindex_vault(config)

    assert result.embedded_count == 0
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536
    assert result.diagnostics == [
        "Missing API key for OpenAI embeddings provider "
        "(provider=openai, model=text-embedding-3-small). "
        "Set environment variable OPENAI_API_KEY."
    ]
    assert not (tmp_path / METADATA_DIRECTORY / "vector" / "index.sqlite").exists()


def test_reindex_rejects_symlinked_vector_directory_without_writing_outside(tmp_path) -> None:
    config = _config(tmp_path / "vault")
    initialize_vault(config)
    _write_page(config.vault_path, "concepts/search.md", title="Search")
    outside = tmp_path / "outside-vector"
    outside.mkdir()
    vector_dir = config.vault_path / METADATA_DIRECTORY / "vector"
    vector_dir.rmdir()
    vector_dir.symlink_to(outside, target_is_directory=True)
    provider = CountingFakeEmbeddingProvider()

    result = reindex_vault(config, provider)

    assert result.embedded_count == 0
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert result.provider == "fake"
    assert result.model == "fake-embedding"
    assert result.dimensions == 8
    assert provider.calls == []
    assert not (outside / "index.sqlite").exists()
    assert len(result.diagnostics) == 1
    assert "symlink" in result.diagnostics[0]
    assert str(vector_dir) in result.diagnostics[0]


def test_reindex_provider_failure_does_not_delete_or_mutate_existing_index(tmp_path) -> None:
    config = _config(tmp_path)
    initialize_vault(config)
    _write_page(tmp_path, "concepts/changed.md", title="Changed", body="Original body.")
    _write_page(tmp_path, "concepts/removed.md", title="Removed", body="Removed body.")
    provider = CountingFakeEmbeddingProvider()
    previous_result = reindex_vault(config, provider)
    assert previous_result.embedded_count == 2
    before_rows = _index_rows(config)

    _write_page(tmp_path, "concepts/changed.md", title="Changed", body="Changed body.")
    (tmp_path / "concepts" / "removed.md").unlink()
    failing_provider = RaisingFakeEmbeddingProvider()
    result = reindex_vault(config, failing_provider)

    assert result.embedded_count == 0
    assert result.skipped_count == 0
    assert result.deleted_count == 1
    assert result.provider == "fake"
    assert result.model == "fake-embedding"
    assert result.dimensions == 8
    assert len(failing_provider.calls) == 1
    assert _index_rows(config) == before_rows
    assert result.diagnostics == ["RuntimeError: upstream timeout"]


def test_missing_api_key_does_not_delete_or_mutate_existing_index(tmp_path, monkeypatch) -> None:
    missing_env = "HERMES_MEMORY_WIKI_TEST_MISSING_OPENAI_API_KEY"
    monkeypatch.delenv(missing_env, raising=False)
    config = replace(
        _config(tmp_path),
        embeddings=EmbeddingConfig(api_key_env=missing_env),
    )
    initialize_vault(config)
    _write_page(tmp_path, "concepts/changed.md", title="Changed", body="Original body.")
    _write_page(tmp_path, "concepts/removed.md", title="Removed", body="Removed body.")
    provider = CountingFakeEmbeddingProvider(model="previous", dimensions=4)
    previous_result = reindex_vault(config, provider)
    assert previous_result.embedded_count == 2
    before_rows = _index_rows(config)

    _write_page(tmp_path, "concepts/changed.md", title="Changed", body="Changed body.")
    (tmp_path / "concepts" / "removed.md").unlink()
    result = reindex_vault(config)

    assert result.embedded_count == 0
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536
    assert len(result.diagnostics) == 1
    assert missing_env in result.diagnostics[0]
    assert _index_rows(config) == before_rows
