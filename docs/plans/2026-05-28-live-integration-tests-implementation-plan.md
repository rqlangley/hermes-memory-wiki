# Live Integration Tests Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add opt-in live OpenAI and pre-install plugin integration tests for `hermes-memory-wiki`, plus durable project documentation that lets a fresh session understand how to run and resume testing work.

**Architecture:** Keep the default test suite fully offline and deterministic. Add live tests under `tests/live/` gated by `HERMES_MEMORY_WIKI_LIVE_OPENAI=1` plus `OPENAI_API_KEY`, and add a reusable smoke script that exercises the actual plugin tool handlers against a temporary vault. Update project docs after every implementation step with current commands, status, and resumption notes.

**Tech Stack:** Python 3.13 in `.venv`, pytest, standard library subprocess/tempfile/json/pathlib, existing `hermes_memory_wiki` plugin/tool APIs, OpenAI embeddings via the existing urllib-backed provider.

---

## Branch Strategy

- Base branch at plan creation: `feat/initial-hermes-memory-wiki-plugin`.
- Feature branch: `feature/live-integration-tests`.
- Commit after the plan, after each implementation task, and after each documentation checkpoint.
- Push the feature branch after verified milestones if network/auth allow.
- Do not merge to main in this task unless explicitly requested after final verification.

## Documentation Checkpoint Rule

After every implementation step below, update at least:

- `docs/development.md` with current test commands/status where relevant.
- `docs/plans/2026-05-28-live-integration-tests-execution-handoff.md` with completed work, latest verification, commits, and the next action.

When test behavior affects installation or configuration, also update:

- `README.md`
- `docs/installation.md`
- `docs/configuration.md`

## Task 1: Add pytest live-test gating infrastructure

**Objective:** Introduce explicit pytest markers and shared helpers so live OpenAI tests are skipped unless the caller opts in.

**Files:**
- Create: `tests/conftest.py`
- Modify: `pyproject.toml`
- Modify docs checkpoint files.

**Step 1: Write failing test/config check**

Add `tests/conftest.py` with helper functions and pytest collection behavior:

- register marker `live_openai`.
- skip tests marked `live_openai` unless both `HERMES_MEMORY_WIKI_LIVE_OPENAI=1` and `OPENAI_API_KEY` are set.
- expose `require_live_openai()` or fixtures if useful.

Add marker config to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
  "live_openai: opt-in tests that call the real OpenAI embeddings API",
]
```

**Step 2: Run RED**

Run before adding marker/helper config if feasible:

```bash
.venv/bin/python -m pytest --markers | grep live_openai
```

Expected: fails/no marker before config.

**Step 3: Implement minimal infrastructure**

Add `tests/conftest.py` and marker config.

**Step 4: Run GREEN**

```bash
.venv/bin/python -m pytest --markers | grep live_openai
.venv/bin/python -m pytest -q
```

Expected: marker appears; offline suite remains passing.

**Step 5: Documentation checkpoint and commit**

Update docs with the marker/opt-in behavior, then commit:

```bash
git add pyproject.toml tests/conftest.py docs README.md
git commit -m "test: add live OpenAI pytest gating"
```

## Task 2: Add live OpenAI embedding provider contract tests

**Objective:** Verify the real `OpenAIEmbeddingProvider` can embed one and multiple texts with the configured key/model while preserving dimensions and input count.

**Files:**
- Create: `tests/live/test_openai_embeddings.py`
- Modify docs checkpoint files.

**Step 1: Write failing tests**

Create tests marked `@pytest.mark.live_openai`:

- `test_openai_embedding_provider_embeds_single_text`
- `test_openai_embedding_provider_preserves_batch_count_and_dimensions`

Assertions:

- provider identity is `openai`.
- model is `text-embedding-3-small`.
- result count matches input count.
- each embedding is a non-empty list of floats/ints.
- dimensions are 1536 for `text-embedding-3-small`.

**Step 2: Run RED/skip behavior**

Without opt-in:

```bash
.venv/bin/python -m pytest tests/live/test_openai_embeddings.py -q
```

Expected: skipped.

With opt-in/key:

```bash
set -a; . /home/langley/.hermes/.env; set +a; HERMES_MEMORY_WIKI_LIVE_OPENAI=1 .venv/bin/python -m pytest tests/live/test_openai_embeddings.py -q
```

Expected after test creation and existing implementation: should pass if provider works; if it fails, fix only test harness/config issues unless production bug is found.

**Step 3: Documentation checkpoint and commit**

Update docs with exact command and observed result, then commit:

```bash
git add tests/live/test_openai_embeddings.py docs README.md
git commit -m "test: add live OpenAI embedding contract tests"
```

## Task 3: Add live vector reindex/search integration tests

**Objective:** Validate end-to-end live vector indexing and hybrid search on a temporary vault using synthetic wiki pages.

**Files:**
- Create: `tests/live/test_live_reindex_search.py`
- Modify docs checkpoint files.

**Step 1: Write tests**

Add live tests marked `live_openai`:

- initialize a `tmp_path` vault.
- apply/create one or more synthetic synthesis pages through existing library functions or tool handlers.
- compile the vault.
- call `reindex_vault(force=True)` with the real OpenAI provider from environment.
- assert embedded count is positive, provider/model/dimensions match expectations, and `index.sqlite` exists.
- call `search_wiki(..., search_mode="hybrid")` and assert `effective_mode == "hybrid"`, `vector_available is True`, and results contain the synthetic page/claim.
- optionally verify keyword fallback is still available without live provider by using isolated env manipulation in a separate non-live test only if needed.

**Step 2: Run targeted live test**

```bash
set -a; . /home/langley/.hermes/.env; set +a; HERMES_MEMORY_WIKI_LIVE_OPENAI=1 .venv/bin/python -m pytest tests/live/test_live_reindex_search.py -q
```

Expected: passes and uses only `tmp_path` data.

**Step 3: Run offline suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: live tests are skipped unless opted in; default suite passes.

**Step 4: Documentation checkpoint and commit**

Update docs, then commit:

```bash
git add tests/live/test_live_reindex_search.py docs README.md
git commit -m "test: add live vector reindex search integration"
```

## Task 4: Add reusable live plugin tool smoke script and tests

**Objective:** Turn the manual live smoke workflow into a reusable, opt-in script and pytest coverage that exercises actual plugin registration/tool handlers before real Hermes installation.

**Files:**
- Create: `scripts/smoke_live_openai.py` or extend `scripts/smoke_fake_hermes.py` with a `--live-openai` mode. Prefer a separate script to keep default offline smoke simple.
- Create: `tests/live/test_live_tool_workflow.py`
- Modify: `docs/development.md`, `docs/installation.md`, `README.md`
- Modify docs checkpoint files.

**Step 1: Write failing pytest for script/API shape**

Test expectations:

- live test is skipped without opt-in/key.
- with opt-in, `run_live_openai_smoke_workflow(vault_path=tmp_path / "vault")` returns JSON-ready summary.
- summary includes registered tools/skills.
- steps include `wiki_init`, `wiki_apply`, `wiki_compile`, `wiki_reindex`, `wiki_search`, `wiki_get`, `wiki_lint`.
- `wiki_reindex` reports provider `openai`, model `text-embedding-3-small`, dimensions `1536`, embedded count > 0.
- `wiki_search` diagnostics show hybrid/vector availability.

**Step 2: Run RED**

```bash
set -a; . /home/langley/.hermes/.env; set +a; HERMES_MEMORY_WIKI_LIVE_OPENAI=1 .venv/bin/python -m pytest tests/live/test_live_tool_workflow.py -q
```

Expected: fails because script/function does not exist.

**Step 3: Implement script**

Implement a JSON-safe script with:

- fake Hermes registration context.
- temporary vault default.
- synthetic non-private page content.
- compact step summaries, not full embeddings or secrets.
- CLI flags: `--vault-path`, `--json`, maybe no explicit `--live-openai` because the script itself is live by name; still require `OPENAI_API_KEY`.
- nonzero exit and JSON error if key missing.

**Step 4: Run GREEN and manual CLI smoke**

```bash
set -a; . /home/langley/.hermes/.env; set +a; HERMES_MEMORY_WIKI_LIVE_OPENAI=1 .venv/bin/python -m pytest tests/live/test_live_tool_workflow.py -q
set -a; . /home/langley/.hermes/.env; set +a; .venv/bin/python scripts/smoke_live_openai.py
```

Expected: both pass, script outputs JSON summary.

**Step 5: Documentation checkpoint and commit**

Update docs with script usage, then commit:

```bash
git add scripts/smoke_live_openai.py tests/live/test_live_tool_workflow.py docs README.md
git commit -m "test: add live plugin tool smoke workflow"
```

## Task 5: Add pre-install plugin layout simulation tests

**Objective:** Verify the repository can be loaded through a user-plugin-like layout without mutating the real Hermes profile.

**Files:**
- Create or modify: `tests/test_user_plugin_layout.py`
- Modify docs checkpoint files.

**Step 1: Write/extend tests**

Add tests that:

- create a fake Hermes home under `tmp_path` with `plugins/memory-wiki` symlink or copy pointing to the repo.
- parse `plugin.yaml` and assert `name`, `kind`, tool declarations.
- import the root plugin module from that layout if safe, or use existing import path and verify root `__init__.py` exports `register`.
- call `register(ctx)` and assert exactly/at least expected tools and skills.
- verify tool schemas use expected external field names/casing (`vaultPath`, `searchMode`, `maxResults`, `lineCount`, `op`, etc.).

**Step 2: Run RED/GREEN**

```bash
.venv/bin/python -m pytest tests/test_user_plugin_layout.py -q
```

Expected: passes after extending implementation/tests; if tests expose missing schema expectations, fix code via TDD.

**Step 3: Documentation checkpoint and commit**

Update docs with pre-install simulation coverage, then commit:

```bash
git add tests/test_user_plugin_layout.py docs README.md
git commit -m "test: strengthen pre-install plugin layout coverage"
```

## Task 6: Add negative-path and stale-index integration coverage

**Objective:** Cover high-risk non-live failure/degradation behavior around missing API keys, keyword fallback, stale reindexing, changed pages, and deleted pages.

**Files:**
- Create or modify: `tests/test_reindex.py`, `tests/test_hybrid_search.py`, `tests/test_vector_index.py`, or a new `tests/test_integration_degradation.py`
- Modify docs checkpoint files.

**Step 1: Write failing tests**

Add non-live tests for:

- no `OPENAI_API_KEY`: provider construction/reindex reports clear missing key behavior or diagnostics.
- keyword search works with no vector index/key.
- hybrid search degrades to keyword with explicit diagnostics when no vector index/provider is available.
- updating a page causes only changed docs to be re-embedded when using fake provider.
- deleting/removing a page deletes stale vector docs.

Use fake providers and `monkeypatch.delenv("OPENAI_API_KEY", raising=False)` for deterministic behavior.

**Step 2: Run RED/GREEN**

```bash
.venv/bin/python -m pytest tests/test_reindex.py tests/test_hybrid_search.py tests/test_vector_index.py -q
```

Expected: failing tests first; minimal fixes if needed; then passing.

**Step 3: Run full offline suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: all offline tests pass; live tests skipped by default.

**Step 4: Documentation checkpoint and commit**

Update docs, then commit:

```bash
git add tests docs README.md src
 git commit -m "test: cover vector degradation and stale index paths"
```

## Task 7: Final verification and handoff refresh

**Objective:** Prove the complete test stack works and leave project docs in a clean resumable state.

**Files:**
- Modify docs: `README.md`, `docs/development.md`, `docs/installation.md`, `docs/configuration.md`, active handoff.

**Step 1: Run full offline verification**

```bash
.venv/bin/python -m compileall src tests scripts
.venv/bin/python -m pytest -q
```

Expected: compile passes; offline tests pass with live tests skipped.

**Step 2: Run full live verification**

```bash
set -a; . /home/langley/.hermes/.env; set +a; HERMES_MEMORY_WIKI_LIVE_OPENAI=1 .venv/bin/python -m pytest tests/live -q
set -a; . /home/langley/.hermes/.env; set +a; .venv/bin/python scripts/smoke_live_openai.py
```

Expected: all live tests pass using temporary vaults and synthetic content.

**Step 3: Inspect git state/diff**

```bash
git status --short --branch
git diff --stat
 git log --oneline --decorate -10
```

**Step 4: Final docs checkpoint and commit**

Commit final documentation refresh if needed:

```bash
git add docs README.md
git commit -m "docs: document live integration testing workflow"
```

**Step 5: Optional push**

```bash
git push -u origin feature/live-integration-tests
```

## Final Review Gates

After each task:

1. Controller reruns targeted verification.
2. Spec compliance review checks the task against this plan.
3. Code quality review checks tests/docs for maintainability and safety.
4. Documentation checkpoint is updated and committed.

After all tasks:

- Final integration review.
- Fresh offline and live verification.
- Git status/log/diff inspection.

## Acceptance Criteria

- Default `pytest -q` stays offline and passes without OpenAI API calls.
- Live tests are explicit, opt-in, and skipped without both opt-in flag and key.
- Live OpenAI provider, vector reindex/search, and plugin tool workflow are covered.
- Pre-install plugin layout is covered without mutating the real Hermes profile.
- Negative/degradation behaviors are covered deterministically without network calls.
- Docs explain how to run offline tests, live tests, and pre-install smoke checks.
- Active handoff/progress docs identify completed steps and next action after every checkpoint.
