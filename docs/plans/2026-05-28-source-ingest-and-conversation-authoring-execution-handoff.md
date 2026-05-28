# Source Ingest and Conversation Authoring Execution Handoff

## Goal

Implement source ingestion, conversation-summary source capture, typed entity/concept upserts, and updated authoring workflow guidance for `/home/langley/projects/hermes-memory-wiki`.

## Required workflow

Use the user's rigorous software engineering workflow:

1. Load `software-engineering-rigor`, `subagent-driven-development`, `test-driven-development`, `receiving-code-review`, and `verification-before-completion` as needed.
2. Create feature branch `feat/source-ingest-conversation-authoring` from `main`.
3. Follow TDD task-by-task from the implementation plan.
4. Commit incrementally after each task.
5. Use two-stage review: spec compliance first, code quality second.
6. Run final verification before completion.
7. Push branch; do not merge to `main` until tests/review pass.

## Source artifacts

Read these files first:

- Design: `docs/plans/2026-05-28-source-ingest-and-conversation-authoring-design.md`
- Plan: `docs/plans/2026-05-28-source-ingest-and-conversation-authoring-implementation-plan.md`
- Existing apply code: `src/hermes_memory_wiki/apply.py`
- Existing tools code: `src/hermes_memory_wiki/tools.py`
- Existing markdown helpers: `src/hermes_memory_wiki/markdown.py`
- Existing tests: `tests/test_apply.py`, `tests/test_tools.py`, `tests/test_smoke_workflow.py`, `tests/test_skills.py`

## Decisions already made

- Keep tools deterministic; no hidden LLM calls inside `wiki_apply` or `wiki_ingest`.
- The agent/LLM decides what summaries, claims, and mutations to send.
- Add `wiki_ingest` for source-page creation/refresh.
- Support `local-file` and `conversation-summary` source types. Generic `text` source is desirable and included in the plan unless implementation uncovers a reason to defer.
- Extend `wiki_apply` with typed deterministic `upsert_entity` and `upsert_concept` ops.
- Do not expose arbitrary freeform page writes.
- Compile after ingest/apply writes. Do not auto-reindex unless later explicitly requested.
- Preserve human notes and existing page ids on refresh.

## Non-goals

- No OpenClaw bridge mode.
- No unsafe-local import.
- No internal LLM summarizer.
- No generic arbitrary page upsert.
- No dependence on OpenClaw runtime.

## Verification commands

Run at minimum:

```bash
python -m compileall src tests
python -m pytest -q
```

Focused commands from the plan:

```bash
python -m pytest tests/test_ingest.py -q
python -m pytest tests/test_apply.py -q
python -m pytest tests/test_tools.py -q
python -m pytest tests/test_skills.py -q
```

## Pasteable prompt for clean execution chat

```text
Implement the source ingest and conversation authoring feature in /home/langley/projects/hermes-memory-wiki. First load the relevant software-development skills, then read docs/plans/2026-05-28-source-ingest-and-conversation-authoring-design.md and docs/plans/2026-05-28-source-ingest-and-conversation-authoring-implementation-plan.md. Follow the plan task-by-task using TDD and subagent-driven-development. Create branch feat/source-ingest-conversation-authoring from main, commit incrementally, and do not merge to main. Key requirements: add deterministic wiki_ingest for local-file and conversation-summary sources; extend wiki_apply with deterministic typed upsert_entity and upsert_concept; preserve human notes and existing ids; compile after writes; update README/docs/skills; no hidden internal LLM calls; no arbitrary freeform page-write tool. Verify with python -m compileall src tests and python -m pytest -q, then perform spec-compliance and code-quality review before reporting completion.
```
