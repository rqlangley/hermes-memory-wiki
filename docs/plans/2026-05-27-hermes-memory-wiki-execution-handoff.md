# hermes-memory-wiki Execution Handoff

**Date:** 2026-05-27  
**Last updated:** 2026-05-27 after Task 6.1

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

The feature branch exists and has been pushed to origin through Task 6.1 after verification, review, and handoff update.

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
fcd922e feat: add wiki keyword search modes
021eb6f fix: boost wiki source evidence text matches
79f80a8 fix: validate empty keyword search modes
7a5614a feat: add embedding provider interface
a42cc69 fix: harden embedding response validation
5a68569 fix: validate embedding response indexes
845f673 docs: update handoff after embedding provider
179827a docs: include handoff update commit
affbad6 feat: build wiki vector search documents
425d4aa feat: persist wiki vector index in sqlite
ff52a71 fix: close vector index sqlite connections
4d2fa1d docs: update handoff after vector index storage
4132993 feat: reindex wiki embeddings incrementally
f74e076 fix: protect reindex state on embedding diagnostics
186fad7 fix: apply reindex updates atomically
32649ab docs: update handoff after reindex workflow
36dff49 feat: search wiki vector index
3dac371 fix: preserve vector search diagnostics
a3c9286 docs: update handoff after vector search
c40d332 feat: add hybrid wiki search
579f2d6 fix: make hybrid search tests environment-independent
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

### Task 4.3 — Add search modes

Files:

- `src/hermes_memory_wiki/search_keyword.py`
- `tests/test_keyword_search.py`

Implemented:

- search mode validation for `auto`, `find-person`, `route-question`, `source-evidence`, and `raw-claim`
- mode-specific boosts for person-like pages, route/best-used-for fields, source/evidence metadata, and raw claim matches
- `route-question` mode can qualify pages from route fields even when general page text does not match
- unsupported modes raise `ValueError`, including empty-result `keyword_search(...)` calls

Covered behavior:

- `find-person` boosts person-like pages and identifier/alias/person-name matches
- `route-question` boosts routing and best-used-for matches
- `source-evidence` boosts source pages and evidence kind/source/path/line/note/text matches
- `raw-claim` prioritizes pages with matching claims
- invalid modes raise predictably

Review results:

- Spec compliance: PASS after scoped evidence-text fix
- Code quality: APPROVED after scoped empty-search validation polish

### Task 5.1 — Define embedding provider interface and fake provider

Files:

- `src/hermes_memory_wiki/embeddings.py`
- `tests/test_embeddings.py`

Implemented:

- `EmbeddingProvider` protocol with `provider`, `model`, `dimensions`, and `embed_texts(...)`.
- `FakeEmbeddingProvider` with deterministic offline vectors and stable dimensions.
- `OpenAIEmbeddingProvider` using `EmbeddingConfig` defaults, `OPENAI_API_KEY` by default, configurable env var/model/batch size/timeout, and injectable stdlib `urllib` transport.
- `/v1/embeddings` calls are made only from `embed_texts(...)`.
- batching preserves input order.
- clear missing API key diagnostic including provider, model, and env var.
- OpenAI response validation rejects malformed JSON, non-object/non-list shapes, embedding count mismatches, duplicate/out-of-range indexes, missing/non-list embeddings, and non-numeric embedding values.

Covered behavior:

- fake provider returns deterministic vectors;
- fake provider vector dimensions are stable;
- OpenAI provider reports clear missing API key diagnostics;
- OpenAI batching preserves order;
- malformed OpenAI responses raise contextual `RuntimeError`s rather than leaking low-level exceptions;
- duplicate/out-of-range OpenAI response indexes are rejected.

Review results:

- Spec compliance: PASS
- Code quality: APPROVED after scoped response-validation and index-validation fixes

Non-blocking notes:

- `OpenAIEmbeddingProvider.dimensions` is accepted but not inferred from live responses yet; later vector index integration may establish a stronger dimension contract.
- Response index validation uses `isinstance(index, int)`; JSON booleans would currently pass the integer check because `bool` subclasses `int` in Python. This is malformed-response hardening only and was accepted as a minor non-blocking quality note.

### Task 5.2 — Build search documents

Files:

- `src/hermes_memory_wiki/vector_index.py`
- `tests/test_vector_index.py`

Implemented:

- `SearchDocument` dataclass with deterministic document metadata.
- `build_search_documents(...)` for page-level and claim-level embedding/search documents.
- Stable page document IDs using `page:<path>`.
- Stable claim document IDs using explicit claim IDs where present and deterministic ordinal/hash fallback otherwise.
- SHA-256 `text_hash` values derived from document text.
- Page document text containing title, path, kind, aliases, source IDs, claims, questions, contradictions, and cleaned body text.
- Claim document text containing page title/path, claim ID/text/status/confidence, page source IDs, and evidence source/kind/path/line/note/text fields.
- Body cleanup that excludes frontmatter and Hermes/OpenClaw generated related blocks.

Covered behavior:

- page document includes title/path/kind/claims/questions/body;
- claim document includes claim text, page title, source IDs, and evidence;
- document IDs are deterministic;
- text hash changes when text changes;
- generated related blocks and frontmatter are excluded from body text.

Review results:

- Spec compliance: PASS
- Code quality: APPROVED

Non-blocking notes:

- `tests/test_vector_index.py` hardcodes the exact fallback short hash for one deterministic ID assertion; accepted as a minor test brittleness note because it documents the current stable ID contract.

### Task 5.3 — Implement SQLite vector index storage

Files:

- `src/hermes_memory_wiki/vector_index.py`
- `tests/test_vector_index.py`

Implemented:

- `StoredEmbedding` dataclass for loaded vector index records.
- `VectorIndex` SQLite storage wrapper with parent directory creation and schema initialization.
- SQLite `documents` and `embeddings` tables using the approved v1 schema.
- SQLite indexes `idx_documents_page_path` and `idx_embeddings_provider_model`.
- `upsert_documents(...)` for deterministic document persistence and stale document deletion.
- `stale_documents_for_embedding(...)` to select documents missing current provider/model/dimension/hash embeddings.
- `store_embeddings(...)` with JSON vector storage, embedded timestamp handling, length mismatch validation, and declared dimension validation.
- `load_embeddings(...)` for deterministic provider/model/dimension-filtered embedding retrieval.
- Explicit SQLite connection closing via an internal context manager and regression coverage for connection/file descriptor leaks.

Covered behavior:

- creates SQLite schema;
- upserts documents;
- stores embeddings as JSON;
- rejects embedding count mismatches;
- rejects declared dimension mismatches before writing rows;
- skips unchanged embeddings by hash/provider/model;
- marks changed hash/model/dimensions as stale;
- deletes stale documents no longer present and cascades stale embeddings;
- loads all embeddings for a provider/model in deterministic order;
- closes SQLite connections after repeated operations.

Review results:

- Spec compliance: PASS
- Code quality: APPROVED after scoped connection-close and dimension-validation fixes

Non-blocking notes:

- The approved schema keys embeddings by `document_id`, so storing a different provider/model for the same document overwrites the previous embedding. This matches Task 5.3/design v1 but remains a future limitation if concurrent multiple embedding models are required.

### Task 5.4 — Implement reindex workflow

Files:

- `src/hermes_memory_wiki/vector_index.py`
- `tests/test_reindex.py`

Implemented:

- `ReindexResult` dataclass for embedded/skipped/deleted counts, provider/model/dimensions, and diagnostics.
- `reindex_vault(...)` workflow that reads queryable pages, builds page/claim search documents, plans stale documents without mutating the index, embeds only required documents, and stores updates in SQLite.
- Default vector index path at `<vault>/.hermes-wiki/vector/index.sqlite`.
- Default OpenAI provider construction from `MemoryWikiConfig.embeddings`.
- Known OpenAI embedding dimensions for `text-embedding-3-small`, `text-embedding-3-large`, and `text-embedding-ada-002` so default OpenAI reindex can perform dimension-aware stale checks.
- Missing API key diagnostics before any SQLite mutation for default OpenAI reindex.
- Atomic document sync plus embedding storage after successful embedding calls; provider/storage failures return diagnostics without mutating existing document or embedding rows.
- Deletion counting for documents no longer present in the vault.

Covered behavior:

- first reindex embeds all current page and claim documents;
- second reindex skips unchanged documents;
- `force=True` re-embeds unchanged documents;
- changed page text re-embeds only changed documents;
- deleted pages are counted and removed after successful reindex;
- missing OpenAI API key returns a diagnostic without deleting or mutating existing index rows;
- provider embedding failures return typed diagnostics and leave existing index rows unchanged.

Review results:

- Initial spec compliance: FAIL; fixed missing-key mutation, missing regression coverage, and default OpenAI dimension-aware stale checks.
- Spec compliance after fixes: PASS.
- Initial code quality: REQUEST_CHANGES; fixed atomicity so provider/storage failures do not partially mutate the index.
- Code quality after fixes: APPROVED.

Non-blocking notes:

- On provider failure, `deleted_count` currently reports the planned deletion count even though no mutation is applied. This is acceptable for Task 5.4 because diagnostics indicate failure and the persisted index remains unchanged; a future API polish pass may separate planned and applied deletion counts.

### Task 5.5 — Implement vector search

Files:

- `src/hermes_memory_wiki/vector_index.py`
- `tests/test_vector_search.py`

Implemented:

- `VectorSearchResults` list-compatible result carrier with observable diagnostics for later hybrid fallback.
- `cosine_similarity(...)` with zero-vector handling and dimension-mismatch errors.
- `vector_search(...)` over persisted `VectorIndex` embeddings using provider/model matching and query embedding.
- Page and claim `WikiSearchResult` conversion with snippets, vector metadata, search mode, scores, and matched claim IDs.
- Missing index, empty initialized index, disabled/unavailable embeddings, and non-positive max-results behavior return empty list-compatible results without unnecessary query embedding calls.
- Dimension mismatches between query and stored embeddings raise a clear `ValueError`.

Covered behavior:

- cosine similarity ranks expected fake vectors;
- vector search embeds query once;
- returns page and claim results with snippets and metadata;
- missing and empty indexes are graceful and preserve diagnostics;
- provider/config unavailability preserves diagnostics without network access;
- successful vector search exposes empty diagnostics;
- dimension mismatch is diagnosed.

Review results:

- Initial spec compliance: FAIL; fixed missing true empty-index coverage and discarded diagnostics.
- Spec compliance after fixes: PASS.
- Code quality: APPROVED.

Non-blocking notes:

- Query embedding failures currently propagate directly instead of returning diagnostics; acceptable for Task 5.5 because provider failures during query-time search should be surfaced clearly and hybrid fallback handling is Task 6.1.
- Stored embeddings are loaded provider/model-wide and dimension mismatches fail the search; future hybrid fallback may choose to skip incompatible stale rows instead.

### Task 6.1 — Implement score normalization and rank fusion

Files:

- `src/hermes_memory_wiki/hybrid_search.py`
- `tests/test_hybrid_search.py`

Implemented:

- `SearchDiagnostics` dataclass for requested/effective search mode, vector availability, and diagnostic messages.
- `search_wiki(...)` entry point for keyword, vector, and hybrid search modes.
- Default search mode resolution from `MemoryWikiConfig.search.default_search_mode`, including `auto` normalization to `hybrid` when needed.
- Keyword-only search using `read_queryable_pages(...)` and `keyword_search(...)` without API keys.
- Vector-only search using `vector_search(...)` and propagating `VectorSearchResults.diagnostics`.
- Hybrid score fusion using normalized keyword/vector scores and configured lexical/vector weights.
- Fusion by page path plus matched claim/document identity to avoid merging distinct claim hits incorrectly.
- Hybrid fallback to keyword with clear diagnostics when vector search is unavailable.

Covered behavior:

- keyword-only results are returned when vector unavailable;
- vector-only results are returned for vector mode;
- hybrid combines same page/claim hits by path and claim id;
- lexical/vector weights are respected;
- mode boosts remain applied;
- diagnostics explain fallback;
- tests are deterministic whether `OPENAI_API_KEY` is set or unset;
- `search_mode="auto"` with config default `auto` normalizes to hybrid behavior.

Review results:

- Spec compliance: PASS.
- Initial code quality: REQUEST_CHANGES; fixed ambient `OPENAI_API_KEY` test dependency and `auto` default handling.
- Code quality after fixes: APPROVED.

Non-blocking notes:

- Hybrid score metadata currently records normalized component scores and search type provenance for fused results; future UI/tool formatting can decide how much of that metadata to expose.

## Latest verification

Use `.venv/bin/python`; bare `python` is not available on this host.

Latest verification after Task 6.1:

```bash
.venv/bin/python -m pytest tests/test_hybrid_search.py -q
# 7 passed

OPENAI_API_KEY='***' .venv/bin/python -m pytest tests/test_hybrid_search.py -q
# 7 passed

.venv/bin/python -m pytest tests/test_keyword_search.py tests/test_vector_search.py tests/test_hybrid_search.py -q
# 37 passed

.venv/bin/python -m pytest -q
# 114 passed

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

Continue with **Task 7.1 — Implement lookup and `wiki_get` core** from the implementation plan.

Files:

- modify `src/hermes_memory_wiki/vault.py`
- create `tests/test_get.py`

Required TDD test cases:

- exact path lookup;
- lookup without `.md`;
- basename lookup;
- frontmatter id lookup;
- title lookup;
- claim id lookup returns parent page;
- line slicing returns expected content/truncated flag.

Implementation notes:

- expose `GetPageResult` and `get_page(...)` as specified in the implementation plan;
- use existing path safety helpers and queryable page readers where appropriate;
- preserve vault-root read safety; do not follow unsafe symlink paths;
- return excerpts/content without frontmatter by default per design;
- do not implement `wiki_get` Hermes tool registration yet (Task 8.1).

Expected commit message:

```text
feat: resolve and read wiki pages
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
