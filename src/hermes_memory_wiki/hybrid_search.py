from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.embeddings import EmbeddingProvider
from hermes_memory_wiki.search_keyword import WikiSearchResult, keyword_search
from hermes_memory_wiki.vault import read_queryable_pages
from hermes_memory_wiki.vector_index import vector_search


@dataclass
class SearchDiagnostics:
    requested_mode: str
    effective_mode: str
    vector_available: bool
    messages: list[str]


def search_wiki(
    config: MemoryWikiConfig,
    query: str,
    *,
    max_results: int = 10,
    mode: str = "auto",
    search_mode: str | None = None,
    provider: EmbeddingProvider | None = None,
) -> tuple[list[WikiSearchResult], SearchDiagnostics]:
    """Search the wiki with keyword, vector, or weighted hybrid ranking."""
    requested_mode = search_mode or config.search.default_search_mode
    requested_mode = requested_mode.lower().strip() if requested_mode else "hybrid"
    if requested_mode == "auto":
        requested_mode = config.search.default_search_mode.lower().strip() or "hybrid"
        if requested_mode == "auto":
            requested_mode = "hybrid"
    if requested_mode not in {"keyword", "vector", "hybrid"}:
        raise ValueError(f"Unsupported wiki search mode: {requested_mode}")

    if max_results <= 0:
        return [], SearchDiagnostics(
            requested_mode=requested_mode,
            effective_mode=requested_mode,
            vector_available=False,
            messages=[],
        )

    if requested_mode == "keyword":
        results = _keyword_results(config, query, max_results=max_results, mode=mode)
        return results, SearchDiagnostics(
            requested_mode=requested_mode,
            effective_mode="keyword",
            vector_available=False,
            messages=[],
        )

    if requested_mode == "vector":
        vector_results, vector_messages = _vector_results(
            config, query, max_results=max_results, mode=mode, provider=provider
        )
        vector_available = not vector_messages
        return vector_results[:max_results], SearchDiagnostics(
            requested_mode=requested_mode,
            effective_mode="vector",
            vector_available=vector_available,
            messages=vector_messages,
        )

    keyword_results = _keyword_results(config, query, max_results=max_results, mode=mode)
    vector_results, vector_messages = _vector_results(
        config, query, max_results=max_results, mode=mode, provider=provider
    )
    vector_available = not vector_messages
    if not vector_available:
        messages = list(vector_messages)
        messages.append("Falling back to keyword search because vector search is unavailable.")
        return keyword_results, SearchDiagnostics(
            requested_mode=requested_mode,
            effective_mode="keyword",
            vector_available=False,
            messages=messages,
        )

    fused = _fuse_results(
        keyword_results,
        vector_results,
        lexical_weight=float(config.search.lexical_weight),
        vector_weight=float(config.search.vector_weight),
        max_results=max_results,
    )
    return fused, SearchDiagnostics(
        requested_mode=requested_mode,
        effective_mode="hybrid",
        vector_available=True,
        messages=list(vector_messages),
    )


def _keyword_results(
    config: MemoryWikiConfig, query: str, *, max_results: int, mode: str
) -> list[WikiSearchResult]:
    pages = read_queryable_pages(config.vault_path)
    results = keyword_search(pages, query, max_results=max_results, mode=mode)
    for result in results:
        metadata = dict(result.metadata)
        metadata.setdefault("search_type", "keyword")
        result.metadata = metadata
    return results


def _vector_results(
    config: MemoryWikiConfig,
    query: str,
    *,
    max_results: int,
    mode: str,
    provider: EmbeddingProvider | None,
) -> tuple[list[WikiSearchResult], list[str]]:
    results = vector_search(
        config,
        query,
        provider=provider,
        max_results=max_results,
        mode=mode,
    )
    diagnostics = list(getattr(results, "diagnostics", []))
    return list(results), diagnostics


def _fuse_results(
    keyword_results: list[WikiSearchResult],
    vector_results: list[WikiSearchResult],
    *,
    lexical_weight: float,
    vector_weight: float,
    max_results: int,
) -> list[WikiSearchResult]:
    keyword_normalized = _normalized_scores(keyword_results)
    vector_normalized = _normalized_scores(vector_results)
    combined: dict[tuple[str, str | None], WikiSearchResult] = {}
    order: dict[tuple[str, str | None], int] = {}

    for result in keyword_results:
        key = _fusion_key(result)
        order.setdefault(key, len(order))
        fused = _copy_result(result)
        lexical_score = keyword_normalized.get(id(result), 0.0)
        fused.score = lexical_weight * lexical_score
        fused.metadata = _hybrid_metadata(
            fused.metadata,
            search_types=["keyword"],
            lexical_score=lexical_score,
            vector_score=0.0,
        )
        combined[key] = fused

    for result in vector_results:
        key = _fusion_key(result)
        order.setdefault(key, len(order))
        vector_score = vector_normalized.get(id(result), 0.0)
        if key not in combined:
            fused = _copy_result(result)
            fused.score = vector_weight * vector_score
            fused.metadata = _hybrid_metadata(
                fused.metadata,
                search_types=["vector"],
                lexical_score=0.0,
                vector_score=vector_score,
            )
            combined[key] = fused
            continue

        existing = combined[key]
        existing.score += vector_weight * vector_score
        existing.metadata = _merge_metadata(existing.metadata, result.metadata)
        search_types = list(existing.metadata.get("search_types", []))
        if "vector" not in search_types:
            search_types.append("vector")
        existing.metadata = _hybrid_metadata(
            existing.metadata,
            search_types=search_types,
            lexical_score=float(existing.metadata.get("lexical_score", 0.0)),
            vector_score=vector_score,
        )
        if not existing.snippet and result.snippet:
            existing.snippet = result.snippet

    fused_results = list(combined.values())
    fused_results.sort(key=lambda result: (-result.score, order[_fusion_key(result)], result.path))
    return fused_results[:max_results]


def _normalized_scores(results: list[WikiSearchResult]) -> dict[int, float]:
    positive_scores = [max(0.0, float(result.score)) for result in results]
    if not positive_scores:
        return {}
    max_score = max(positive_scores)
    if max_score <= 0.0:
        return {id(result): 0.0 for result in results}
    return {id(result): max(0.0, float(result.score)) / max_score for result in results}


def _fusion_key(result: WikiSearchResult) -> tuple[str, str | None]:
    if result.matched_claim_id:
        return result.path, result.matched_claim_id
    document_type = result.metadata.get("document_type")
    document_id = result.metadata.get("document_id")
    if document_type == "claim" and document_id:
        return result.path, str(document_id)
    return result.path, None


def _copy_result(result: WikiSearchResult) -> WikiSearchResult:
    return WikiSearchResult(
        corpus=result.corpus,
        path=result.path,
        title=result.title,
        kind=result.kind,
        score=float(result.score),
        snippet=result.snippet,
        search_mode=result.search_mode,
        matched_claim_id=result.matched_claim_id,
        metadata=dict(result.metadata),
    )


def _hybrid_metadata(
    metadata: dict[str, Any],
    *,
    search_types: list[str],
    lexical_score: float,
    vector_score: float,
) -> dict[str, Any]:
    updated = dict(metadata)
    updated["search_type"] = "hybrid"
    updated["search_types"] = search_types
    updated["lexical_score"] = lexical_score
    updated["vector_score"] = vector_score
    return updated


def _merge_metadata(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if key not in merged:
            merged[key] = value
    return merged
