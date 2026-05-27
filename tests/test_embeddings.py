import json
import urllib.request

import pytest

from hermes_memory_wiki.embeddings import (
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    _urllib_transport,
)


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


def test_openai_provider_rejects_embedding_count_mismatch(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def transport(url, headers, body, timeout):
        del url, headers, body, timeout
        return {"data": [{"index": 0, "embedding": [1.0]}]}

    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        batch_size=2,
        transport=transport,
    )

    with pytest.raises(RuntimeError) as excinfo:
        provider.embed_texts(["one", "two"])

    message = str(excinfo.value).lower()
    assert "expected 2" in message
    assert "received 1" in message
    assert "openai embeddings" in message


def test_urllib_transport_wraps_malformed_json_response(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback
            return False

        def read(self):
            return b"not-json"

    def fake_urlopen(request, timeout):
        assert isinstance(request, urllib.request.Request)
        assert timeout == 3.0
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as excinfo:
        _urllib_transport("https://example.test/embeddings", {}, b"{}", 3.0)

    message = str(excinfo.value).lower()
    assert "openai embeddings" in message
    assert "json" in message


def test_openai_provider_wraps_nonnumeric_embedding_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def transport(url, headers, body, timeout):
        del url, headers, body, timeout
        return {"data": [{"index": 0, "embedding": ["not-a-number"]}]}

    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small",
        transport=transport,
    )

    with pytest.raises(RuntimeError) as excinfo:
        provider.embed_texts(["one"])

    message = str(excinfo.value).lower()
    assert "openai embedding" in message
    assert "numeric" in message
