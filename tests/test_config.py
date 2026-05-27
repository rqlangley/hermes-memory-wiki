from pathlib import Path

from hermes_memory_wiki.config import load_config


def test_default_vault_path_expands_to_home():
    home = Path("/tmp/hermes-test-home")

    config = load_config(home=home)

    assert config.vault_path == home / ".hermes" / "wiki" / "main"


def test_default_search_mode_is_hybrid():
    config = load_config()

    assert config.search.default_search_mode == "hybrid"


def test_default_embedding_model_is_text_embedding_3_small():
    config = load_config()

    assert config.embeddings.model == "text-embedding-3-small"


def test_embeddings_enabled_by_default():
    config = load_config()

    assert config.embeddings.enabled is True


def test_explicit_config_overrides_defaults():
    home = Path("/tmp/hermes-test-home")

    config = load_config(
        {
            "memory_wiki": {
                "vault_path": "~/custom-wiki",
                "render": {
                    "preserve_human_blocks": False,
                    "create_backlinks": False,
                    "create_dashboards": False,
                },
                "search": {
                    "default_search_mode": "lexical",
                    "lexical_weight": 1.0,
                    "vector_weight": 0.0,
                },
                "embeddings": {
                    "enabled": False,
                    "provider": "local",
                    "model": "custom-model",
                    "api_key_env": "CUSTOM_API_KEY",
                    "batch_size": 8,
                    "timeout_seconds": 5,
                },
            }
        },
        home=home,
    )

    assert config.vault_path == home / "custom-wiki"
    assert config.render.preserve_human_blocks is False
    assert config.render.create_backlinks is False
    assert config.render.create_dashboards is False
    assert config.search.default_search_mode == "lexical"
    assert config.search.lexical_weight == 1.0
    assert config.search.vector_weight == 0.0
    assert config.embeddings.enabled is False
    assert config.embeddings.provider == "local"
    assert config.embeddings.model == "custom-model"
    assert config.embeddings.api_key_env == "CUSTOM_API_KEY"
    assert config.embeddings.batch_size == 8
    assert config.embeddings.timeout_seconds == 5


def test_embedding_api_key_env_defaults_to_openai_api_key():
    config = load_config()

    assert config.embeddings.api_key_env == "OPENAI_API_KEY"
