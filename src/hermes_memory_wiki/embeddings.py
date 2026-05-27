"""Embedding provider interfaces and implementations."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Protocol, Sequence

from hermes_memory_wiki.config import EmbeddingConfig


class EmbeddingProvider(Protocol):
    """Protocol implemented by text embedding providers."""

    provider: str
    model: str
    dimensions: int | None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text, preserving input order."""
        ...


Transport = Callable[[str, Mapping[str, str], bytes, float], Mapping[str, Any]]


class FakeEmbeddingProvider:
    """Deterministic offline embedding provider for tests and local development."""

    provider = "fake"

    def __init__(self, *, model: str = "fake-embedding", dimensions: int = 16) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector: list[float] = []
        counter = 0
        while len(vector) < self.dimensions:
            digest = hashlib.sha256(
                f"{self.model}\0{counter}\0{text}".encode("utf-8")
            ).digest()
            for byte in digest:
                # Map bytes into a small, stable float range.
                vector.append((byte / 127.5) - 1.0)
                if len(vector) == self.dimensions:
                    break
            counter += 1
        return vector


class OpenAIEmbeddingProvider:
    """OpenAI embeddings provider using a small, injectable urllib transport."""

    provider = "openai"

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        *,
        model: str | None = None,
        api_key_env: str | None = None,
        batch_size: int | None = None,
        timeout_seconds: float | None = None,
        dimensions: int | None = None,
        transport: Transport | None = None,
        endpoint: str = "https://api.openai.com/v1/embeddings",
    ) -> None:
        config = config or EmbeddingConfig()
        self.model = model or config.model
        self.api_key_env = api_key_env or config.api_key_env
        self.batch_size = batch_size if batch_size is not None else config.batch_size
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(config.timeout_seconds)
        )
        self.dimensions = dimensions
        self._transport = transport or _urllib_transport
        self._endpoint = endpoint

        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                "Missing API key for OpenAI embeddings provider "
                f"(provider={self.provider}, model={self.model}). "
                f"Set environment variable {self.api_key_env}."
            )

        embeddings: list[list[float]] = []
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            body = json.dumps({"model": self.model, "input": batch}).encode("utf-8")
            response = self._transport(
                self._endpoint,
                headers,
                body,
                float(self.timeout_seconds),
            )
            embeddings.extend(_embeddings_from_response(response))

        return embeddings


def _embeddings_from_response(response: Mapping[str, Any]) -> list[list[float]]:
    data = response.get("data")
    if not isinstance(data, list):
        raise RuntimeError("OpenAI embeddings response did not contain a data list")

    ordered_items = sorted(
        enumerate(data),
        key=lambda item: item[1].get("index", item[0])
        if isinstance(item[1], Mapping)
        else item[0],
    )
    embeddings: list[list[float]] = []
    for _, item in ordered_items:
        if not isinstance(item, Mapping) or "embedding" not in item:
            raise RuntimeError("OpenAI embeddings response item missing embedding")
        embedding = item["embedding"]
        if not isinstance(embedding, list):
            raise RuntimeError("OpenAI embedding value was not a list")
        embeddings.append([float(value) for value in embedding])
    return embeddings


def _urllib_transport(
    url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url,
        data=body,
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI embeddings request failed: {exc}") from exc

    parsed = json.loads(response_body)
    if not isinstance(parsed, Mapping):
        raise RuntimeError("OpenAI embeddings response was not a JSON object")
    return parsed
