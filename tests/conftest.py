"""Shared pytest configuration for hermes-memory-wiki tests."""

from __future__ import annotations

import os

import pytest


LIVE_OPENAI_MARKER = "live_openai"
LIVE_OPENAI_ENV = "HERMES_MEMORY_WIKI_LIVE_OPENAI"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


def live_openai_enabled() -> bool:
    """Return whether tests may call the real OpenAI embeddings API."""

    return os.environ.get(LIVE_OPENAI_ENV) == "1" and bool(os.environ.get(OPENAI_API_KEY_ENV))


def live_openai_skip_reason() -> str:
    """Explain why live OpenAI tests are disabled."""

    if os.environ.get(LIVE_OPENAI_ENV) != "1":
        return f"set {LIVE_OPENAI_ENV}=1 to enable live OpenAI tests"
    if not os.environ.get(OPENAI_API_KEY_ENV):
        return f"set {OPENAI_API_KEY_ENV} to run live OpenAI tests"
    return "live OpenAI tests are enabled"


def pytest_configure(config: pytest.Config) -> None:
    marker_definition = f"{LIVE_OPENAI_MARKER}: opt-in tests that call the real OpenAI embeddings API"
    configured_markers = config.getini("markers")
    if not any(marker.startswith(f"{LIVE_OPENAI_MARKER}:") for marker in configured_markers):
        config.addinivalue_line("markers", marker_definition)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if live_openai_enabled():
        return
    skip_live_openai = pytest.mark.skip(reason=live_openai_skip_reason())
    for item in items:
        if LIVE_OPENAI_MARKER in item.keywords:
            item.add_marker(skip_live_openai)
