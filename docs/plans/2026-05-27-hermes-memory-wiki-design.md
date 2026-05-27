# hermes-memory-wiki Design

**Date:** 2026-05-27

**Status:** Approved direction from user conversation. The user explicitly agreed with the proposed native Hermes plugin approach, requested vector search from the beginning, requested no OpenClaw bridge-mode port, requested no migration of the existing OpenClaw wiki, and requested this new project/repo.

## Goal

Build **hermes-memory-wiki**, a native Hermes Agent plugin that adds tools and skills for maintaining a persistent markdown memory wiki with structured pages, source-backed claims, generated indexes/dashboards, linting, and built-in hybrid keyword + OpenAI-vector search.

The plugin should provide the practical wiki-management capabilities of OpenClaw memory-wiki while being additive and reversible for Hermes: installable as a user plugin and activatable through Hermes plugin/tool configuration, with no modification to the default Hermes source install.

## Non-goals

1. **No OpenClaw bridge-mode port.** Do not import OpenClaw memory-core artifacts, dream reports, daily notes, event logs, or session memory.
2. **No migration of the existing OpenClaw wiki.** The OpenClaw vault at `~/.openclaw/wiki/main` is reference material only.
3. **No runtime dependency on OpenClaw.** OpenClaw bundled JS files may be inspected during implementation, but hermes-memory-wiki must run without OpenClaw installed.
4. **No large external vector database for v1.** Use local SQLite and brute-force cosine initially. Add sqlite-vec/FAISS/LanceDB later only if needed.
5. **No automatic private-session ingestion.** Future import/bridge workflows require separate design because of privacy implications.
6. **No modification of Hermes core for v1.** Package as a user plugin under `~/.hermes/plugins/memory-wiki` or pip-installable plugin with `hermes_agent.plugins` entry point.

## Primary users and use cases

### User stories

1. As a Hermes user, I can initialize a clean wiki vault for durable knowledge notes.
2. As a Hermes user, I can ask Hermes to search the wiki semantically and lexically before answering questions that depend on accumulated knowledge.
3. As a Hermes user, I can retrieve exact wiki pages or excerpts by id, path, title, or claim id.
4. As a Hermes user, I can ask Hermes to file a new source-backed synthesis without hand-editing generated markdown blocks.
5. As a Hermes user, I can ask Hermes to update claims/questions/contradictions/status/confidence metadata on an existing page.
6. As a Hermes user, I can run a lint pass to surface provenance gaps, contradictions, open questions, stale claims/pages, and low-confidence material.
7. As a Hermes user, I can recompile indexes/dashboards and rebuild the vector index after meaningful changes.
8. As a Hermes user, I can install wiki skills that teach the agent how to use these tools safely and consistently.

## Architecture overview

hermes-memory-wiki will be a Python package and Hermes plugin.

```text
Hermes Agent
  └─ plugin discovery
      └─ hermes-memory-wiki plugin
          ├─ registered tools under toolset: memory_wiki
          ├─ registered plugin skills
          ├─ wiki core library
          ├─ OpenAI embedding client
          └─ local vault/index files
```

### Repository/package layout

Proposed implementation layout:

```text
hermes-memory-wiki/
  README.md
  pyproject.toml
  src/hermes_memory_wiki/
    __init__.py
    plugin.py
    config.py
    paths.py
    markdown.py
    schema.py
    vault.py
    search_keyword.py
    embeddings.py
    vector_index.py
    hybrid_search.py
    apply.py
    compile.py
    lint.py
    tools.py
    skills/
      wiki-maintainer/SKILL.md
      wiki-authoring/SKILL.md
      wiki-search/SKILL.md
  tests/
    fixtures/
      vault_basic/
      vault_claims/
    test_config.py
    test_markdown.py
    test_vault_init.py
    test_keyword_search.py
    test_vector_index.py
    test_hybrid_search.py
    test_apply.py
    test_compile.py
    test_lint.py
    test_tools.py
  docs/
    plans/
    references/
```

For user-plugin installs, the same code can be copied/symlinked into:

```text
~/.hermes/plugins/memory-wiki/
  plugin.yaml
  __init__.py
```

For pip/plugin installs, expose an entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
memory-wiki = "hermes_memory_wiki.plugin"
```

The implementation should support both if practical.

## Hermes plugin integration

Hermes plugin APIs inspected in this environment:

```text
/home/langley/.hermes/hermes-agent/hermes_cli/plugins.py
```

Important API points:

- Directory plugins live under `~/.hermes/plugins/<name>/`.
- Each directory plugin needs `plugin.yaml` and `__init__.py` with `register(ctx)`.
- `ctx.register_tool(...)` registers tools in the global registry.
- Tools registered under a plugin toolset are visible through Hermes toolset resolution.
- `ctx.register_skill(...)` registers read-only namespaced plugin skills.
- Standalone user plugins are opt-in via `plugins.enabled` in Hermes config.

Recommended plugin key/name:

```yaml
name: memory-wiki
version: 0.1.0
kind: standalone
description: Hermes memory wiki tools with hybrid keyword/vector search.
provides_tools:
  - wiki_init
  - wiki_status
  - wiki_search
  - wiki_get
  - wiki_apply
  - wiki_compile
  - wiki_reindex
  - wiki_lint
```

Toolset name:

```text
memory_wiki
```

Plugin key for config activation:

```yaml
plugins:
  enabled:
    - memory-wiki
```

## Tool design

### `wiki_init`

Initialize the vault structure.

Parameters:

```json
{
  "vaultPath": "optional override path"
}
```

Behavior:

- Create root vault directory.
- Create standard directories:
  - `sources/`
  - `entities/`
  - `concepts/`
  - `syntheses/`
  - `reports/`
  - `.hermes-wiki/`
  - `.hermes-wiki/cache/`
  - `.hermes-wiki/vector/`
- Create initial files if missing:
  - `AGENTS.md`
  - `WIKI.md`
  - `index.md`
  - `inbox.md`
  - `.hermes-wiki/state.json`
  - `.hermes-wiki/log.jsonl`
- Never overwrite existing human content.

Return:

- root path;
- created directories;
- created files;
- whether anything changed.

Reference OpenClaw:

- `cli-Cx8TeRn1.js:473-508`.

### `wiki_status`

Inspect wiki configuration and health.

Parameters:

```json
{}
```

Return text summary and structured details:

- vault path;
- exists/initialized status;
- page counts by kind;
- cache/index status;
- vector index status;
- embedding provider/model/dimensions;
- embedding availability and missing API key diagnostics;
- last compile/reindex timestamps;
- lint issue count if recent lint report exists.

Reference OpenClaw:

- `extensions/memory-wiki/index.js:835-853`.

### `wiki_search`

Search wiki pages and claims using keyword, vector, or hybrid retrieval.

Parameters:

```json
{
  "query": "string, required",
  "maxResults": "integer optional, default 10",
  "mode": "auto | find-person | route-question | source-evidence | raw-claim",
  "searchMode": "keyword | vector | hybrid",
  "includeClaims": "boolean optional, default true"
}
```

Behavior:

- `keyword`: deterministic OpenClaw-like lexical/scoring search only.
- `vector`: semantic search over page/claim embedding docs only.
- `hybrid`: combine lexical and vector scores; degrade to keyword if embeddings unavailable.
- Return results with path/title/kind/score/snippet/searchMode/matchedClaim metadata.

Reference OpenClaw:

- `extensions/memory-wiki/index.js:854-884`.
- `cli-Cx8TeRn1.js:1376-1443`, `1461-1918`, `2023-2035`, `2170-2208`.

### `wiki_get`

Read a page or excerpt.

Parameters:

```json
{
  "lookup": "path, id, title, slug, or claim id",
  "fromLine": "integer optional, default 1",
  "lineCount": "integer optional, default 200"
}
```

Behavior:

- Resolve by exact relative path, path without `.md`, basename, frontmatter id, title, or claim id.
- Return body content excerpt without frontmatter by default, plus metadata.
- Include total lines and truncated flag.

Reference OpenClaw:

- `extensions/memory-wiki/index.js:946-985`.
- `cli-Cx8TeRn1.js:2209-2286`.

### `wiki_apply`

Apply structured mutations.

Parameters for `create_synthesis`:

```json
{
  "op": "create_synthesis",
  "title": "string",
  "body": "string",
  "sourceIds": ["string"],
  "claims": ["claim objects optional"],
  "contradictions": ["string optional"],
  "questions": ["string optional"],
  "confidence": "number 0..1 optional",
  "status": "string optional"
}
```

Parameters for `update_metadata`:

```json
{
  "op": "update_metadata",
  "lookup": "string",
  "sourceIds": ["string optional"],
  "claims": ["claim objects optional"],
  "contradictions": ["string optional"],
  "questions": ["string optional"],
  "confidence": "number 0..1 or null optional",
  "status": "string optional"
}
```

Behavior:

- Preserve human blocks.
- Preserve existing page body where appropriate.
- Write generated summary sections inside managed markers.
- Update frontmatter deterministically.
- Compile after mutation.
- Mark vector index stale; optionally reindex changed page if configured.

Reference OpenClaw:

- `extensions/memory-wiki/index.js:921-945`.
- `cli-Cx8TeRn1.js:2293-2450`.

### `wiki_compile`

Regenerate indexes, dashboards, claim digest, and search document cache.

Parameters:

```json
{
  "reindex": "boolean optional, default false"
}
```

Behavior:

- Initialize vault if needed.
- Read queryable pages.
- Refresh generated related blocks if enabled.
- Refresh dashboards if enabled.
- Refresh root and directory indexes.
- Write `.hermes-wiki/cache/agent-digest.json`.
- Write `.hermes-wiki/cache/claims.jsonl`.
- Write `.hermes-wiki/cache/search-docs.jsonl`.
- Optionally call reindex.

Reference OpenClaw:

- `cli-Cx8TeRn1.js:1283-1350`.

### `wiki_reindex`

Build or update vector index.

Parameters:

```json
{
  "force": "boolean optional, default false",
  "changedOnly": "boolean optional, default true"
}
```

Behavior:

- Ensure compile cache/search docs exist.
- Build document records from pages and claims.
- Hash each search document text.
- Skip embeddings whose hash/provider/model/dimensions match.
- Batch OpenAI embedding requests.
- Store vectors in SQLite.
- Return embedded/skipped/deleted counts and cost-relevant counts.

No OpenClaw equivalent exists for local wiki vector indexing; this is hermes-memory-wiki-specific.

### `wiki_lint`

Lint structural and knowledge-health issues.

Parameters:

```json
{}
```

Behavior:

- Compile first, or use compiled state if current.
- Issue categories:
  - `schema`
  - `provenance`
  - `contradictions`
  - `open-questions`
  - `low-confidence`
  - `stale`
  - `duplicates`
  - `broken-links`
  - `vector-index`
- Write markdown and JSON reports under `.hermes-wiki/reports/` or `reports/`.

Reference OpenClaw:

- `extensions/memory-wiki/index.js:885-920`.
- `cli-Cx8TeRn1.js:3260 onward`.

## Vault format

### Directories

```text
<root>/
  AGENTS.md
  WIKI.md
  index.md
  inbox.md
  sources/
    index.md
  entities/
    index.md
  concepts/
    index.md
  syntheses/
    index.md
  reports/
    index.md
  .hermes-wiki/
    state.json
    log.jsonl
    cache/
      agent-digest.json
      claims.jsonl
      search-docs.jsonl
    vector/
      index.sqlite
```

### Page kinds

- `source`
- `entity`
- `concept`
- `synthesis`
- `report`

### Frontmatter

Common fields:

```yaml
---
pageType: synthesis
id: synthesis.example-topic
title: Example Topic
sourceIds:
  - source.example
claims:
  - id: claim.example-topic.001
    text: Example claim.
    status: active
    confidence: 0.82
    evidence:
      - kind: source
        sourceId: source.example
        path: sources/example.md
        lines: L10-L15
        confidence: 0.82
questions:
  - What is still unknown?
contradictions: []
status: active
confidence: 0.82
updatedAt: "2026-05-27T00:00:00Z"
---
```

### Managed markers

To preserve compatibility with OpenClaw mental model, use similar marker semantics but Hermes-specific names for new vaults:

```html
<!-- hermes-wiki:generated:start -->
<!-- hermes-wiki:generated:end -->
<!-- hermes-wiki:human:start -->
<!-- hermes-wiki:human:end -->
```

Reader/writer should also recognize OpenClaw markers for compatibility if a user manually points at an OpenClaw-style vault:

```html
<!-- openclaw:wiki:generated:start -->
<!-- openclaw:wiki:generated:end -->
<!-- openclaw:human:start -->
<!-- openclaw:human:end -->
```

Do not overwrite human blocks.

## Search design

### Keyword search

Mirror OpenClaw local wiki behavior:

- tokenize query terms;
- search title/path/id/metadata/body/claims/questions/contradictions;
- exact title/id/path matches score highest;
- claim matches add score based on confidence/freshness/status;
- body occurrences add limited score;
- search modes apply boosts/filters.

Keyword search must work without network or API keys.

### Vector search

Vector search is built in from v1 and uses OpenAI embeddings by default.

Default model:

```text
text-embedding-3-small
```

Configurable model:

```yaml
memory_wiki:
  embeddings:
    provider: openai
    model: text-embedding-3-small
    api_key_env: OPENAI_API_KEY
    batch_size: 64
```

Behavior:

- Require `OPENAI_API_KEY` or configured env var for embedding calls.
- `wiki_search(searchMode=hybrid)` degrades to keyword if key/index unavailable.
- `wiki_reindex` reports a clear diagnostic if the key is missing.
- Embedding calls happen only during indexing and query-time vector search.
- Never send entire raw vault blindly; only generated search documents are embedded.

### Search documents

Index two document granularities:

1. Page documents:

```text
Title: ...
Path: ...
Kind: ...
Aliases: ...
Source IDs: ...
Claims: ...
Questions: ...
Contradictions: ...
Body: selected body text without generated related blocks/frontmatter
```

2. Claim documents:

```text
Page: ...
Claim ID: ...
Claim: ...
Status: ...
Confidence: ...
Evidence: source ids/kinds/notes/paths
```

### Vector index

Use SQLite for MVP.

Schema:

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  page_path TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  text TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  updated_at TEXT,
  metadata_json TEXT NOT NULL
);

CREATE TABLE embeddings (
  document_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  embedding_json TEXT NOT NULL,
  embedded_at TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_documents_page_path ON documents(page_path);
CREATE INDEX idx_embeddings_provider_model ON embeddings(provider, model);
```

For MVP, JSON vectors plus Python cosine similarity are acceptable. Later optimization can replace this with `sqlite-vec` while preserving the public tool behavior.

### Hybrid rank fusion

Compute:

```text
final_score = lexical_weight * normalized_keyword_score
            + vector_weight * normalized_vector_score
            + mode_boost
```

Defaults:

```yaml
memory_wiki:
  search:
    default_search_mode: hybrid
    lexical_weight: 0.45
    vector_weight: 0.55
```

If vector search is unavailable, use keyword-only and include a diagnostic in details.

## Config design

Default config:

```yaml
memory_wiki:
  vault_path: ~/.hermes/wiki/main
  render:
    preserve_human_blocks: true
    create_backlinks: true
    create_dashboards: true
  search:
    default_search_mode: hybrid
    lexical_weight: 0.45
    vector_weight: 0.55
  embeddings:
    enabled: true
    provider: openai
    model: text-embedding-3-small
    api_key_env: OPENAI_API_KEY
    batch_size: 64
    timeout_seconds: 60
```

Implementation should read Hermes config via Hermes config utilities when available. For unit tests, config loading must support explicit dict/path injection and environment overrides.

## Skills design

Ship at least three skills.

### `wiki-maintainer`

Use when maintaining or updating the wiki.

Guidance:

- Run `wiki_status` first when context is unknown.
- Use `wiki_search` before answering from stored wiki knowledge.
- Use `wiki_get` before citing or editing a page.
- Use `wiki_apply` for structured mutations.
- Run `wiki_lint` after meaningful updates.
- Run `wiki_compile` after structural changes.
- Run `wiki_reindex` when semantic search matters after content changes.
- Preserve human blocks.
- Keep claims source-backed.

### `wiki-authoring`

Use when creating pages or claims.

Guidance:

- Page type conventions.
- Frontmatter schema.
- Claim/evidence schema.
- Source-backed synthesis rules.
- Avoid duplicate entities/concepts.
- Confidence/status/freshness conventions.

### `wiki-search`

Use when retrieving wiki knowledge.

Guidance:

- Choose keyword/vector/hybrid.
- Use search modes intentionally.
- Follow `wiki_search` → `wiki_get` before relying on results.
- Interpret vector-search diagnostics.

## Testing strategy

Use TDD. Tests should not require OpenAI network access by default.

### Unit tests

- config normalization;
- path expansion;
- markdown frontmatter parse/render;
- marker preservation;
- vault initialization;
- keyword scoring;
- lookup resolution;
- apply mutation validation;
- compile cache generation;
- lint categories;
- vector index storage/retrieval with fake embeddings;
- hybrid score fusion;
- tool handler schemas and outputs.

### Integration tests

- plugin registration smoke test with a fake Hermes plugin context;
- full local workflow:
  1. initialize temp vault;
  2. create source/entity/synthesis pages;
  3. compile;
  4. reindex with fake embedding provider;
  5. hybrid search;
  6. get result page;
  7. lint.

### Optional live tests

Live OpenAI embedding tests must be opt-in via env var:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY=... pytest tests/live -v
```

## Security and privacy

- Do not index arbitrary local paths.
- Do not ingest Hermes sessions or memories automatically.
- Vector indexing sends search-document text to OpenAI; document this clearly.
- Allow embeddings to be disabled entirely.
- Avoid logging API keys or raw embedding payloads.
- Reject path traversal outside the configured vault root.
- Keep tool writes restricted to the configured vault root.

## Open questions for implementation

1. Should plugin skills be only namespaced (`memory-wiki:wiki-maintainer`) or should the package include an installer command to copy them into flat `~/.hermes/skills`?
   - Recommendation: register plugin skills first; add optional installer later.
2. Should the on-disk metadata directory be `.hermes-wiki` only, or support `.openclaw-wiki` compatibility mode?
   - Recommendation: default `.hermes-wiki`; read OpenClaw markers if present; do not write `.openclaw-wiki` unless user explicitly points at an existing vault and sets compatibility mode.
3. Should `wiki_apply` automatically run `wiki_reindex` for changed pages?
   - Recommendation: no by default; mark index stale and let `wiki_reindex` run explicitly or through `wiki_compile(reindex=true)`.
4. Should `wiki_search(searchMode=vector)` auto-reindex if stale?
   - Recommendation: no network writes during search by default. Return stale diagnostics.

## Success criteria for v1

- Plugin can be installed/enabled without modifying Hermes core.
- Tools appear under the `memory_wiki` toolset.
- A fresh vault can be initialized under `~/.hermes/wiki/main`.
- Pages can be created/updated through `wiki_apply`.
- Keyword search works without API keys.
- Vector indexing/search works with `OPENAI_API_KEY` and mocked tests pass offline.
- Hybrid search degrades cleanly to keyword if embeddings are unavailable.
- Compile creates indexes/dashboards/cache files.
- Lint produces useful structured and human-readable reports.
- Skills are available and accurately instruct the agent how to use the wiki.
