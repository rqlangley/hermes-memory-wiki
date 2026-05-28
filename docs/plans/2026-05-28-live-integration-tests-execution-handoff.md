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
- [ ] Task 3: live vector reindex/search tests.
- [ ] Task 4: reusable live plugin tool smoke script/tests.
- [ ] Task 5: pre-install plugin layout simulation tests.
- [ ] Task 6: negative-path/stale-index coverage.
- [ ] Task 7: final verification/docs refresh.

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

Start Task 3 from the implementation plan: add `tests/live/test_live_reindex_search.py` for live vector reindex and hybrid search on a temporary synthetic vault.

## Paste-Into-New-Chat Prompt

```text
Please continue executing the implementation handoff at:

/home/langley/projects/hermes-memory-wiki/docs/plans/2026-05-28-live-integration-tests-execution-handoff.md

Use software-engineering-rigor, test-driven-development, subagent-driven-development, receiving-code-review if needed, and verification-before-completion. Treat the implementation plan and this handoff as the source of truth. Continue from the first unchecked task. After each task, update docs and this handoff, run targeted verification, commit, and then proceed.
```
