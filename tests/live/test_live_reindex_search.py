from __future__ import annotations

import pytest

from hermes_memory_wiki.apply import apply_mutation, normalize_mutation
from hermes_memory_wiki.compile import compile_vault
from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.hybrid_search import search_wiki
from hermes_memory_wiki.vault import METADATA_DIRECTORY, initialize_vault
from hermes_memory_wiki.vector_index import reindex_vault


pytestmark = pytest.mark.live_openai


def _config(vault_path) -> MemoryWikiConfig:
    return MemoryWikiConfig(vault_path=vault_path)


def _create_synthetic_page(config: MemoryWikiConfig) -> None:
    result = apply_mutation(
        config,
        normalize_mutation(
            {
                "op": "create_synthesis",
                "path": "syntheses/live-vector-integration.md",
                "id": "synthesis.live-vector-integration",
                "title": "Live Vector Integration",
                "body": (
                    "This page validates live OpenAI vector reindexing for "
                    "hermes-memory-wiki with synthetic content only."
                ),
                "sourceIds": ["live-vector-fixture"],
                "claims": [
                    {
                        "id": "claim.live-vector-integration",
                        "text": "Live OpenAI vector reindexing retrieves synthetic Hermes wiki content.",
                        "confidence": 0.99,
                        "evidence": [
                            {
                                "sourceId": "live-vector-fixture",
                                "quote": "synthetic Hermes wiki content",
                            }
                        ],
                    }
                ],
                "status": "stable",
            }
        ),
    )
    assert result.path == "syntheses/live-vector-integration.md"
    assert result.id == "synthesis.live-vector-integration"
    assert result.created is True


def test_live_reindex_builds_openai_vector_index_for_synthetic_vault(tmp_path) -> None:
    config = _config(tmp_path / "vault")
    initialize_vault(config)
    _create_synthetic_page(config)
    compile_result = compile_vault(config)

    result = reindex_vault(config, force=True)

    assert compile_result.updated_files
    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 1536
    assert result.diagnostics == []
    assert result.embedded_count >= 2
    assert result.skipped_count == 0
    assert (config.vault_path / METADATA_DIRECTORY / "vector" / "index.sqlite").exists()


def test_live_hybrid_search_uses_openai_vectors_for_synthetic_vault(tmp_path) -> None:
    config = _config(tmp_path / "vault")
    initialize_vault(config)
    _create_synthetic_page(config)
    compile_vault(config)
    reindex_result = reindex_vault(config, force=True)
    assert reindex_result.diagnostics == []

    results, diagnostics = search_wiki(
        config,
        "Can live OpenAI vector search retrieve synthetic Hermes wiki content?",
        search_mode="hybrid",
        max_results=5,
    )

    assert diagnostics.requested_mode == "hybrid"
    assert diagnostics.effective_mode == "hybrid"
    assert diagnostics.vector_available is True
    assert diagnostics.messages == []
    assert results
    assert any(result.path == "syntheses/live-vector-integration.md" for result in results)
    assert any(
        result.matched_claim_id == "claim.live-vector-integration" for result in results
    )
    assert any(
        "vector" in result.metadata.get("searchTypes", [result.metadata.get("searchType")])
        for result in results
    )
