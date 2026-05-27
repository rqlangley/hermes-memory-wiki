import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_memory_wiki import plugin


EXPECTED_TOOLS = {
    "wiki_init",
    "wiki_status",
    "wiki_search",
    "wiki_get",
    "wiki_apply",
    "wiki_compile",
    "wiki_reindex",
    "wiki_lint",
}


class FakeContext:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}


def _registered_tools():
    ctx = FakeContext()
    plugin.register(ctx)
    return ctx.tools


def _payload(result):
    assert isinstance(result, str)
    payload = json.loads(result)
    assert isinstance(payload["text"], str)
    assert payload["text"]
    assert isinstance(payload["details"], dict)
    return payload


def test_register_registers_expected_memory_wiki_tools():
    tools = _registered_tools()

    assert set(tools) == EXPECTED_TOOLS
    for name, entry in tools.items():
        assert entry["toolset"] == "memory_wiki"
        assert entry["description"]
        assert entry["schema"]["type"] == "object"
        assert callable(entry["handler"])


def test_schemas_require_fields_where_relevant():
    tools = _registered_tools()

    assert tools["wiki_search"]["schema"]["required"] == ["query"]
    assert tools["wiki_get"]["schema"]["required"] == ["lookup"]
    assert tools["wiki_apply"]["schema"]["required"] == ["op"]

    for name in EXPECTED_TOOLS - {"wiki_search", "wiki_get", "wiki_apply"}:
        assert "required" not in tools[name]["schema"] or tools[name]["schema"]["required"] == []


def test_wiki_init_handler_returns_text_and_details(tmp_path):
    handler = _registered_tools()["wiki_init"]["handler"]

    payload = _payload(handler({"vaultPath": str(tmp_path / "vault")}))

    assert "initialized" in payload["text"].lower()
    assert payload["details"]["vaultPath"] == str(tmp_path / "vault")
    assert payload["details"]["created"] is True
    assert (tmp_path / "vault" / ".hermes-wiki" / "state.json").is_file()


def test_wiki_status_handler_returns_basic_vault_status(tmp_path):
    vault = tmp_path / "vault"
    plugin.register(FakeContext())
    _registered_tools()["wiki_init"]["handler"]({"vaultPath": str(vault)})

    payload = _payload(_registered_tools()["wiki_status"]["handler"]({"vaultPath": str(vault)}))

    assert "status" in payload["text"].lower()
    assert payload["details"]["vaultPath"] == str(vault)
    assert payload["details"]["exists"] is True
    assert payload["details"]["pageCount"] == 0


def test_wiki_get_handler_calls_core_and_returns_page(monkeypatch, tmp_path):
    from hermes_memory_wiki import tools

    def fake_get_page(config, lookup, *, from_line=1, line_count=200):
        assert config.vault_path == tmp_path
        assert lookup == "entities/alice.md"
        assert from_line == 2
        assert line_count == 5
        return SimpleNamespace(
            path="entities/alice.md",
            id="entity.alice",
            title="Alice",
            kind="entity",
            content="Alice excerpt",
            from_line=2,
            line_count=5,
            total_lines=9,
            truncated=True,
        )

    monkeypatch.setattr(tools, "get_page", fake_get_page)

    payload = _payload(
        _registered_tools()["wiki_get"]["handler"](
            {"vaultPath": str(tmp_path), "lookup": "entities/alice.md", "fromLine": 2, "lineCount": 5}
        )
    )

    assert "Alice" in payload["text"]
    assert payload["details"]["path"] == "entities/alice.md"
    assert payload["details"]["content"] == "Alice excerpt"
    assert payload["details"]["truncated"] is True


def test_wiki_search_handler_calls_core_and_returns_results(monkeypatch, tmp_path):
    from hermes_memory_wiki import tools

    diagnostics = SimpleNamespace(
        requested_mode="keyword", effective_mode="keyword", vector_available=False, messages=[]
    )

    def fake_search_wiki(config, query, *, max_results=10, mode="auto", search_mode=None, provider=None):
        assert config.vault_path == tmp_path
        assert query == "alice"
        assert max_results == 3
        assert mode == "find-person"
        assert search_mode == "keyword"
        assert provider is None
        return [
            SimpleNamespace(
                corpus="page",
                path="entities/alice.md",
                title="Alice",
                kind="entity",
                score=1.0,
                snippet="Alice snippet",
                search_mode="find-person",
                matched_claim_id=None,
                metadata={"search_type": "keyword"},
            )
        ], diagnostics

    monkeypatch.setattr(tools, "search_wiki", fake_search_wiki)

    payload = _payload(
        _registered_tools()["wiki_search"]["handler"](
            {
                "vaultPath": str(tmp_path),
                "query": "alice",
                "maxResults": 3,
                "mode": "find-person",
                "searchMode": "keyword",
            }
        )
    )

    assert "1 result" in payload["text"]
    assert payload["details"]["results"][0]["path"] == "entities/alice.md"
    assert payload["details"]["diagnostics"]["effectiveMode"] == "keyword"


def test_wiki_apply_handler_normalizes_and_calls_core(monkeypatch, tmp_path):
    from hermes_memory_wiki import tools

    calls = {}

    def fake_normalize(raw):
        calls["raw"] = raw
        return "normalized"

    def fake_apply(config, mutation):
        assert config.vault_path == tmp_path
        assert mutation == "normalized"
        return SimpleNamespace(path="syntheses/answer.md", id="synthesis.answer", created=True)

    monkeypatch.setattr(tools, "normalize_mutation", fake_normalize)
    monkeypatch.setattr(tools, "apply_mutation", fake_apply)

    payload = _payload(
        _registered_tools()["wiki_apply"]["handler"](
            {"vaultPath": str(tmp_path), "op": "create_synthesis", "title": "Answer"}
        )
    )

    assert calls["raw"]["op"] == "create_synthesis"
    assert "applied" in payload["text"].lower()
    assert payload["details"] == {
        "path": "syntheses/answer.md",
        "id": "synthesis.answer",
        "created": True,
    }


@pytest.mark.parametrize(
    ("tool_name", "core_name", "result", "expected"),
    [
        (
            "wiki_compile",
            "compile_vault",
            SimpleNamespace(
                vault_root=Path("/vault"),
                page_counts={"entity": 2},
                claim_count=4,
                updated_files=[Path("/vault/index.md")],
            ),
            {"claimCount": 4, "updatedFileCount": 1},
        ),
        (
            "wiki_lint",
            "lint_vault",
            SimpleNamespace(
                vault_root=Path("/vault"),
                issue_count=3,
                error_count=1,
                warning_count=2,
                markdown_path=Path("/vault/.hermes-wiki/cache/lint-report.md"),
                json_path=Path("/vault/.hermes-wiki/cache/lint-report.json"),
                updated_files=[],
            ),
            {"issueCount": 3, "errorCount": 1, "warningCount": 2},
        ),
        (
            "wiki_reindex",
            "reindex_vault",
            SimpleNamespace(
                embedded_count=5,
                skipped_count=6,
                deleted_count=1,
                provider="fake",
                model="fake-model",
                dimensions=3,
                diagnostics=[],
            ),
            {"embeddedCount": 5, "skippedCount": 6, "deletedCount": 1},
        ),
    ],
)
def test_maintenance_handlers_call_core_and_return_details(
    monkeypatch, tmp_path, tool_name, core_name, result, expected
):
    from hermes_memory_wiki import tools

    def fake_core(config, **kwargs):
        assert config.vault_path == tmp_path
        if core_name == "reindex_vault":
            assert kwargs == {"force": True}
        else:
            assert kwargs == {}
        return result

    monkeypatch.setattr(tools, core_name, fake_core)

    args = {"vaultPath": str(tmp_path)}
    if tool_name == "wiki_reindex":
        args["force"] = True
    payload = _payload(_registered_tools()[tool_name]["handler"](args))

    for key, value in expected.items():
        assert payload["details"][key] == value
