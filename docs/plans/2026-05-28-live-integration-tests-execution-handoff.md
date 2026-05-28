# Execution Handoff: Live Integration Tests

## Goal

Build and verify opt-in live OpenAI and pre-install plugin integration tests for `hermes-memory-wiki`, while keeping the default test suite offline and updating documentation after every step so a fresh session can resume safely.

## Source Artifacts

- Implementation plan: `docs/plans/2026-05-28-live-integration-tests-implementation-plan.md`
- Prior design/approval: user approved the live-test recommendations in chat on 2026-05-28.

## Repository

- Path: `/home/langley/projects/hermes-memory-wiki`
- Remote: `https://github.com/rqlangley/hermes-memory-wiki.git`
- Base branch at start: `feat/initial-hermes-memory-wiki-plugin`
- Feature branch: `feature/live-integration-tests`

## Current Status

- [x] Plan created and committed in `439ffb2 docs: plan live integration tests`.
- [x] Task 1: live pytest gating implemented in `tests/conftest.py` and `pyproject.toml`.
- [x] Task 2: live OpenAI embedding provider tests implemented in `tests/live/test_openai_embeddings.py`.
- [x] Task 3: live vector reindex/search tests implemented in `tests/live/test_live_reindex_search.py`.
- [x] Task 4: reusable live plugin tool smoke script/tests implemented in `scripts/smoke_live_openai.py` and `tests/live/test_live_tool_workflow.py`.
- [x] Task 5: pre-install plugin layout simulation tests strengthened in `tests/test_user_plugin_layout.py`.
- [x] Task 6: negative-path/stale-index coverage.
- [x] Task 7: final verification/docs refresh.

## Latest Verification

Task 1 verification on 2026-05-28:

```bash
.venv/bin/python -m pytest --markers | grep live_openai
.venv/bin/python -m pytest -q
```

Result: marker registration visible; 195 tests passed.

Task 2 verification on 2026-05-28:

```bash
.venv/bin/python -m pytest tests/live/test_openai_embeddings.py -q
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live/test_openai_embeddings.py -q
```

Result: default run skipped 2 live tests; opt-in live run passed 2 tests.

Task 3 verification on 2026-05-28:

```bash
.venv/bin/python -m pytest tests/live/test_live_reindex_search.py -q
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live/test_live_reindex_search.py -q
.venv/bin/python -m pytest -q
```

Result: default live module run skipped 2 tests; opt-in live run passed 2 tests; full default suite passed with 195 passed and 4 skipped.

Task 4 verification on 2026-05-28:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live/test_live_tool_workflow.py -q
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python scripts/smoke_live_openai.py
.venv/bin/python -m pytest tests/live/test_live_tool_workflow.py -q
.venv/bin/python -m pytest -q
```

Result: opt-in live tool workflow passed 1 test; script returned an OK JSON summary with OpenAI reindex details; default tool workflow test skipped 1 test; full default suite passed with 195 passed and 5 skipped.

Task 4 review-fix verification on 2026-05-28:

```bash
.venv/bin/python -m pytest tests/test_smoke_live_openai_script.py -q
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live/test_live_tool_workflow.py -q
env -u OPENAI_API_KEY -u PYTHONPATH /usr/bin/python3 -S scripts/smoke_live_openai.py --json
```

Result: checkout import/bootstrap regression test passed; explicit `--json` missing-key CLI path returned safe JSON with exit code 1; opt-in live tool workflow still passed; bare-interpreter no-key CLI check returned JSON with exit code 1 instead of a traceback.

Task 5 verification on 2026-05-28:

```bash
.venv/bin/python -m pytest tests/test_user_plugin_layout.py -q
.venv/bin/python -m compileall src tests scripts
.venv/bin/python -m pytest -q
```

RED result before the minimal schema fix: focused layout test failed because `wiki_search` still advertised legacy `mode` in its public schema instead of only the external `searchMode` field.

GREEN result: focused pre-install layout simulation passed 6 tests; compileall passed; full default suite passed with 200 passed and 5 skipped. Commit: `test: strengthen pre-install plugin layout coverage`.

Task 6 verification on 2026-05-28:

```bash
.venv/bin/python -m pytest tests/test_hybrid_search.py::test_keyword_only_results_are_returned_when_vector_unavailable tests/test_hybrid_search.py::test_hybrid_fallback_reports_missing_index_when_provider_exists -q
.venv/bin/python -m pytest tests/test_reindex.py tests/test_hybrid_search.py tests/test_vector_index.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall src tests scripts
```

RED result after adding stricter degradation assertions: focused run failed 2 hybrid fallback tests because diagnostics did not include an explicit `Vector search unavailable` message.

GREEN result: focused negative/degradation/stale-index run passed 35 tests; compileall passed; full default suite passed with 204 passed and 5 skipped. Commit: `test: cover vector degradation and stale index paths`.

Task 6 review-fix verification on 2026-05-28:

```bash
.venv/bin/python -m pytest tests/test_reindex.py tests/test_hybrid_search.py tests/test_vector_index.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall src tests scripts
```

Result: duplicate hybrid fallback diagnostics were collapsed into one explicit message, reindex-level stale claim deletion coverage was added, focused run passed 36 tests, full default suite passed with 205 passed and 5 skipped, and compileall passed. Commit: `test: address vector degradation review feedback`.

Task 7 final verification on 2026-05-28:

```bash
.venv/bin/python -m compileall src tests scripts
.venv/bin/python -m pytest -q
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live -q
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python scripts/smoke_live_openai.py --json
```

Result: compileall passed; default offline suite passed with 205 passed and 5 skipped; opt-in live suite passed 5 tests; live smoke script returned an OK JSON summary with 8 registered tools, 3 registered skills, OpenAI provider/model `text-embedding-3-small`, 1536 dimensions, and no secret output.

## Environment and Secrets

- `OPENAI_API_KEY` must be supplied from the caller's local secret manager or untracked environment.
- Live tests must be gated by `HERMES_MEMORY_WIKI_LIVE_OPENAI=1` plus `OPENAI_API_KEY`.
- Do not print the API key. Do not commit `.env` files or local secret-file paths.

## Required Workflow

Use:

- `software-engineering-rigor`
- `test-driven-development`
- `subagent-driven-development` for implementation/reviews where practical
- `receiving-code-review` if reviewers find issues
- `verification-before-completion`

After every implementation task:

1. Run targeted verification.
2. Update docs and this handoff with current state.
3. Commit code/tests/docs.
4. Run spec compliance review, then quality review.
5. Proceed only after issues are fixed or explicitly deferred.

## Verification Commands

Offline/default:

```bash
.venv/bin/python -m compileall src tests scripts
.venv/bin/python -m pytest -q
```

Live OpenAI:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live -q
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python scripts/smoke_live_openai.py
```

## Next Action

Implementation plan tasks are complete. Next action: review git state, run final review gates if this handoff is resumed before merge, push `feature/live-integration-tests`, and merge only after validation remains green.

## Paste-Into-New-Chat Prompt

```text
Please continue executing the implementation handoff at:

/home/langley/projects/hermes-memory-wiki/docs/plans/2026-05-28-live-integration-tests-execution-handoff.md

Use software-engineering-rigor, test-driven-development, subagent-driven-development, receiving-code-review if needed, and verification-before-completion. Treat the implementation plan and this handoff as the source of truth. Continue from the first unchecked task. After each task, update docs and this handoff, run targeted verification, commit, and then proceed.
```
