# hermes-memory-wiki Execution Handoff

**Date:** 2026-05-27  
**Last updated:** 2026-05-27 after Task 4.2

## Project

```text
/home/langley/projects/hermes-memory-wiki
```

Remote:

```text
https://github.com/rqlangley/hermes-memory-wiki
```

Feature branch:

```text
feat/initial-hermes-memory-wiki-plugin
```

## Source artifacts

Read these before implementing:

- `README.md`
- `docs/plans/2026-05-27-hermes-memory-wiki-design.md`
- `docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md`
- `docs/references/openclaw-memory-wiki-source-inventory.md`

The implementation plan remains the source of truth for task order and task-level acceptance criteria. This handoff tracks current execution state and environment-specific notes.

## Current implementation state

The feature branch exists, has been pushed to origin, and was clean/in sync after Task 4.2.

Completed commits:

```text
7ec0b7e chore: add python package skeleton
3af2c84 feat: add memory wiki config defaults
d16c59b feat: add vault path safety helpers
2555699 feat: parse and render wiki markdown
0267ccd feat: normalize wiki page summaries
2446d9a feat: preserve wiki managed and human blocks
a3f5c7c feat: initialize hermes wiki vault
4b24e01 fix: reject unsafe vault symlinks
49ffeab feat: read queryable wiki pages
496545e fix: ignore unsafe wiki page symlinks
1f18d13 feat: build wiki keyword search text
88b157c fix: include wiki body in keyword search text
fb9d7f4 feat: rank wiki keyword search results
```

Completed tasks:

### Task 0.1 — Python package skeleton

Files:

- `pyproject.toml`
- `src/hermes_memory_wiki/__init__.py`
- `src/hermes_memory_wiki/plugin.py`
- `tests/test_import.py`
- `.gitignore`

### Task 1.1 — Config defaults

Files:

- `src/hermes_memory_wiki/config.py`
- `tests/test_config.py`

Implemented:

- `RenderConfig`
- `SearchConfig`
- `EmbeddingConfig`
- `MemoryWikiConfig`
- `expand_path(...)`
- `load_config(...)`

Defaults include:

- vault path: `~/.hermes/wiki/main`
- search mode: `hybrid`
- OpenAI embedding model: `text-embedding-3-small`
- embeddings enabled by default
- API key env var: `OPENAI_API_KEY`

### Task 1.2 — Vault path safety helpers

Files:

- `src/hermes_memory_wiki/paths.py`
- `tests/test_paths.py`

Implemented:

- `normalize_relative_path(...)`
- `safe_join(...)`
- `to_display_path(...)`

Covered behavior:

- safe paths under root
- rejects `../outside.md`
- rejects absolute paths outside root
- Windows-style backslash normalization
- relative POSIX display paths

### Task 2.1 — Parse and render wiki markdown frontmatter

Files:

- `src/hermes_memory_wiki/markdown.py`
- `tests/test_markdown.py`
- `pyproject.toml` updated with `PyYAML>=6`

Implemented:

- `WikiMarkdown`
- `WikiMarkdownError`
- `parse_wiki_markdown(...)`
- `render_wiki_markdown(...)`

Covered behavior:

- parses markdown with YAML frontmatter
- parses markdown without frontmatter
- renders frontmatter/body with trailing newline
- preserves unknown/nested frontmatter fields
- body excludes frontmatter delimiters
- invalid YAML raises `WikiMarkdownError`

Review results:

- Spec compliance: PASS
- Code quality: APPROVED

Non-blocking notes:

- Parser/render behavior is currently LF-oriented; CRLF frontmatter delimiters are not recognized.
- `render_wiki_markdown(...)` does not wrap PyYAML serialization failures in `WikiMarkdownError`.

### Task 2.2 — Normalize wiki page summaries

Files:

- `src/hermes_memory_wiki/schema.py`
- `tests/test_schema.py`

Implemented:

- `WikiEvidence`
- `WikiClaim`
- `WikiPageSummary`
- `PersonCard`
- `page_kind_from_path(...)`
- `to_page_summary(...)`

Covered behavior:

- derives kind from `pageType` and path
- normalizes `id`, `title`, `sourceIds`, `aliases`
- defaults title from markdown H1 and id from kind/path stem
- normalizes claims with evidence
- ignores invalid claim/evidence objects safely
- normalizes questions and contradictions
- supports person-card-like and route-question fields

Review results:

- Spec compliance: PASS
- Code quality: APPROVED

Non-blocking notes:

- `to_page_summary(...)` is typed as `WikiPageSummary | None` but currently always returns a summary or raises from markdown parsing.
- Frozen dataclasses contain mutable list/dict fields; current usage is acceptable, but immutability is shallow.

### Task 2.3 — Preserve managed and human blocks

Files:

- `src/hermes_memory_wiki/markdown.py`
- `tests/test_markdown.py`

Implemented:

- `HERMES_GENERATED_START`
- `HERMES_GENERATED_END`
- `HERMES_HUMAN_START`
- `HERMES_HUMAN_END`
- OpenClaw compatibility marker constants
- `replace_managed_block(...)`
- `ensure_human_notes_block(...)`

Covered behavior:

- replaces Hermes generated blocks
- preserves Hermes human blocks
- recognizes OpenClaw generated and human markers
- adds missing Hermes human notes blocks
- preserves text outside generated blocks
- writes new/replaced generated blocks with Hermes markers

Review results:

- Spec compliance: PASS
- Code quality: APPROVED

Non-blocking notes:

- `_append_block(...)` normalizes trailing whitespace when appending a new block via `text.rstrip()`; acceptable for current markdown output, but adjust later if byte-for-byte preservation outside managed blocks becomes required.

### Task 3.1 — Initialize vault structure

Files:

- `src/hermes_memory_wiki/vault.py`
- `tests/test_vault_init.py`

Implemented:

- `METADATA_DIRECTORY = ".hermes-wiki"`
- `InitResult`
- `initialize_vault(...)`

Covered behavior:

- creates required vault directories and starter files
- uses `.hermes-wiki/cache` and `.hermes-wiki/vector`
- writes deterministic `state.json` from injected `now`
- creates and appends `log.jsonl` only when something changed
- second initialization is idempotent
- existing `inbox.md` content is not overwritten
- rejects symlinked managed paths to avoid writes outside the configured vault root

Review results:

- Spec compliance: PASS
- Code quality: APPROVED after scoped symlink-safety fix

### Task 3.2 — List and read queryable pages

Files:

- `src/hermes_memory_wiki/vault.py`
- `tests/test_vault_read.py`

Implemented:

- `QUERY_DIRS`
- `list_wiki_markdown_files(...)`
- `read_queryable_pages(...)`

Covered behavior:

- lists immediate `.md` files in query directories
- returns sorted relative POSIX paths
- excludes query directory `index.md` files
- ignores files outside query directories and missing query directories
- reads pages into `WikiPageSummary` objects with parsed raw markdown body/metadata
- skips invalid markdown pages without crashing
- skips symlinked query directories and page files to avoid reading outside the vault

Review results:

- Spec compliance: PASS
- Code quality: APPROVED after scoped symlink-read safety fix

### Task 4.1 — Build searchable text and snippets

Files:

- `src/hermes_memory_wiki/search_keyword.py`
- `tests/test_keyword_search.py`

Implemented:

- `build_query_tokens(...)`
- `build_page_search_text(...)`
- `build_snippet(...)`

Covered behavior:

- removes generated related blocks from snippet text
- removes frontmatter from snippet text
- query tokens deduplicate and ignore tiny tokens
- exact query line is chosen for snippets
- fallback snippets choose the first meaningful body line
- page search text includes summary fields, claims, evidence, and body text without generated blocks
- nested set values are rendered deterministically

Review results:

- Spec compliance: PASS after scoped body-search-text fix
- Code quality: APPROVED after scoped body-search-text and deterministic-set-order fixes

### Task 4.2 — Implement keyword scoring

Files:

- `src/hermes_memory_wiki/search_keyword.py`
- `tests/test_keyword_search.py`

Implemented:

- `WikiSearchResult`
- `score_page(...)`
- `keyword_search(...)`

Covered behavior:

- exact title matches outrank body-only matches
- id/path matches boost score
- claim text matches return matched claim metadata
- confidence boosts claim score
- stale/contested claims score lower than fresh active claims
- body occurrence boost is capped
- nonmatching pages score zero and are filtered

Review results:

- Spec compliance: PASS
- Code quality: APPROVED

Non-blocking notes:

- `keyword_search(..., max_results=<negative>)` currently follows Python slicing semantics; consider normalizing or validating non-positive values when result pagination behavior is hardened.

## Latest verification

Use `.venv/bin/python`; bare `python` is not available on this host.

Latest verification after Task 4.2:

```bash
.venv/bin/python -m pytest tests/test_keyword_search.py -q
# 15 passed

.venv/bin/python -m pytest -q
# 60 passed

.venv/bin/python -m compileall src tests
# passed

.venv/bin/python -m pip install -e .
# passed

.venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
# 0.1.0
```

## Approved design summary

Build **hermes-memory-wiki**, a native Hermes Agent plugin that adds memory-wiki tools and skills without modifying Hermes core.

Required capabilities:

- initialize/manage a markdown wiki vault;
- structured page schema for sources/entities/concepts/syntheses/reports;
- tools: `wiki_init`, `wiki_status`, `wiki_search`, `wiki_get`, `wiki_apply`, `wiki_lint`, `wiki_compile`, `wiki_reindex`;
- deterministic keyword search based on OpenClaw memory-wiki behavior;
- built-in optional OpenAI vector search from the beginning;
- hybrid search default when embeddings are available;
- graceful fallback to keyword search when embeddings/API key are unavailable;
- plugin-provided skills for maintenance, authoring, and search.

Non-goals:

- no OpenClaw bridge mode;
- no migration of existing OpenClaw wiki;
- no runtime dependency on OpenClaw;
- no automatic private session/memory ingestion;
- no Hermes core modifications.

## OpenClaw source references

OpenClaw files are reference-only. Do not import or shell out to them at runtime.

Inventory:

```text
docs/references/openclaw-memory-wiki-source-inventory.md
```

Primary local files:

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/config-U1dUmpXj.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/obsidian-vault-maintainer/SKILL.md
```

Key observed fact: OpenClaw memory-wiki local wiki search is keyword/scoring based. OpenClaw embeddings belong to shared memorySearch/memory-core; hermes-memory-wiki should implement its own wiki vector index using OpenAI.

## Next task

Continue with **Task 4.3 — Add search modes** from the implementation plan.

Files:

- modify `src/hermes_memory_wiki/search_keyword.py`
- modify `tests/test_keyword_search.py`

Required TDD test cases:

- `find-person` boosts person-like pages;
- `route-question` boosts pages with routing/best-used-for fields;
- `source-evidence` boosts source pages and evidence matches;
- `raw-claim` prioritizes pages with matching claims;
- invalid mode raises or defaults predictably.

Reference only:

- OpenClaw `cli-Cx8TeRn1.js:1725-1764`
- OpenClaw `cli-Cx8TeRn1.js:1766-1799`

Expected commit message:

```text
feat: add wiki keyword search modes
```

## Required workflow

Use strict software engineering workflow:

1. Start in `/home/langley/projects/hermes-memory-wiki`.
2. Verify branch and status:

   ```bash
   git status --short --branch
   ```

   Expected branch: `feat/initial-hermes-memory-wiki-plugin`.

3. Pull/rebase if needed.
4. Follow the implementation plan task-by-task.
5. Use TDD for every code task:
   - write failing test;
   - verify RED for expected reason;
   - implement minimal code;
   - verify GREEN;
   - run broader tests;
   - commit.
6. Use subagent-driven-development:
   - implementation subagent per task or small phase;
   - spec compliance review first;
   - code quality review second;
   - fix issues before proceeding.
7. Do not implement bridge mode or OpenClaw runtime imports.
8. Push branch after successful tasks or milestones.
9. Open PR only after final verification for the initial plugin implementation.

## Verification commands

Use `.venv/bin/python` on this host.

For each focused task, run the targeted tests from the implementation plan plus the full suite:

```bash
.venv/bin/python -m pytest -q
```

Before claiming a milestone complete, run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall src tests
.venv/bin/python -m pip install -e .
.venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
git status --short --branch
```

Optional live OpenAI embeddings test only if explicitly allowed and an API key is configured:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live -v
```

## Minimal pasteable fresh-chat prompt

```text
Continue implementing hermes-memory-wiki.

Project: /home/langley/projects/hermes-memory-wiki
Branch: feat/initial-hermes-memory-wiki-plugin

Before acting, load: software-engineering-rigor, hermes-agent, subagent-driven-development, test-driven-development, verification-before-completion, requesting-code-review, receiving-code-review, github-pr-workflow.

Read and follow:
/home/langley/projects/hermes-memory-wiki/docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md

Use the handoff, design, implementation plan, and source inventory as the source of truth. Start by checking `git status --short --branch`, then continue with the next incomplete task using strict TDD, spec review before quality review, incremental commits, verification, and push to origin after successful milestones.
```
