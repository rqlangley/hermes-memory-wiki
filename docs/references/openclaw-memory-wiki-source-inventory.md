# OpenClaw memory-wiki source inventory

This document records the local OpenClaw files that should be referenced while implementing hermes-memory-wiki. The Hermes project must not depend on these files at runtime; they are reference material for behavior, schemas, and edge cases.

## Installed OpenClaw context

OpenClaw is installed on this server with memory-wiki enabled in:

```text
/home/langley/.openclaw/openclaw.json
```

Relevant configured plugin entry from inspection:

```json
{
  "plugins": {
    "entries": {
      "memory-wiki": {
        "enabled": true,
        "config": {
          "vaultMode": "bridge",
          "vault": { "path": "~/.openclaw/wiki/main" },
          "bridge": {
            "enabled": true,
            "readMemoryArtifacts": true,
            "indexDreamReports": true,
            "indexDailyNotes": true,
            "indexMemoryRoot": true,
            "followMemoryEvents": true
          },
          "search": { "backend": "shared", "corpus": "all" },
          "render": {
            "createDashboards": true,
            "createBacklinks": true,
            "preserveHumanBlocks": true
          }
        }
      }
    }
  }
}
```

The existing OpenClaw vault is intentionally **not** a migration target for this project, but can be inspected as a tiny fixture example:

```text
/home/langley/.openclaw/wiki/main/
  AGENTS.md
  WIKI.md
  index.md
  inbox.md
  .openclaw-wiki/state.json
  .openclaw-wiki/log.jsonl
```

## Primary memory-wiki plugin bundle

### Manifest

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/openclaw.plugin.json
```

Use this for:

- declared plugin id/name/description;
- declared agent tools;
- declared skills;
- startup shape.

### Main bundled plugin source

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js
```

Important inspected regions:

- Lines 455-660: gateway methods registered by OpenClaw memory-wiki.
- Lines 734-751: prompt/tool guidance for wiki usage.
- Lines 770-828: TypeBox schemas for `wiki_status`, `wiki_lint`, `wiki_search`, `wiki_get`, and `wiki_apply`.
- Lines 835-985: tool implementations for `wiki_status`, `wiki_search`, `wiki_lint`, `wiki_apply`, and `wiki_get`.
- Lines 989-1026: plugin registration, including prompt supplement, corpus supplement, gateway methods, tools, and CLI command registration.

OpenClaw tool names to preserve in Hermes where possible:

- `wiki_status`
- `wiki_search`
- `wiki_get`
- `wiki_apply`
- `wiki_lint`

Recommended additional Hermes tools:

- `wiki_init`
- `wiki_compile`
- `wiki_reindex`

## Shared OpenClaw chunks used by memory-wiki

OpenClaw bundles most memory-wiki core functions into a shared chunk. The exact chunk hash can change between OpenClaw versions, so do not hard-code it for runtime imports.

Current inspected chunk:

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js
```

Important inspected regions verified on 2026-05-28:

- Lines 363-370: `inferWikiPageKind(relativePath)` derives broad page kind from the first queryable directory only.
  - `entities/` -> `entity`
  - `concepts/` -> `concept`
  - `sources/` -> `source`
  - `syntheses/` -> `synthesis`
  - `reports/` -> `report`
  - all other paths -> `null`

- Lines 372-407: `toWikiPageSummary(...)` summary/frontmatter fields.
  - `kind` is the directory-derived broad kind, not `pageType`.
  - Parsed fields include `id`, `pageType`, `entityType`, `canonicalId`, `aliases`, `sourceIds`, `claims`, `contradictions`, `questions`, `confidence`, `privacyTier`, `personCard`, `relationships`, `bestUsedFor`, `notEnoughFor`, `sourceType`, `provenanceMode`, `sourcePath`, `bridgeRelativePath`, `bridgeWorkspaceDir`, `unsafeLocalConfiguredPath`, `unsafeLocalRelativePath`, `lastRefreshedAt`, and `updatedAt`.

- Lines 411-422: OpenClaw vault directory list.
  - `entities`, `concepts`, `syntheses`, `sources`, `reports`, `_attachments`, `_views`, `.openclaw-wiki`, `.openclaw-wiki/locks`, `.openclaw-wiki/cache`.
  - Hermes should keep `.hermes-wiki` naming and add its vector cache directory as a Hermes extension.

- Lines 432-441: starter `AGENTS.md` guidance.
  - Generated blocks are plugin-owned.
  - Human notes outside managed markers are preserved.
  - Source-backed claims are preferred over wiki-to-wiki citation loops.
  - Structured `claims` with evidence are preferred over burying key beliefs in prose.
  - `agent-digest.json` and `claims.jsonl` are machine-readable; Markdown pages are the human view.

- Lines 443-461: starter `WIKI.md` guidance.
  - Documents plugin ownership, vault/render/search modes, evidence layer vs synthesis layer, cache digest, and human notes block markers.

- Lines 473-508: `initializeMemoryWikiVault(config, options)`.
  - Creates vault root and standard directories.
  - Creates `AGENTS.md`, `WIKI.md`, `index.md`, `inbox.md` only when missing.
  - Creates `.openclaw-wiki/state.json` and `.openclaw-wiki/log.jsonl` and appends an init log.

- Lines 511-538: compile page groups and cache path constants.
  - Page groups are `source`, `entity`, `concept`, `synthesis`, `report` mapped to `sources`, `entities`, `concepts`, `syntheses`, `reports`.
  - Cache files include `.openclaw-wiki/cache/agent-digest.json` and `.openclaw-wiki/cache/claims.jsonl`.

- Lines 1283-1350: `compileMemoryWikiVault(config)`.
  - Initializes vault.
  - Reads page summaries.
  - Refreshes related blocks.
  - Refreshes dashboards.
  - Writes digest artifacts.
  - Refreshes root and directory indexes.
  - Appends compile log.
  - Returns `pageCounts`, `pages`, `claimCount`, and updated files.

- Lines 1376-1443: query constants.
  - Query directories: `entities`, `concepts`, `sources`, `syntheses`, `reports`.
  - Search modes: `auto`, `find-person`, `route-question`, `source-evidence`, `raw-claim`.

- Lines 1461-1483: wiki markdown file discovery and queryable page loading.
  - Reads `.md` files under query directories, excluding directory `index.md` files.

- Lines 1498-1516: query digest loading.
  - Reads agent digest and claims digest if available.

- Lines 1517-1579: snippet and searchable text construction.
  - Removes generated related blocks.
  - Removes markdown frontmatter for snippet text.
  - Tokenizes query terms.

- Lines 1632-1655: claim scoring.
  - Exact/text token matches.
  - Confidence weighting.
  - Freshness/status boosts/penalties.

- Lines 1667-1678: metadata scoring.
  - Title/path/id/source-id boosts.

- Lines 1725-1764 and 1766-1799: mode-specific score boosts.
  - `find-person`
  - `route-question`
  - `source-evidence`
  - `raw-claim`

- Lines 1801-1844: digest candidate path ranking.
  - Digest-assisted candidate selection before reading full pages.

- Lines 1845-1918: page and claim matching/scoring.
  - The local wiki search path is deterministic keyword/token/metadata scoring.
  - No local wiki embedding call was found in this search path.

- Lines 1951-1956: corpus/shared-memory selection helpers.
  - Local wiki search is separate from shared memory search.

- Lines 2023-2035: conversion of a queryable page into a wiki search result.
  - Result fields include corpus, path, title, kind, score, snippet, searchMode, metadata, and matched claim metadata.

- Lines 2170-2208: `searchMemoryWiki(params)`.
  - Applies search overrides.
  - Initializes vault.
  - Searches local wiki corpus.
  - Optionally merges shared memory results when `backend=shared` and `corpus=memory|all`.

- Lines 2209-2286: `getMemoryWikiPage(params)`.
  - Resolves lookup by path/id/basename.
  - Supports `fromLine` and `lineCount`.
  - Falls back to shared memory reads when configured.

- Lines 2293-2450: `normalizeMemoryWikiMutationInput(...)` and `applyMemoryWikiMutation(...)`.
  - Supports `create_synthesis` and `update_metadata`.
  - `create_synthesis` requires title, body, and at least one `sourceId`.
  - Synthesis frontmatter uses `pageType: synthesis`, `id: synthesis.<slug>`, `title`, normalized `sourceIds`, optional structured `claims`, `contradictions`, `questions`, numeric `confidence`, `status`, and `updatedAt`.
  - `update_metadata` requires lookup and narrowly updates `sourceIds`, `claims`, `contradictions`, `questions`, `confidence`, `status`, and `updatedAt`.
  - Preserves human notes block markers.
  - Writes frontmatter/body.
  - Compiles after mutation.

- Lines 3260 onward: `lintMemoryWikiVault(config)`.
  - Use as reference for lint categories and report shape.

### Claim and evidence schema

Verified in `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js` lines 789-813 and the shared summary parser above:

- Claims live in page frontmatter (`claims:`); there is no top-level `claims/` query directory.
- Claim fields: `id`, required `text`, `status`, numeric `confidence` between 0 and 1, optional `evidence`, and `updatedAt`.
- Evidence fields: `kind`, `sourceId`, `path`, `lines`, numeric `weight`, `note`, numeric `confidence` between 0 and 1, `privacyTier`, and `updatedAt`.

### Lint behavior to mirror

Verified primary entrypoint in `cli-Cx8TeRn1.js` lines 3260-3279; helper collection functions live immediately before that region in the same bundle.

- Lint compiles first, then collects page issues and groups by category.
- Lint writes a report and appends a lint log entry.
- Required Hermes parity checks for the approved clean-slate pass:
  - missing `id`;
  - duplicate page `id`;
  - duplicate claim `id`;
  - missing `pageType`;
  - `pageType` mismatching directory-derived broad kind;
  - missing title;
  - invalid markdown/frontmatter;
  - provenance warnings for missing `sourceIds` on non-source/non-report pages and claims without evidence;
  - low confidence, stale pages/claims, contradictions, open questions, broken wikilinks/source links, and source provenance metadata issues.

## OpenClaw memory-wiki config source

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/config-U1dUmpXj.js
```

Important inspected regions:

- Lines 8-23: supported vault/search/render mode constants.
  - Vault modes: `isolated`, `bridge`, `unsafe-local`.
  - Render modes: `native`, `obsidian`.
  - Search backends: `shared`, `local`.
  - Search corpora: `wiki`, `memory`, `all`.

- Lines 24-63: config schema.
  - Includes vault, obsidian, bridge, unsafeLocal, ingest, search, context, and render settings.

- Lines 79-130: config normalization and defaults.
  - Default OpenClaw vault path is `~/.openclaw/wiki/main`.
  - Default vault mode is `isolated`.
  - Default search backend is `shared` and corpus is `wiki`.
  - Default render settings preserve human blocks and create backlinks/dashboards.

hermes-memory-wiki should **not** port bridge or unsafe-local mode for v1.

## Deferred or Hermes-specific features in this parity pass

- Keep Hermes `.hermes-wiki` metadata naming instead of OpenClaw `.openclaw-wiki`.
- Keep Hermes vector/hybrid search as an additive feature, but index OpenClaw-compatible page and claim documents.
- Do not import or shell out to OpenClaw at runtime.
- Do not support legacy divergent Hermes pages such as `entities/*.md` with `pageType: person`.
- Bridge, unsafe-local, Obsidian CLI, and shared-memory backend behavior are reference-only unless a later phase explicitly scopes them.

## OpenClaw skills to adapt

### Wiki maintainer skill

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md
```

Current skill guidance includes:

- use `wiki_status` first;
- use memory/wiki search before relying on stored knowledge;
- use `wiki_search` then `wiki_get`;
- use `wiki_apply` for narrow mutations;
- run `wiki_lint` after meaningful updates;
- use CLI maintenance loop: `openclaw wiki ingest`, `compile`, `lint`;
- preserve human note blocks;
- treat sources/memory artifacts/daily notes as evidence;
- avoid duplicate entities/concepts.

Hermes adaptation should remove OpenClaw CLI references or replace them with Hermes tool/CLI equivalents.

### Obsidian maintainer skill

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/obsidian-vault-maintainer/SKILL.md
```

Use as optional reference for Obsidian-compatible wikilinks and vault hygiene.

## Embedding/vector-search reference material

OpenClaw memory-wiki local wiki search does not appear to use embeddings. Embeddings are part of broader OpenClaw memory search infrastructure.

Relevant inspected files for OpenClaw embedding infrastructure:

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/memory-embedding-adapter-o6oYhd-H.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/embedding-provider-C029Zeb0.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/embedding-batch-Qua9Xd87.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/memory-core-host-engine-embeddings-3y56AGBy.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/zod-schema.agent-runtime-D8PVvs6o.js
```

Important observations:

- OpenClaw supports memory embedding providers including OpenAI.
- OpenClaw agent config supports memorySearch vector/hybrid settings.
- OpenClaw memory-wiki uses shared memory search results when configured with shared backend/corpus; those results may be vector/hybrid.
- hermes-memory-wiki should implement its own vector index for wiki documents, not rely on OpenClaw memory-core.

## Runtime-dependency rule

hermes-memory-wiki must not import or shell out to these OpenClaw files during normal operation. They are only a behavioral reference and fixture source.
