import json

import pytest

from hermes_memory_wiki.embeddings import FakeEmbeddingProvider, OpenAIEmbeddingProvider


def test_fake_provider_returns_deterministic_vectors():
    provider = FakeEmbeddingProvider(dimensions=8)

    first = provider.embed_texts(["alpha", "beta", "alpha"])
    second = provider.embed_texts(["alpha", "beta", "alpha"])

    assert first == second
    assert first[0] == first[2]
    assert first[0] != first[1]


def test_fake_provider_vector_dimensions_are_stable():
    provider = FakeEmbeddingProvider(dimensions=12)

    vectors = provider.embed_texts(["", "short", "a much longer input string"])

    assert provider.dimensions == 12
    assert [len(vector) for vector in vectors] == [12, 12, 12]


def test_openai_provider_missing_api_key_diagnostic_is_clear(monkeypatch):
    monkeypatch.delenv("CUSTOM_OPENAI_KEY", raising=False)
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        api_key_env="CUSTOM_OPENAI_KEY",
    )

    with pytest.raises(RuntimeError) as excinfo:
        provider.embed_texts(["hello"])

    message = str(excinfo.value)
    assert "CUSTOM_OPENAI_KEY" in message
    assert "openai" in message.lower()
    assert "text-embedding-3-small" in message


def test_openai_embedding_input_batching_preserves_order(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def transport(url, headers, body, timeout):
        del url, timeout
        assert headers["Authorization"] == "Bearer test-key"
        payload = json.loads(body.decode("utf-8"))
        calls.append(payload["input"])
        return {
            "data": [
                {"index": index, "embedding": [float(text.split("-")[1])]}
                for index, text in enumerate(payload["input"])
            ]
        }

    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        batch_size=2,
        transport=transport,
    )

    vectors = provider.embed_texts(["item-0", "item-1", "item-2", "item-3", "item-4"])

    assert calls == [["item-0", "item-1"], ["item-2", "item-3"], ["item-4"]]
    assert vectors == [[0.0], [1.0], [2.0], [3.0], [4.0]]
