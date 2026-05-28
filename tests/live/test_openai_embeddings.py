from __future__ import annotations

import pytest

from hermes_memory_wiki.config import EmbeddingConfig
from hermes_memory_wiki.embeddings import OpenAIEmbeddingProvider


pytestmark = pytest.mark.live_openai


def _assert_embedding_vector(vector: list[float], *, expected_dimensions: int = 1536) -> None:
    assert isinstance(vector, list)
    assert len(vector) == expected_dimensions
    assert all(isinstance(value, float) for value in vector)
    assert any(value != 0.0 for value in vector)


def test_openai_embedding_provider_embeds_single_text() -> None:
    provider = OpenAIEmbeddingProvider(EmbeddingConfig(batch_size=2, timeout_seconds=60))

    embeddings = provider.embed_texts(
        ["hermes-memory-wiki live OpenAI embedding provider contract test"]
    )

    assert provider.provider == "openai"
    assert provider.model == "text-embedding-3-small"
    assert len(embeddings) == 1
    _assert_embedding_vector(embeddings[0])


def test_openai_embedding_provider_preserves_batch_count_and_dimensions() -> None:
    provider = OpenAIEmbeddingProvider(EmbeddingConfig(batch_size=2, timeout_seconds=60))
    texts = [
        "first synthetic hermes-memory-wiki embedding fixture",
        "second synthetic hermes-memory-wiki embedding fixture",
        "third synthetic hermes-memory-wiki embedding fixture",
    ]

    embeddings = provider.embed_texts(texts)

    assert len(embeddings) == len(texts)
    for embedding in embeddings:
        _assert_embedding_vector(embedding)
    assert embeddings[0] != embeddings[1]
