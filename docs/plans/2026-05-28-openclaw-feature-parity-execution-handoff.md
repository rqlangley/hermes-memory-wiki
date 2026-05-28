# Execution Handoff: OpenClaw Feature Parity for Hermes Memory Wiki

## Goal

Correct the `hermes-memory-wiki` plugin so its local wiki data model, generated vault guidance, compile outputs, lint rules, search/get/apply behavior, tools, docs, and skills mirror OpenClaw `memory-wiki` as closely as practical while remaining a native Hermes Python plugin. This is a clean-slate correction: do not preserve the current divergent behavior where entity subtypes are stored as broad `pageType` values.

## Source Artifacts

- Implementation plan: `docs/plans/2026-05-28-openclaw-feature-parity-implementation-plan.md`
- Prior design: `docs/plans/2026-05-27-hermes-memory-wiki-design.md`
- Original implementation plan: `docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md`
- Original execution handoff: `docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md`
- Source inventory: `docs/references/openclaw-memory-wiki-source-inventory.md`
- OpenClaw reference source:
  - `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js`
  - `/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js`
  - `/home/langley/.npm-global/lib/node_modules/openclaw/dist/config-U1dUmpXj.js`
  - `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md`

## Repository

- Path: `/home/langley/projects/hermes-memory-wiki`
- Base branch: `main`
- Feature branch: `feature/openclaw-memory-wiki-parity`
- Current planning files were written on `main`; implementation must begin by creating/switching to the feature branch.

## Approved Decisions

- Use Option A: strict OpenClaw semantic parity, Hermes-native implementation.
- No runtime dependency on OpenClaw.
- No compatibility support for current divergent Hermes wiki pages.
- Keep `.hermes-wiki` naming instead of `.openclaw-wiki`.
- Keep Hermes vector/hybrid search as an additive feature, but index OpenClaw-compatible page/claim documents.
- Directory-derived broad page kinds are canonical:
  - `entities/` -> `entity`
  - `concepts/` -> `concept`
  - `syntheses/` -> `synthesis`
  - `sources/` -> `source`
  - `reports/` -> `report`
- `pageType` is required and must match the broad kind.
- Entity subtype belongs in `entityType`, e.g. `pageType: entity`, `entityType: person`.
- Claims are structured frontmatter with evidence; there is no top-level `claims/` directory.

## Explicit Non-Goals

- Do not support `entities/*.md` with `pageType: person` as valid.
- Do not add legacy compatibility/migration behavior.
- Do not add OpenClaw bridge-mode runtime dependency.
- Do not edit Hermes core.
- Do not require live OpenAI credentials for default tests.
- Do not merge to `main` before final verification and review gates pass.

## Required Skills / Workflow

Use:

- `software-engineering-rigor`
- `hermes-plugin-porting`
- `test-driven-development`
- `subagent-driven-development`
- `receiving-code-review`
- `verification-before-completion`
- `systematic-debugging` if failures occur

Workflow:

1. Read this handoff.
2. Read the implementation plan in full.
3. Re-check repo state.
4. Create/switch to `feature/openclaw-memory-wiki-parity`.
5. Implement task-by-task with strict TDD:
   - write failing tests;
   - verify RED;
   - implement minimal code;
   - verify GREEN;
   - run relevant broader tests;
   - commit.
6. Use implementation subagents for focused task groups where appropriate.
7. After implementation tasks, run spec compliance review first.
8. After spec compliance passes, run code quality review.
9. Handle review feedback through `receiving-code-review` with scoped fix commits.
10. Run final verification fresh.
11. Push branch and merge to `main` only after validation.

## Implementation Phases

Follow the exact plan at:

```text
/home/langley/projects/hermes-memory-wiki/docs/plans/2026-05-28-openclaw-feature-parity-implementation-plan.md
```

Phase summary:

1. Refresh source/parity inventory.
2. Correct schema and page-kind model.
3. Align lint behavior with OpenClaw.
4. Expand vault init and generated guidance.
5. Align compile outputs and reports.
6. Align `wiki_apply`, `wiki_get`, keyword/hybrid/vector search.
7. Decide/implement source ingest parity if current port has partial support.
8. Update docs and bundled/native skills.
9. Correct tool/plugin integration metadata.
10. Add end-to-end parity smoke workflow.
11. Run spec compliance review.
12. Run code quality review.
13. Final verification, push, merge/PR.

## Critical File Paths

Primary source files:

```text
src/hermes_memory_wiki/vault.py
src/hermes_memory_wiki/schema.py
src/hermes_memory_wiki/compile.py
src/hermes_memory_wiki/lint.py
src/hermes_memory_wiki/apply.py
src/hermes_memory_wiki/search_keyword.py
src/hermes_memory_wiki/vector_index.py
src/hermes_memory_wiki/hybrid_search.py
src/hermes_memory_wiki/tools.py
src/hermes_memory_wiki/plugin.py
```

Skills:

```text
src/hermes_memory_wiki/skills/wiki-search/SKILL.md
src/hermes_memory_wiki/skills/wiki-authoring/SKILL.md
src/hermes_memory_wiki/skills/wiki-maintainer/SKILL.md
```

Docs:

```text
docs/schema.md
docs/openclaw-feature-parity.md
docs/references/openclaw-memory-wiki-source-inventory.md
docs/configuration.md
docs/development.md
docs/installation.md
```

Tests likely affected:

```text
tests/test_schema.py
tests/test_lint.py
tests/test_compile.py
tests/test_vault_init.py
tests/test_apply.py
tests/test_keyword_search.py
tests/test_hybrid_search.py
tests/test_get.py
tests/test_vector_index.py
tests/test_tools.py
tests/test_skills.py
tests/test_smoke_workflow.py
scripts/smoke_fake_hermes.py
```

## Verification Commands

Targeted commands are listed in the implementation plan. Final verification must include:

```bash
python -m pytest -q
python -m compileall src tests scripts
python scripts/smoke_fake_hermes.py
```

If editable install verification is appropriate:

```bash
python -m pip install -e .
python -m pytest -q
```

Optional live OpenAI tests only when explicitly enabled:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" pytest tests/live -v
```

Do not print secrets. Do not require live tests for default completion.

## Review Prompts

### Spec compliance reviewer prompt

```text
Review /home/langley/projects/hermes-memory-wiki on branch feature/openclaw-memory-wiki-parity for compliance with docs/plans/2026-05-28-openclaw-feature-parity-implementation-plan.md.

Focus only on OpenClaw parity/spec compliance first. Compare behavior against the referenced OpenClaw source inventory and source files. Verify: directory-derived broad page kind, pageType matching broad kind, entityType for entity subtypes, structured claim/evidence schema, generated starter guidance, compile outputs/reports/digests, lint categories/errors/warnings, apply/get/search/tool metadata, docs, and bundled skills.

Do not do general style review unless it affects spec compliance. Return concrete issues with file paths and line references. If no issues, say spec compliance passed and list verification commands you inspected or ran.
```

### Code quality reviewer prompt

```text
Review /home/langley/projects/hermes-memory-wiki on branch feature/openclaw-memory-wiki-parity after spec compliance has passed.

Focus on code quality, maintainability, deterministic tests, path safety, no live network in default tests, no runtime dependence on OpenClaw, no unnecessary compatibility shims, and Hermes plugin integration cleanliness. Return concrete issues with file paths and line references. If no issues, say code quality review passed and list verification commands you inspected or ran.
```

## Paste-Into-New-Chat Prompt

```text
Please execute the implementation handoff at:

/home/langley/projects/hermes-memory-wiki/docs/plans/2026-05-28-openclaw-feature-parity-execution-handoff.md

Use software-engineering-rigor, hermes-plugin-porting, test-driven-development, subagent-driven-development, receiving-code-review, systematic-debugging when needed, and verification-before-completion.

Start from a clean context. Treat the handoff and implementation plan as the source of truth. The approved direction is Option A: strict OpenClaw semantic parity with a Hermes-native implementation and no legacy compatibility support. Use branch feature/openclaw-memory-wiki-parity. Implement task-by-task with TDD, commit incrementally, run spec compliance review before code quality review, push to origin, and merge to main only after final verification passes.
```

## Completion Criteria

- Implementation plan followed or deviations documented and justified.
- Tests cover OpenClaw-compatible schema, lint, compile, apply, search/get, tool behavior, skills/docs, and smoke workflow.
- Default test suite passes without network credentials.
- Spec compliance review passes before code quality review.
- Final verification passes fresh.
- Branch is pushed and merged/PR-created only after validation.
