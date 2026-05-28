# Source Ingest and Conversation Authoring Design

**Status:** Approved direction from user, implementation not started.

**Goal:** Add first-class Hermes memory-wiki support for importing sources, treating conversations as source material, and using typed deterministic mutations so an agent can build/update wiki knowledge from user conversations without raw filesystem writes.

## Background

The current Hermes port intentionally keeps `wiki_apply` close to OpenClaw parity: deterministic `create_synthesis` and `update_metadata` operations. OpenClaw does not use `wiki_apply` as a generic arbitrary-page upsert. It creates source pages through ingest/import flows, and leaves interpretation of source knowledge to the agent/LLM.

The missing local-Hermes functionality is a model-callable source ingestion path and typed page upserts for source-backed entity/concept pages. The core design principle remains:

> Tools are deterministic. The agent/LLM exercises discretion by deciding what source text, claims, bodies, and mutations to pass to those tools.

## Requirements

1. Add a `wiki_ingest` tool that imports source material into `sources/` deterministically.
2. Support at least local-file and conversation-derived source inputs.
3. Preserve human notes on repeated source ingests.
4. Compile after writes, matching existing `wiki_apply` behavior.
5. Provide typed, schema-aware page upsert operations for entities and concepts so agents can build wiki articles from source-backed conversation knowledge.
6. Keep `wiki_apply` deterministic; do not add hidden internal LLM calls.
7. Update workflow skills/docs so agents know the intended flow.
8. Test via TDD with offline deterministic tests, plus tool-registration/tool-handler tests.

## Non-goals

- Do not add an internal LLM provider or automatic summarizer inside the tool layer.
- Do not add arbitrary freeform page writes exposed to the model.
- Do not implement OpenClaw bridge mode or unsafe-local import in this feature.
- Do not require vector embeddings for source ingest or typed upsert to work.
- Do not migrate existing user data beyond normal compile/reindex behavior.

## Proposed architecture

### Layer 1: `wiki_ingest`

Add a deterministic source-ingest module, likely `src/hermes_memory_wiki/ingest.py`.

Supported source types:

- `local-file`: read UTF-8 text from `inputPath`; reject binary-looking files; render fenced source content.
- `conversation-summary`: accept agent-supplied Markdown/text `body`; render it as a source page with conversation provenance metadata if supplied.
- Optional near-term alias: `text` for generic agent-supplied source text. This can share implementation with `conversation-summary` but use `sourceType: text`.

Input schema idea:

```json
{
  "sourceType": "local-file | conversation-summary | text",
  "title": "Source title",
  "inputPath": "/absolute/or/relative/local/file",
  "body": "Markdown source content supplied by the agent",
  "sessionId": "optional conversation/session id",
  "messageRange": "optional source message range",
  "sourcePath": "optional provenance label for non-file sources",
  "vaultPath": "optional vault override"
}
```

Output details should include:

- `path`
- `id`
- `title`
- `sourceType`
- `created`
- `changed`
- `bytes`
- compile summary

Rendering rules:

- Deterministic page path: `sources/<slug>.md` derived from title.
- Default id: `source.<slug>`.
- Existing page id is preserved if present.
- Frontmatter includes `pageType: source`, `sourceType`, `title`, `id`, `status: active`, `updatedAt`, and source-specific provenance fields.
- For first create, set `ingestedAt`; on refresh, preserve existing `ingestedAt` if present.
- Body has a generated source-content block and a human notes block.
- Existing human notes are preserved.
- Existing generated block is replaced.

### Layer 2: typed page upserts in `wiki_apply`

Extend `wiki_apply` with deterministic typed operations:

- `upsert_entity`
- `upsert_concept`

These are intentionally not generic arbitrary Markdown writes. They should only write allowed broad page kinds with required metadata and source-backed claim fields.

Input fields:

```json
{
  "op": "upsert_entity | upsert_concept",
  "title": "Page title",
  "body": "Generated body/summary supplied by the agent",
  "sourceIds": ["source..."],
  "claims": [...],
  "questions": [...],
  "contradictions": [...],
  "confidence": 0.0,
  "status": "active",
  "entityType": "project | person | system | organization | product | ...",  // entity only
  "aliases": ["..."],
  "lookup": "optional existing page lookup to update instead of title-derived path"
}
```

Rules:

- `upsert_entity` requires `title`, `entityType`, `body`, and non-empty `sourceIds`.
- `upsert_concept` requires `title`, `body`, and non-empty `sourceIds`.
- If `lookup` is provided and resolves to an existing page of the expected kind, update that page and preserve existing id/path.
- If no lookup, write deterministic path:
  - `entities/<slug>.md` with id `entity.<slug>`
  - `concepts/<slug>.md` with id `concept.<slug>`
- Preserve existing id if overwriting title-derived page.
- Replace generated summary block; preserve human notes.
- Set `pageType` to directory-derived kind.
- Include `entityType` only for entities.
- Compile after write.

### Layer 3: workflow skill C

Update `wiki-authoring` and `wiki-maintainer` skills to document the LLM-discretion workflow:

1. Search/get existing pages to avoid duplicates.
2. Ingest source material first:
   - local file via `wiki_ingest(sourceType="local-file")`
   - conversation/user guidance via `wiki_ingest(sourceType="conversation-summary", body=...)`
3. Use `wiki_apply` typed upserts or synthesis creation with `sourceIds` pointing to ingested source pages.
4. Use `update_metadata` only for existing metadata repair.
5. Run compile/lint/reindex as needed.
6. Verify with search/get.

## Safety constraints

- `wiki_ingest` local-file input may read outside the vault because source files live elsewhere, but writes must be confined to the configured vault using existing `safe_join` patterns.
- Reject binary files by checking for NUL bytes in the first 4096 bytes.
- For local files, use `Path(inputPath).expanduser().resolve()` and record the resolved source path.
- Do not follow symlink writes inside the vault in a way that escapes the vault. Use `safe_join`/resolved path checks for output paths.
- Do not expose arbitrary output path parameters in the first version.
- Do not auto-reindex in this feature unless explicitly requested later; compile after writes and let existing lint warn about stale vectors. Agents can call `wiki_reindex`.

## Testing strategy

- Unit-test ingest normalization/rendering/path/id behavior in `tests/test_ingest.py`.
- Unit-test typed page upsert behavior in `tests/test_apply.py`.
- Tool registration/schema tests in `tests/test_tools.py`.
- Tool workflow tests proving `wiki_ingest` + typed upsert + compile/search/get works on a temporary vault.
- Skill tests to ensure docs mention `wiki_ingest`, conversation-source workflow, and deterministic tools.

## Acceptance criteria

- `wiki_ingest` is registered in the `memory_wiki` toolset.
- `wiki_ingest` can import a local text file into `sources/<slug>.md` with OpenClaw-like source metadata and fenced content.
- `wiki_ingest` can create a conversation-summary source from agent-supplied body text.
- Re-ingesting same title preserves human notes and existing page id.
- `wiki_apply` supports `upsert_entity` and `upsert_concept` with strict schemas and deterministic paths.
- Typed upserts preserve human notes and update generated body/frontmatter.
- The full offline test suite passes.
- Docs/skills explain that tools are deterministic and LLM discretion belongs in the agent workflow.
