from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, cast

import pytest

from hermes_memory_wiki.config import EmbeddingConfig, MemoryWikiConfig
from hermes_memory_wiki.vector_index import (
    SearchDocument,
    VectorIndex,
    cosine_similarity,
    vector_search,
)
from hermes_memory_wiki.vault import METADATA_DIRECTORY


@dataclass
class MappingEmbeddingProvider:
    vectors: dict[str, list[float]]
    provider: str = "fake"
    model: str = "fake-search"
    dimensions: int | None = 3

    def __post_init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self.vectors[text] for text in texts]


def _config(vault_path) -> MemoryWikiConfig:
    return MemoryWikiConfig(vault_path=vault_path)


def _index(config: MemoryWikiConfig) -> VectorIndex:
    return VectorIndex(config.vault_path / METADATA_DIRECTORY / "vector" / "index.sqlite")


def _diagnostics(results: object) -> list[str]:
    return cast(list[str], getattr(results, "diagnostics"))


def _doc(
    doc_id: str,
    *,
    doc_type: str = "page",
    page_path: str = "topics/vector.md",
    title: str = "Vector Search",
    kind: str = "concept",
    text: str | None = None,
    metadata: dict | None = None,
) -> SearchDocument:
    return SearchDocument(
        id=doc_id,
        page_path=page_path,
        kind=kind,
        title=title,
        doc_type=doc_type,  # type: ignore[arg-type]
        text=text or f"Title: {title}\nBody:\nVector search ranks {doc_id}.",
        text_hash=f"hash-{doc_id}",
        metadata=metadata or {"page_id": "concept:vector"},
    )


def test_cosine_similarity_ranks_expected_fake_vectors() -> None:
    query = [1.0, 0.0, 0.0]
    candidates = {
        "best": [0.9, 0.1, 0.0],
        "middle": [0.5, 0.5, 0.0],
        "worst": [-1.0, 0.0, 0.0],
    }

    ranked = sorted(candidates, key=lambda key: cosine_similarity(query, candidates[key]), reverse=True)

    assert ranked == ["best", "middle", "worst"]
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_vector_search_embeds_query_once(tmp_path) -> None:
    config = _config(tmp_path)
    provider = MappingEmbeddingProvider({"search query": [1.0, 0.0, 0.0]})
    docs = [_doc("page:one"), _doc("page:two")]
    index = _index(config)
    index.upsert_documents(docs)
    index.store_embeddings(provider, docs, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

    results = vector_search(config, "search query", provider=provider, max_results=1)

    assert len(results) == 1
    assert provider.calls == [["search query"]]


def test_vector_search_returns_page_and_claim_results_with_snippets_and_metadata(tmp_path) -> None:
    config = _config(tmp_path)
    provider = MappingEmbeddingProvider({"routing question": [1.0, 0.0, 0.0]})
    page_doc = _doc(
        "page:topics/routing.md",
        page_path="topics/routing.md",
        title="Routing",
        text="Title: Routing\nBody:\nUse vector search for routing questions.",
        metadata={"id": "concept:routing", "sourceIds": ["source-a"], "claimCount": 1},
    )
    claim_doc = _doc(
        "claim:topics/routing.md:claim-route",
        doc_type="claim",
        page_path="topics/routing.md",
        title="Routing",
        text="Page: Routing\nClaim ID: claim-route\nClaim: Route questions by semantic similarity.\nStatus: active",
        metadata={"id": "concept:routing", "claimId": "claim-route", "status": "active", "claimConfidence": 0.8},
    )
    weak_doc = _doc("page:topics/weak.md", page_path="topics/weak.md", title="Weak")
    index = _index(config)
    index.upsert_documents([page_doc, claim_doc, weak_doc])
    index.store_embeddings(
        provider,
        [page_doc, claim_doc, weak_doc],
        [[0.95, 0.05, 0.0], [0.9, 0.1, 0.0], [-1.0, 0.0, 0.0]],
    )

    results = vector_search(config, "routing question", provider=provider, max_results=2, mode="route-question")

    assert [result.path for result in results] == ["topics/routing.md", "topics/routing.md"]
    assert [result.matched_claim_id for result in results] == [None, "claim-route"]
    assert results[0].corpus == "wiki"
    assert results[0].title == "Routing"
    assert results[0].kind == "concept"
    assert results[0].search_mode == "route-question"
    assert "Use vector search" in results[0].snippet
    assert results[0].metadata["search_type"] == "vector"
    assert results[0].metadata["document_id"] == "page:topics/routing.md"
    assert results[0].metadata["id"] == "concept:routing"
    assert "Route questions by semantic similarity" in results[1].snippet
    assert results[1].metadata["claimId"] == "claim-route"


def test_vector_search_missing_index_preserves_diagnostics_without_embedding_query(tmp_path) -> None:
    provider = MappingEmbeddingProvider({"anything": [1.0, 0.0, 0.0]})

    results = vector_search(_config(tmp_path / "missing"), "anything", provider=provider)

    assert results == []
    assert isinstance(results, list)
    assert any("Vector index not found" in diagnostic for diagnostic in _diagnostics(results))
    assert provider.calls == []


def test_vector_search_empty_initialized_index_preserves_diagnostics_without_embedding_query(tmp_path) -> None:
    config = _config(tmp_path)
    provider = MappingEmbeddingProvider({"anything": [1.0, 0.0, 0.0]})
    _index(config)

    results = vector_search(config, "anything", provider=provider)

    assert results == []
    assert isinstance(results, list)
    assert any("No vector embeddings available" in diagnostic for diagnostic in _diagnostics(results))
    assert provider.calls == []


def test_vector_search_provider_unavailable_preserves_diagnostics_without_network(tmp_path) -> None:
    config = MemoryWikiConfig(
        vault_path=tmp_path,
        embeddings=EmbeddingConfig(enabled=False),
    )

    results = vector_search(config, "anything")

    assert results == []
    assert isinstance(results, list)
    assert any("Embeddings are disabled" in diagnostic for diagnostic in _diagnostics(results))


def test_vector_search_success_results_expose_empty_diagnostics(tmp_path) -> None:
    config = _config(tmp_path)
    provider = MappingEmbeddingProvider({"search query": [1.0, 0.0, 0.0]})
    doc = _doc("page:one")
    index = _index(config)
    index.upsert_documents([doc])
    index.store_embeddings(provider, [doc], [[1.0, 0.0, 0.0]])

    results = vector_search(config, "search query", provider=provider)

    assert len(results) == 1
    assert _diagnostics(results) == []


def test_vector_search_diagnoses_dimension_mismatch(tmp_path) -> None:
    config = _config(tmp_path)
    provider = MappingEmbeddingProvider({"bad query": [1.0, 0.0]}, dimensions=2)
    doc = _doc("page:bad")
    index = _index(config)
    index.upsert_documents([doc])
    index.store_embeddings(MappingEmbeddingProvider({}, dimensions=3), [doc], [[1.0, 0.0, 0.0]])

    with pytest.raises(ValueError, match="dimension mismatch.*query.*2.*page:bad.*3"):
        vector_search(config, "bad query", provider=provider)
