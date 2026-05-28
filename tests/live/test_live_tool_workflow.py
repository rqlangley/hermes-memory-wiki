from __future__ import annotations

import pytest

from scripts.smoke_live_openai import REQUIRED_STEPS, run_live_openai_smoke_workflow


pytestmark = pytest.mark.live_openai


def test_live_openai_smoke_workflow_runs_actual_plugin_tools(tmp_path) -> None:
    summary = run_live_openai_smoke_workflow(vault_path=tmp_path / "vault")

    assert summary["ok"] is True
    assert summary["vaultPath"] == str(tmp_path / "vault")
    assert set(summary["registeredTools"]) >= {
        "wiki_init",
        "wiki_apply",
        "wiki_compile",
        "wiki_reindex",
        "wiki_search",
        "wiki_get",
        "wiki_lint",
    }
    assert set(summary["registeredSkills"]) >= {"wiki-maintainer", "wiki-authoring", "wiki-search"}
    assert [step["name"] for step in summary["steps"]] == REQUIRED_STEPS

    for step in summary["steps"]:
        assert step["ok"] is True
        if step["name"] != "register":
            assert isinstance(step["text"], str)
            assert step["text"]
            assert isinstance(step["details"], dict)

    reindex_step = next(step for step in summary["steps"] if step["name"] == "wiki_reindex")
    reindex_details = reindex_step["details"]
    assert reindex_details["provider"] == "openai"
    assert reindex_details["model"] == "text-embedding-3-small"
    assert reindex_details["dimensions"] == 1536
    assert reindex_details["embeddedCount"] >= 2
    assert reindex_details["diagnostics"] == []

    search_step = next(step for step in summary["steps"] if step["name"] == "wiki_search")
    search_details = search_step["details"]
    assert search_details["resultCount"] >= 1
    assert search_details["diagnostics"]["requestedMode"] == "hybrid"
    assert search_details["diagnostics"]["effectiveMode"] == "hybrid"
    assert search_details["diagnostics"]["vectorAvailable"] is True
    assert search_details["diagnostics"]["messages"] == []

    get_step = next(step for step in summary["steps"] if step["name"] == "wiki_get")
    assert get_step["details"]["found"] is True
    assert get_step["details"]["path"] == "syntheses/live-openai-smoke-synthesis.md"

    lint_step = next(step for step in summary["steps"] if step["name"] == "wiki_lint")
    assert lint_step["details"]["errorCount"] == 0
