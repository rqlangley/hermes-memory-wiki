import json

from scripts.smoke_fake_hermes import run_smoke_workflow


REQUIRED_STEPS = [
    "register",
    "wiki_init",
    "wiki_apply",
    "wiki_compile",
    "wiki_reindex",
    "wiki_search",
    "wiki_get",
    "wiki_lint",
]


def test_fake_hermes_smoke_workflow_runs_offline(tmp_path):
    summary = run_smoke_workflow(vault_path=tmp_path / "vault")

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

    steps = summary["steps"]
    assert [step["name"] for step in steps] == REQUIRED_STEPS
    for step in steps:
        assert step["ok"] is True
        if step["name"] != "register":
            assert isinstance(step["text"], str)
            assert step["text"]
            assert isinstance(step["details"], dict)

    search_step = next(step for step in steps if step["name"] == "wiki_search")
    assert search_step["details"]["diagnostics"]["requestedMode"] == "hybrid"
    assert search_step["details"]["diagnostics"]["effectiveMode"] in {"hybrid", "keyword"}
    assert search_step["details"]["results"]

    get_step = next(step for step in steps if step["name"] == "wiki_get")
    assert get_step["details"]["found"] is True
    assert get_step["details"]["path"] == "syntheses/offline-smoke-synthesis.md"

    lint_step = next(step for step in steps if step["name"] == "wiki_lint")
    assert "issueCount" in lint_step["details"]

    # The summary is meant for CLI/manual debugging and must remain JSON serializable.
    json.dumps(summary)
