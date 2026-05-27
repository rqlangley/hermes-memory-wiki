"""Configuration defaults for the Hermes memory wiki plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class RenderConfig:
    preserve_human_blocks: bool = True
    create_backlinks: bool = True
    create_dashboards: bool = True


@dataclass(frozen=True)
class SearchConfig:
    default_search_mode: str = "hybrid"
    lexical_weight: float = 0.45
    vector_weight: float = 0.55


@dataclass(frozen=True)
class EmbeddingConfig:
    enabled: bool = True
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    api_key_env: str = "OPENAI_API_KEY"
    batch_size: int = 64
    timeout_seconds: int = 60


@dataclass(frozen=True)
class MemoryWikiConfig:
    vault_path: Path
    render: RenderConfig = field(default_factory=RenderConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    embeddings: EmbeddingConfig = field(default_factory=EmbeddingConfig)


def expand_path(path: str, home: Path | None = None) -> Path:
    """Expand a config path, honoring an injected home directory for tests."""
    if home is not None and (path == "~" or path.startswith("~/")):
        return home / path[2:]
    return Path(path).expanduser()


def load_config(
    raw: Mapping[str, Any] | None = None, *, home: Path | None = None
) -> MemoryWikiConfig:
    """Load memory wiki config from a mapping with safe defaults."""
    raw_config = _memory_wiki_section(raw)

    render_raw = _section(raw_config, "render")
    search_raw = _section(raw_config, "search")
    embeddings_raw = _section(raw_config, "embeddings")

    return MemoryWikiConfig(
        vault_path=expand_path(str(raw_config.get("vault_path", "~/.hermes/wiki/main")), home),
        render=RenderConfig(
            preserve_human_blocks=render_raw.get("preserve_human_blocks", True),
            create_backlinks=render_raw.get("create_backlinks", True),
            create_dashboards=render_raw.get("create_dashboards", True),
        ),
        search=SearchConfig(
            default_search_mode=search_raw.get("default_search_mode", "hybrid"),
            lexical_weight=search_raw.get("lexical_weight", 0.45),
            vector_weight=search_raw.get("vector_weight", 0.55),
        ),
        embeddings=EmbeddingConfig(
            enabled=embeddings_raw.get("enabled", True),
            provider=embeddings_raw.get("provider", "openai"),
            model=embeddings_raw.get("model", "text-embedding-3-small"),
            api_key_env=embeddings_raw.get("api_key_env", "OPENAI_API_KEY"),
            batch_size=embeddings_raw.get("batch_size", 64),
            timeout_seconds=embeddings_raw.get("timeout_seconds", 60),
        ),
    )


def _memory_wiki_section(raw: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if raw is None:
        return {}
    section = raw.get("memory_wiki")
    if isinstance(section, Mapping):
        return section
    return raw


def _section(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    section = raw.get(key)
    if isinstance(section, Mapping):
        return section
    return {}
