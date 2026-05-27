from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from hermes_memory_wiki.plugin import register as package_register


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = [
    "wiki_init",
    "wiki_status",
    "wiki_search",
    "wiki_get",
    "wiki_apply",
    "wiki_compile",
    "wiki_reindex",
    "wiki_lint",
]


def test_root_init_exposes_package_register() -> None:
    root_init = PROJECT_ROOT / "__init__.py"
    assert root_init.exists()

    spec = importlib.util.spec_from_file_location("hermes_memory_wiki_user_plugin", root_init)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.register is package_register


def test_plugin_manifest_declares_memory_wiki_plugin() -> None:
    manifest_path = PROJECT_ROOT / "plugin.yaml"
    assert manifest_path.exists()

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert manifest == {
        "name": "memory-wiki",
        "version": "0.1.0",
        "kind": "standalone",
        "description": "Hermes memory wiki tools with hybrid keyword/vector search.",
        "provides_tools": EXPECTED_TOOLS,
    }
