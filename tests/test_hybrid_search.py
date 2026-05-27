from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from hermes_memory_wiki.config import MemoryWikiConfig, SearchConfig
from hermes_memory_wiki.hybrid_search import search_wiki
from hermes_memory_wiki.vector_index import SearchDocument, VectorIndex
from hermes_memory_wiki.vault import METADATA_DIRECTORY


@dataclass
class MappingEmbeddingProvider:
    vectors: dict[str, list[float]]
    provider: str = "fake"
    model: str = "fake-hybrid"
    dimensions: int | None = 3

    def __post_init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self.vectors[text] for text in texts]


def _config(vault_path, *, search: SearchConfig | None = None) -> MemoryWikiConfig:
    return MemoryWikiConfig(vault_path=vault_path, search=search or SearchConfig())


def _write_page(
    root,
    relative_path: str,
    *,
    title: str,
    body: str,
    page_id: str | None = None,
    page_type: str | None = None,
    frontmatter_extra: str = "",
) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = [f"title: {title}"]
    if page_id is not None:
        frontmatter.append(f"id: {page_id}")
    if page_type is not None:
        frontmatter.append(f"pageType: {page_type}")
    if frontmatter_extra:
        frontmatter.append(frontmatter_extra.rstrip())
    path.write_text("---\n" + "\n".join(frontmatter) + "\n---\n" + body, encoding="utf-8")


def _index(config: MemoryWikiConfig) -> VectorIndex:
    return VectorIndex(config.vault_path / METADATA_DIRECTORY / "vector" / "index.sqlite")


def _doc(
    doc_id: str,
    *,
    page_path: str,
    title: str,
    text: str | None = None,
    doc_type: str = "page",
    metadata: dict | None = None,
) -> SearchDocument:
    return SearchDocument(
        id=doc_id,
        page_path=page_path,
        kind="concept",
        title=title,
        doc_type=doc_type,  # type: ignore[arg-type]
        text=text or f"Title: {title}\nBody:\nSemantic vector content for {title}.",
        text_hash=f"hash-{doc_id}",
        metadata=metadata or {"page_id": f"concept:{title.lower().replace(' ', '-')}"},
    )


def test_keyword_only_results_are_returned_when_vector_unavailable(tmp_path) -> None:
    config = _config(tmp_path)
    _write_page(tmp_path, "concepts/keyword.md", title="Keyword Page", body="offline keyword needle")

    results, diagnostics = search_wiki(config, "needle", search_mode="hybrid")

    assert [result.path for result in results] == ["concepts/keyword.md"]
    assert diagnostics.requested_mode == "hybrid"
    assert diagnostics.effective_mode == "keyword"
    assert diagnostics.vector_available is False
    assert any("Missing API key" in message for message in diagnostics.messages)
    assert results[0].metadata["search_type"] == "keyword"


def test_vector_only_results_are_returned_for_vector_mode(tmp_path) -> None:
    config = _config(tmp_path)
    _write_page(tmp_path, "concepts/keyword.md", title="Keyword Page", body="keyword text should not matter")
    provider = MappingEmbeddingProvider({"semantic query": [1.0, 0.0, 0.0]})
    docs = [
        _doc("page:semantic", page_path="concepts/semantic.md", title="Semantic"),
        _doc("page:weak", page_path="concepts/weak.md", title="Weak"),
    ]
    index = _index(config)
    index.upsert_documents(docs)
    index.store_embeddings(provider, docs, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

    results, diagnostics = search_wiki(config, "semantic query", search_mode="vector", provider=provider)

    assert [result.path for result in results] == ["concepts/semantic.md", "concepts/weak.md"]
    assert diagnostics.effective_mode == "vector"
    assert diagnostics.vector_available is True
    assert all(result.metadata["search_type"] == "vector" for result in results)


def test_hybrid_combines_same_page_hits_by_path_and_claim_id(tmp_path) -> None:
    config = _config(tmp_path)
    _write_page(
        tmp_path,
        "concepts/fusion.md",
        title="Fusion",
        body="Lexical page body mentions fusion needle.",
        frontmatter_extra=(
            "claims:\n"
            "  - id: claim-fusion\n"
            "    text: Fusion needle claim should merge with the vector claim.\n"
        ),
    )
    provider = MappingEmbeddingProvider({"fusion needle": [1.0, 0.0, 0.0]})
    claim_doc = _doc(
        "claim:concepts/fusion.md:claim-fusion",
        page_path="concepts/fusion.md",
        title="Fusion",
        doc_type="claim",
        text="Page: Fusion\nClaim ID: claim-fusion\nClaim: Fusion needle claim should merge with the vector claim.",
        metadata={"page_id": "concept:fusion", "claim_id": "claim-fusion"},
    )
    index = _index(config)
    index.upsert_documents([claim_doc])
    index.store_embeddings(provider, [claim_doc], [[1.0, 0.0, 0.0]])

    results, diagnostics = search_wiki(config, "fusion needle", search_mode="hybrid", provider=provider)

    assert len(results) == 1
    assert results[0].path == "concepts/fusion.md"
    assert results[0].matched_claim_id == "claim-fusion"
    assert results[0].metadata["search_type"] == "hybrid"
    assert set(results[0].metadata["search_types"]) == {"keyword", "vector"}
    assert "lexical_score" in results[0].metadata
    assert "vector_score" in results[0].metadata
    assert diagnostics.effective_mode == "hybrid"


def test_lexical_and_vector_weights_are_respected(tmp_path) -> None:
    provider = MappingEmbeddingProvider({"needle": [1.0, 0.0, 0.0]})
    keyword_doc = _doc("page:keyword", page_path="concepts/keyword.md", title="Keyword")
    vector_doc = _doc("page:vector", page_path="concepts/vector.md", title="Vector")

    lexical_config = _config(tmp_path / "lexical", search=SearchConfig(lexical_weight=0.9, vector_weight=0.1))
    _write_page(lexical_config.vault_path, "concepts/keyword.md", title="Keyword", body="needle needle needle")
    lexical_index = _index(lexical_config)
    lexical_index.upsert_documents([keyword_doc, vector_doc])
    lexical_index.store_embeddings(provider, [keyword_doc, vector_doc], [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])

    lexical_results, _ = search_wiki(lexical_config, "needle", search_mode="hybrid", provider=provider)
    assert lexical_results[0].path == "concepts/keyword.md"

    provider.calls.clear()
    vector_config = _config(tmp_path / "vector", search=SearchConfig(lexical_weight=0.1, vector_weight=0.9))
    _write_page(vector_config.vault_path, "concepts/keyword.md", title="Keyword", body="needle needle needle")
    vector_index = _index(vector_config)
    vector_index.upsert_documents([keyword_doc, vector_doc])
    vector_index.store_embeddings(provider, [keyword_doc, vector_doc], [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])

    vector_results, _ = search_wiki(vector_config, "needle", search_mode="hybrid", provider=provider)
    assert vector_results[0].path == "concepts/vector.md"


def test_mode_boosts_remain_applied(tmp_path) -> None:
    config = _config(tmp_path)
    _write_page(tmp_path, "concepts/body.md", title="Body", body="invoice triage")
    _write_page(
        tmp_path,
        "entities/router.md",
        title="Router",
        body="general notes mention invoice triage",
        page_type="person",
        frontmatter_extra=(
            "bestUsedFor:\n"
            "  - invoice escalation\n"
            "routing:\n"
            "  billing:\n"
            "    - invoice triage\n"
        ),
    )

    results, _ = search_wiki(config, "invoice triage", search_mode="keyword", mode="route-question")

    assert results[0].path == "entities/router.md"
    assert all(result.search_mode == "route-question" for result in results)


def test_diagnostics_explain_vector_fallback_from_config_default(tmp_path) -> None:
    config = _config(tmp_path, search=SearchConfig(default_search_mode="hybrid"))
    _write_page(tmp_path, "concepts/fallback.md", title="Fallback", body="fallback needle")

    results, diagnostics = search_wiki(config, "fallback needle")

    assert [result.path for result in results] == ["concepts/fallback.md"]
    assert diagnostics.requested_mode == "hybrid"
    assert diagnostics.effective_mode == "keyword"
    assert diagnostics.vector_available is False
    assert any("Falling back to keyword search" in message for message in diagnostics.messages)
    assert any("Missing API key" in message for message in diagnostics.messages)
