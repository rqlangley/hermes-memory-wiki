# hermes-memory-wiki Execution Handoff

**Date:** 2026-05-27  
**Last updated:** 2026-05-27 after Task 11.1

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

The feature branch exists and has been pushed to origin through Task 11.1 after verification, review, and handoff update.

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
9bee2de docs: update handoff after hybrid search
e6812ef feat: resolve and read wiki pages
c41ca28 docs: update handoff after wiki get
aff7ffe feat: create wiki synthesis mutations
86b9186 fix: accept create synthesis op mutations
e33cd7a fix: validate synthesis mutation fields
3981671 docs: update handoff after synthesis mutations
d5160bf feat: update wiki page metadata
200c0d0 docs: update handoff after metadata mutations
10b1d34 feat: compile wiki indexes and caches
38ca9c3 fix: harden wiki compile outputs
308b590 docs: update handoff after wiki compile
0cf2b70 feat: lint wiki health and provenance
0972b13 fix: harden wiki lint checks
098bda0 docs: update handoff after wiki lint
56ff35d feat: register hermes wiki tools
97d7989 fix: use hermes tool schema keyword
65123b7 docs: update handoff after tool registration
e1fe2ee feat: add hermes user plugin layout
678f8ab docs: update handoff after plugin layout
559b413 feat: add memory wiki skills
5d2991c docs: update handoff after wiki skills
5c487ff docs: add installation and configuration guide
56f4b83 docs: clarify memory wiki config limitations
a327cf8 docs: update handoff after install docs
9306a5e docs: add development workflow
0cee728 docs: clarify development workflow guidance
ed4e9e1 docs: update handoff after development guide
ea3563e test: add wiki workflow smoke test
98c38ca fix: keep smoke workflow offline
2c27f02 docs: update handoff after smoke test
64f08f4 fix: reject unsafe vector reindex paths
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

### Task 7.1 — Implement lookup and `wiki_get` core

Files:

- `src/hermes_memory_wiki/vault.py`
- `tests/test_get.py`

Implemented:

- `GetPageResult` dataclass for resolved page metadata, content excerpt, line range metadata, total lines, truncation, and source `WikiPageSummary`.
- `get_page(...)` resolving queryable pages by exact relative path, path without `.md`, basename/stem, frontmatter id, title, and claim id.
- Frontmatter-free body excerpting from parsed page summaries.
- Line slicing with clamped `from_line`/`line_count`, `total_lines`, and `truncated` metadata.
- Read safety via existing queryable page listing/reading behavior, including symlinked query dirs/files being skipped and traversal-like lookup paths being rejected by path normalization.

Covered behavior:

- exact path lookup;
- lookup without `.md`;
- basename lookup;
- frontmatter id lookup;
- title lookup;
- claim id lookup returns parent page;
- line slicing returns expected content and truncation metadata;
- missing lookup returns `None`.

Review results:

- Spec compliance: PASS.
- Code quality: APPROVED.

Non-blocking notes:

- Additional future edge-case tests could cover clamped line ranges, traversal-looking lookups, and symlink exclusion specifically through `get_page(...)`; existing lower-level vault/path tests cover the safety primitives.

### Task 7.2 — Implement `create_synthesis` mutation

Files:

- `src/hermes_memory_wiki/apply.py`
- `tests/test_apply.py`

Implemented:

- `WikiMutation` and `ApplyResult` dataclasses.
- `normalize_mutation(...)` for `op: create_synthesis` mutations with required `title`, `body`, and non-empty `sourceIds`.
- `apply_mutation(...)` for creating/updating synthesis pages only; `update_metadata` remains deferred to Task 7.3.
- Deterministic synthesis slug/path generation under `syntheses/<slug>.md` and default id `synthesis.<slug>`.
- Frontmatter writing for id/title/pageType/sourceIds/claims/status/updatedAt plus optional questions, contradictions, and confidence.
- Generated summary block creation/replacement using Hermes managed markers.
- Human notes block creation and preservation on update.
- Safe writes under the configured vault root and queryable immediate `.md` synthesis path validation.

Covered behavior:

- title/body/sourceIds required;
- spec-compliant `op` discriminator accepted and unsupported ops rejected;
- deterministic synthesis path and default id;
- required and optional frontmatter fields written;
- generated summary block written;
- human notes block exists and is preserved on update;
- explicit invalid paths and invalid confidence values rejected.

Review results:

- Initial spec compliance: FAIL; fixed `op` vs `type` discriminator and optional field support.
- Spec compliance after fixes: PASS.
- Initial code quality: REQUEST_CHANGES; fixed contradiction text-list normalization, confidence validation, and explicit path queryability validation.
- Code quality after fixes: APPROVED.

### Task 7.3 — Implement `update_metadata` mutation

Files:

- `src/hermes_memory_wiki/apply.py`
- `tests/test_apply.py`

Implemented:

- `normalize_mutation(...)` support for `op: update_metadata` mutations.
- `apply_mutation(...)` dispatch for metadata-only updates.
- Existing page lookup via `get_page(...)` with clear missing-page errors.
- Frontmatter updates for title, sourceIds, claims, questions, contradictions, confidence, and status while preserving body content exactly.
- Empty list values remove list frontmatter fields such as claims; `confidence: null` removes confidence.
- `updatedAt` is refreshed on every metadata update.
- Safe writes through the resolved page path under the configured vault root.

Covered behavior:

- lookup required;
- missing page raises a clear error;
- sourceIds update replaces normalized source IDs;
- empty claims remove claims field;
- confidence null removes confidence;
- body is preserved;
- updatedAt changes.

Review results:

- Spec compliance: PASS.
- Code quality: APPROVED.

Non-blocking notes:

- Future hardening could add explicit update_metadata tests for symlink/path-traversal integration and decide whether lookup-only updatedAt-only mutations should be rejected.

### Task 7.4 — Implement compile cache and indexes

Files:

- `src/hermes_memory_wiki/compile.py`
- `tests/test_compile.py`

Implemented:

- `CompileResult` dataclass and `compile_vault(...)` entry point.
- Deterministic root `index.md` with page/claim counts and directory links.
- Deterministic query directory `index.md` files listing pages grouped by kind.
- `.hermes-wiki/cache/agent-digest.json` with page metadata and aggregate counts.
- `.hermes-wiki/cache/claims.jsonl` with one claim record per line, including stable claim-document correlation.
- `.hermes-wiki/cache/search-docs.jsonl` using existing page/claim search document generation.
- Idempotent writes that skip unchanged output content.
- Compile log append events only when generated output files update.
- Symlink hardening for generated output paths, cache/log directories, and log file writes.

Covered behavior:

- root index includes page counts;
- directory indexes list pages by kind;
- `agent-digest.json` includes pages and claim counts;
- `claims.jsonl` contains one claim per line;
- `search-docs.jsonl` contains page/claim docs;
- compile is idempotent if nothing changed;
- compile appends log when files update;
- generated output/cache/log symlinks are rejected without overwriting outside targets;
- anonymous claim records correlate with generated claim search documents.

Review results:

- Spec compliance: PASS.
- Initial code quality: REQUEST_CHANGES; fixed output symlink safety and anonymous claim/search-doc correlation.
- Spec compliance after fixes: PASS.
- Code quality after fixes: APPROVED.

### Task 7.5 — Implement lint

Files:

- `src/hermes_memory_wiki/lint.py`
- `tests/test_lint.py`

Implemented:

- `LintIssue` and `LintResult` dataclasses.
- `lint_vault(...)` entry point that reads queryable pages and writes deterministic lint reports.
- Health/provenance/schema checks for missing claim evidence, contradictions, open questions, low confidence, stale `updatedAt`, duplicate page ids, duplicate claim ids, invalid markdown, broken source/evidence links, and stale vector indexes.
- Vector index inspection using current search document hash conventions, with warnings for missing/changed/extra vector documents and unreadable/symlinked vector metadata.
- `.hermes-wiki/cache/lint-report.md` and `.hermes-wiki/cache/lint-report.json` report writing with idempotent content comparison.
- Symlink hardening for lint report outputs and vector metadata inspection.

Covered behavior:

- missing claim evidence creates provenance warning;
- contradictions create contradiction issue;
- questions create open-question issue;
- low confidence creates low-confidence issue;
- stale updatedAt creates stale issue;
- duplicate ids create schema error;
- duplicate claim ids create schema error;
- invalid markdown creates schema error;
- broken source links create broken-link issue;
- stale/missing/extra vector index state creates vector-index warning;
- lint report written as markdown and JSON;
- unchanged lint reports are idempotent;
- symlinked vector metadata is not followed outside the vault.

Review results:

- Spec compliance: PASS.
- Initial code quality: REQUEST_CHANGES; fixed vector metadata symlink safety and added robustness coverage.
- Spec compliance after fixes: PASS.
- Code quality after fixes: APPROVED.

### Task 8.1 — Register plugin tools

Files:

- `src/hermes_memory_wiki/tools.py`
- `src/hermes_memory_wiki/plugin.py`
- `tests/test_tools.py`

Implemented:

- `register(ctx)` registration flow for Hermes plugin contexts.
- Toolset constant `memory_wiki`.
- Hermes-compatible tool registration using `ctx.register_tool(..., schema=..., handler=...)`.
- Tool handlers for `wiki_init`, `wiki_status`, `wiki_search`, `wiki_get`, `wiki_apply`, `wiki_compile`, `wiki_reindex`, and `wiki_lint`.
- JSON string response shape with human-readable `text` and structured `details`.
- Schema required fields for `wiki_search.query`, `wiki_get.lookup`, and `wiki_apply.op`.
- Handlers delegate to existing core modules without adding new core behavior.

Covered behavior:

- `register(ctx)` registers all expected tools;
- every tool uses toolset `memory_wiki`;
- schemas expose required fields where relevant;
- handlers return JSON text and details;
- core workflow handlers call existing modules/functions using `vaultPath` override config;
- tests avoid live OpenAI/network calls via monkeypatching where needed.

Review results:

- Initial spec compliance: FAIL; fixed `input_schema` vs Hermes-compatible `schema` registration keyword.
- Spec compliance after fix: PASS.
- Code quality after fix: APPROVED.

### Task 8.2 — Add plugin manifest for user-plugin layout

Files:

- `plugin.yaml`
- root `__init__.py`
- `tests/test_user_plugin_layout.py`

Implemented:

- Root `plugin.yaml` standalone Hermes user-plugin manifest.
- Root `__init__.py` exposing `register` from `hermes_memory_wiki.plugin`.
- Manifest declaration for plugin `memory-wiki`, version `0.1.0`, kind `standalone`, and required tool list.

Covered behavior:

- root `__init__.py` exposes the package `register` entry point;
- `plugin.yaml` parses as YAML and exactly declares the expected plugin metadata and `provides_tools` list;
- no bundled skills or Task 8.3 behavior added.

Review results:

- Spec compliance: PASS.
- Code quality: APPROVED.

### Task 8.3 — Add plugin skills

Files:

- `src/hermes_memory_wiki/skills/wiki-maintainer/SKILL.md`
- `src/hermes_memory_wiki/skills/wiki-authoring/SKILL.md`
- `src/hermes_memory_wiki/skills/wiki-search/SKILL.md`
- `src/hermes_memory_wiki/plugin.py`
- `tests/test_skills.py`
- `tests/test_tools.py`

Implemented:

- Three plugin-bundled Hermes skill documents for maintenance, authoring, and search workflows.
- Plugin skill registration for `wiki-maintainer`, `wiki-authoring`, and `wiki-search` using package-relative skill paths.
- Test fake contexts updated to support `register_skill` while preserving tool registration tests.

Covered behavior:

- `register(ctx)` registers three skills;
- registered skill paths exist and point to expected `SKILL.md` files;
- skill docs have frontmatter, non-empty bodies, and descriptions;
- skill docs mention only existing Hermes memory-wiki tools;
- skill docs avoid OpenClaw/bridge/unsafe-local/Claude references.

Review results:

- Spec compliance: PASS.
- Code quality: APPROVED.

### Task 9.1 — Document installation and configuration

Files:

- `README.md`
- `docs/installation.md`
- `docs/configuration.md`

Implemented:

- README quick start, tool list, and links to installation/configuration docs.
- Installation guide covering editable pip install, user-plugin symlink/copy install, plugin enablement, toolset enablement, `OPENAI_API_KEY`, vault initialization, and first reindex.
- Configuration guide covering active Hermes plugin/toolset settings, supported per-call `vaultPath`, current user-plugin config limitations, Python library/default config shape, practical no-embeddings workflow, and available tools.

Covered behavior:

- documents install without modifying Hermes core;
- documents user-plugin layout under `~/.hermes/plugins/memory-wiki`;
- documents enabling `plugins.enabled: [memory-wiki]` and the `memory_wiki` toolset;
- documents setting `OPENAI_API_KEY` for vector indexing/search;
- documents how to avoid embeddings with current user-plugin handlers;
- documents `wiki_init` and first `wiki_reindex` workflow;
- documents that current user-plugin handlers do not automatically read `memory_wiki.*` Hermes config keys, avoiding unsupported runtime config claims.

Review results:

- Initial spec compliance: FAIL; fixed unsupported claims that `memory_wiki.*` Hermes config keys directly control current user-plugin runtime behavior.
- Spec compliance after fix: PASS.
- Code quality after fix: APPROVED.

### Task 9.2 — Add development guide

Files:

- `docs/development.md`

Implemented:

- Development guide for local workflow, test/contribution commands, live-test policy, source-reference guidance, privacy/security guidance, and release checklist.
- `.venv/bin/python` command convention documented throughout.
- Live OpenAI tests documented as opt-in/future when a `tests/live/` suite exists and explicit permission/API key are present.

Covered behavior:

- TDD expectations documented;
- standard focused/full test commands documented;
- live OpenAI opt-in command and safety requirements documented;
- source-reference notes documented;
- privacy/security notes documented;
- release checklist documented;
- contribution workflow uses generic placeholders rather than task-specific files.

Review results:

- Spec compliance: PASS.
- Initial code quality: REQUEST_CHANGES; fixed missing-`tests/live` command caveat and task-specific contribution examples.
- Code quality after fix: APPROVED.

### Task 10.1 — Add local plugin registration smoke test script

Files:

- `scripts/smoke_fake_hermes.py`
- `tests/test_smoke_workflow.py`

Implemented:

- Offline fake Hermes registration context for local smoke workflow tests.
- `run_smoke_workflow(...)` helper and CLI script that print JSON summary and return nonzero on failure.
- End-to-end tool workflow through `wiki_init`, `wiki_apply`, `wiki_compile`, `wiki_reindex`, `wiki_search`, `wiki_get`, and `wiki_lint`.
- Deterministic offline stubs/providers for reindex/search so the smoke workflow never calls live OpenAI/network providers, even when `OPENAI_API_KEY` is set or an existing vector index is present.

Covered behavior:

- plugin registers tools and skills with a fake context;
- smoke workflow creates a temporary/configured vault;
- synthesis page creation, compile, reindex, hybrid search request, page get, and lint all return JSON tool responses;
- CLI/manual summary is JSON-serializable;
- regression coverage protects against accidental live OpenAI/vector embedding during smoke workflow.

Review results:

- Spec compliance: PASS.
- Initial code quality: REQUEST_CHANGES; fixed live-provider risk in smoke search when using an existing vector-indexed vault.
- Code quality after fix: APPROVED.

### Task 11.1 — Spec compliance review

Files:

- `src/hermes_memory_wiki/vector_index.py`
- `tests/test_reindex.py`

Review checklist result:

- No OpenClaw runtime dependency: PASS.
- No bridge-mode implementation: PASS.
- Default vault path is `~/.hermes/wiki/main`: PASS.
- Toolset is `memory_wiki`: PASS.
- Tools include all required v1 tools: PASS.
- Keyword search works without API key: PASS.
- Vector search uses OpenAI embeddings when configured: PASS.
- Hybrid search degrades cleanly: PASS.
- Skills are registered and accurate: PASS.
- Writes are restricted to configured vault root: initial FAIL, fixed.
- Tests pass offline: PASS.

Fix implemented:

- `reindex_vault(...)` now rejects unsafe symlinked vector-index paths before constructing `VectorIndex` or calling the embedding provider.
- Added regression test for symlinked `.hermes-wiki/vector` directory ensuring no outside `index.sqlite` write and no provider embed calls.

Review results:

- Initial Task 11.1 spec compliance: FAIL; fixed `wiki_reindex` outside-vault write through symlinked vector directory.
- Spec compliance after fix: PASS.

## Latest verification

Use `.venv/bin/python`; bare `python` is not available on this host.

Latest verification after Task 11.1:

```bash
.venv/bin/python -m pytest tests/test_reindex.py -q
# 9 passed

.venv/bin/python -m pytest -q
# 195 passed

.venv/bin/python -m compileall src tests
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

Continue with **Task 11.2 — Code quality review** from the implementation plan.

Objective: review maintainability, security, test coverage, and ergonomics.

Checklist:

- [ ] Clear module boundaries.
- [ ] Small functions.
- [ ] No leaked API keys.
- [ ] No broad exception swallowing that hides user-facing errors.
- [ ] SQLite connections handled safely.
- [ ] Deterministic tests.
- [ ] No network access in default tests.
- [ ] Helpful diagnostics.

Expected outcome:

- APPROVED with evidence, or specific blocking issues to fix before Task 11.3.

Implementation note:

- This is a review task. Do not add code unless the review finds valid blocking issues and a scoped fix is needed.

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
