# OpenClaw memory-wiki feature parity

This repository targets strict semantic parity with OpenClaw `memory-wiki` while remaining a native Hermes plugin.

## Phase 0 verified references

Reference source paths and line ranges were verified on 2026-05-28 before implementation:

- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js`
  - lines 363-407: directory-derived page kind and page summary fields
  - lines 411-508: vault directories and starter files
  - lines 511-538 and 1283-1350: compile groups, cache outputs, and compile result
  - lines 2293-2450: `wiki_apply` mutation behavior
  - lines 3260-3279: lint entrypoint/report shape
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js`
  - lines 789-813: structured claim/evidence tool schema

See `docs/references/openclaw-memory-wiki-source-inventory.md` for the detailed inventory.

## Canonical taxonomy

Queryable directories define broad kind:

| Directory | Broad kind |
| --- | --- |
| `entities/` | `entity` |
| `concepts/` | `concept` |
| `sources/` | `source` |
| `syntheses/` | `synthesis` |
| `reports/` | `report` |

`pageType` is required and must equal the broad kind. Entity subtypes belong in `entityType`, for example:

```yaml
id: entity.ada-lovelace
title: Ada Lovelace
pageType: entity
entityType: person
```

`pageType: person` under `entities/` is intentionally invalid in this clean-slate parity pass.

## Deferred or Hermes-specific items

- Hermes keeps `.hermes-wiki` naming rather than `.openclaw-wiki`.
- Hermes vector/hybrid search remains additive, indexing the OpenClaw-compatible page/claim corpus.
- No runtime OpenClaw dependency is allowed.
- Source ingest parity is deferred: OpenClaw exposes CLI/source-ingest workflow guidance, but the current Hermes port has no `wiki_ingest`/`wiki_import` tool or ingest/import helper to align in this pass. Implementing source ingest should be a separately scoped follow-up rather than Phase 6 expansion.
- Bridge, unsafe-local, Obsidian CLI, and shared-memory backend behavior are reference-only unless a later phase scopes them.
