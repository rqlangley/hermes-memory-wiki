from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, cast

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
EXPECTED_SKILLS = ["wiki-maintainer", "wiki-authoring", "wiki-search"]
EXPECTED_SCHEMA_PROPERTIES = {
    "wiki_init": {"vaultPath"},
    "wiki_status": {"vaultPath"},
    "wiki_search": {"vaultPath", "query", "maxResults", "mode", "searchMode"},
    "wiki_get": {"vaultPath", "lookup", "fromLine", "lineCount"},
    "wiki_apply": {
        "vaultPath",
        "op",
        "lookup",
        "title",
        "body",
        "sourceIds",
        "claims",
        "questions",
        "contradictions",
        "confidence",
        "status",
        "updatedAt",
    },
    "wiki_compile": {"vaultPath"},
    "wiki_reindex": {"vaultPath", "force"},
    "wiki_lint": {"vaultPath"},
}


class FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}
        self.skills: dict[str, dict[str, Any]] = {}

    def register_tool(self, name: str, toolset: str, schema: dict[str, Any], handler: Any, **kwargs: Any) -> None:
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_skill(self, name: str, path: str | Path, **kwargs: Any) -> None:
        self.skills[name] = {"path": Path(path), **kwargs}


def _fake_plugin_link(tmp_path: Path) -> Path:
    hermes_home = tmp_path / "fake-hermes-home"
    plugins_dir = hermes_home / "plugins"
    plugins_dir.mkdir(parents=True)
    plugin_link = plugins_dir / "memory-wiki"
    plugin_link.symlink_to(PROJECT_ROOT, target_is_directory=True)
    return plugin_link


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


def test_fake_hermes_home_manifest_is_loaded_from_user_plugin_layout(tmp_path: Path) -> None:
    plugin_link = _fake_plugin_link(tmp_path)
    manifest_path = plugin_link / "plugin.yaml"

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert plugin_link == tmp_path / "fake-hermes-home" / "plugins" / "memory-wiki"
    assert manifest["name"] == "memory-wiki"
    assert manifest["kind"] == "standalone"
    assert manifest["provides_tools"] == EXPECTED_TOOLS
    assert not (Path.home() / ".hermes" / "plugins" / "memory-wiki-test-sentinel").exists()


def test_fake_user_plugin_layout_import_registers_expected_tools_and_skills(tmp_path: Path) -> None:
    plugin_link = _fake_plugin_link(tmp_path)
    root_init = plugin_link / "__init__.py"
    script = dedent(
        f"""
        import importlib.util
        import json
        import sys
        from pathlib import Path

        sys.path.insert(0, {str(plugin_link / "src")!r})

        class FakeContext:
            def __init__(self):
                self.tools = {{}}
                self.skills = {{}}
            def register_tool(self, name, toolset, schema, handler, **kwargs):
                self.tools[name] = {{"toolset": toolset, "schema": schema, "handler": handler, **kwargs}}
            def register_skill(self, name, path, **kwargs):
                self.skills[name] = {{"path": str(path), **kwargs}}

        spec = importlib.util.spec_from_file_location("memory_wiki_user_plugin", {str(root_init)!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ctx = FakeContext()
        module.register(ctx)
        print(json.dumps({{
            "tools": sorted(ctx.tools),
            "skills": sorted(ctx.skills),
            "skillPaths": {{name: entry["path"] for name, entry in ctx.skills.items()}},
        }}))
        """
    )

    env = {**os.environ, "HOME": str(tmp_path / "fake-home-not-real-profile")}
    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, env=env)
    payload = cast(dict[str, Any], json.loads(result.stdout))

    assert payload["tools"] == sorted(EXPECTED_TOOLS)
    assert payload["skills"] == sorted(EXPECTED_SKILLS)
    skill_paths = cast(dict[str, str], payload["skillPaths"])
    for path in skill_paths.values():
        skill_path = Path(path)
        assert skill_path.is_file()
        assert skill_path.is_relative_to(plugin_link / "src" / "hermes_memory_wiki" / "skills")


def test_register_exposes_expected_tool_and_skill_declarations() -> None:
    ctx = FakeContext()

    package_register(ctx)

    assert list(ctx.tools) == EXPECTED_TOOLS
    assert list(ctx.skills) == EXPECTED_SKILLS
    for entry in ctx.tools.values():
        assert entry["toolset"] == "memory_wiki"
        assert callable(entry["handler"])
    for entry in ctx.skills.values():
        assert entry["description"]
        assert Path(entry["path"]).is_file()


def test_registered_handlers_accept_hermes_runtime_kwargs(tmp_path: Path) -> None:
    ctx = FakeContext()
    package_register(ctx)

    result = ctx.tools["wiki_init"]["handler"]({"vaultPath": str(tmp_path / "wiki")}, task_id="task-123")

    assert "Initialized memory wiki vault" in result
    assert str(tmp_path / "wiki") in result


def test_registered_tool_schemas_use_external_field_names_and_casing() -> None:
    ctx = FakeContext()

    package_register(ctx)

    for name, expected_properties in EXPECTED_SCHEMA_PROPERTIES.items():
        schema = cast(dict[str, Any], ctx.tools[name]["schema"])
        assert schema["type"] == "object"
        assert set(schema["properties"]) == expected_properties
        assert "vaultPath" in schema["properties"]
        assert "vault_path" not in schema["properties"]

    search_schema = cast(dict[str, Any], ctx.tools["wiki_search"]["schema"])
    search_properties = search_schema["properties"]
    assert "searchMode" in search_properties
    assert "search_mode" not in search_properties
    assert "maxResults" in search_properties
    assert "max_results" not in search_properties
    get_schema = cast(dict[str, Any], ctx.tools["wiki_get"]["schema"])
    apply_schema = cast(dict[str, Any], ctx.tools["wiki_apply"]["schema"])
    assert get_schema["properties"]["lineCount"]["default"] == 200
    assert apply_schema["required"] == ["op"]
