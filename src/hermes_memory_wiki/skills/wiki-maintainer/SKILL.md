---
name: wiki-maintainer
description: Use when maintaining a Hermes memory wiki vault, checking health, rebuilding derived files, refreshing indexes, and validating content before or after wiki changes.
version: 0.1.0
author: Nous Research
license: MIT
metadata:
  tools:
    - wiki_init
    - wiki_status
    - wiki_search
    - wiki_get
    - wiki_apply
    - wiki_ingest
    - wiki_compile
    - wiki_reindex
    - wiki_lint
---

## Overview

Maintain Hermes memory wiki vaults safely with the native wiki tools and the OpenClaw-compatible schema. Use this skill to initialize a vault, inspect status, ingest source material, review content, preserve human-authored notes, rebuild generated artifacts, refresh search indexes, and validate health. Tool handlers are deterministic and make no hidden tool-layer LLM calls; the agent/LLM decides what summaries, claims, and citations to submit.

## When to Use

- A vault may not exist yet or needs first-time setup.
- A session needs a health check before reading or changing wiki pages.
- A batch of edits has been applied and derived files should be rebuilt.
- Search results look stale and the index may need a refresh.
- The wiki needs validation before handing work back to the user.
- Claim health, contradictions, or open questions need review.

## Maintenance Loop

1. Run `wiki_status` to inspect the vault path, readiness, and current page counts.
2. If the vault is absent, run `wiki_init` for the intended vault path.
3. Run `wiki_search`/`wiki_get` before editing or cleanup so fixes are grounded in current pages.
4. Run `wiki_ingest` when a `local-file`, `conversation-summary`, or `text` input should become a managed source page; conversation summaries are source pages cited by `sourceIds`.
5. Use structured `wiki_apply` operations only: `upsert_entity`, `upsert_concept`, `create_synthesis`, or `update_metadata`. There is no arbitrary freeform page-write tool.
6. Run `wiki_compile` after content changes so indexes, reports, and cache files are current.
7. Run `wiki_lint` and resolve blocking schema, link, duplicate, provenance, or vector issues.
8. Run `wiki_reindex` when search freshness matters or after larger updates.
9. Perform a search smoke check with `wiki_search` for a known page, source ID, or recent claim term.
10. Use `wiki_get` to inspect exact content before any follow-up `wiki_apply` fixes, then repeat compile/lint/reindex verification as needed.

## Schema and Preservation Rules

- Keep broad page kinds aligned with directories: `entities/` -> `pageType: entity`, `concepts/` -> `pageType: concept`, `syntheses/` -> `pageType: synthesis`, `sources/` -> `pageType: source`, `reports/` -> `pageType: report`.
- Use `entityType` for subtypes such as `person`; do not create alternate broad page types.
- Avoid duplicate entity and concept pages by searching existing titles, aliases, canonical IDs, and claim text before creating new pages.
- Preserve human blocks and notes outside generated regions. Do not rewrite human-maintained prose when only generated output needs refresh.
- Treat generated blocks as tool-owned. Generated markers include `<!-- hermes:wiki:...:start -->` / `<!-- hermes:wiki:...:end -->`; human markers include `<!-- hermes:human:start -->` / `<!-- hermes:human:end -->`.
- Keep source-backed `claims` healthy: stable claim IDs, evidence entries, confidence, status, and freshness timestamps where available.
- Keep source-backed typed pages healthy: `upsert_entity` pages belong under `entities/` with `pageType: entity` and an `entityType`; `upsert_concept` pages belong under `concepts/`; `create_synthesis` is for cross-source synthesis.
- Remember that deterministic tools write the supplied data. They do not decide whether a claim is true; the agent must ground claims in sources, conversation-summary source pages, or retrieved wiki context.

## Reports to Review

`wiki_compile` maintains report pages for:

- Claim health: missing evidence, stale claims, contested claims, and low confidence claims.
- Contradictions: explicit contradiction notes and contested claim statuses.
- Open questions: unresolved page questions that need source or decision follow-up.
- Low confidence: weak page-level or claim-level confidence.

Use these reports to plan targeted `wiki_apply` fixes, not broad rewrites.

## Pitfalls

- Do not edit blindly. Read relevant pages with `wiki_get` before applying changes.
- Do not bypass `wiki_ingest`/`wiki_apply` with arbitrary Markdown writes for normal authoring.
- Do not skip `wiki_compile` after structural or content updates.
- Do not assume search is current if the vault has just changed; refresh with `wiki_reindex` when needed.
- Do not remove human blocks while replacing generated blocks.
- Keep changes small and focused so lint findings remain easy to trace.

## Verification Checklist

- `wiki_status` reports the expected vault.
- Relevant pages were inspected with `wiki_search` and `wiki_get`.
- Source ingestion used `wiki_ingest` when applicable (`local-file`, `conversation-summary`, or `text`), and other edits were made through typed `wiki_apply` operations.
- `wiki_compile` completed after changes.
- `wiki_lint` reports no blocking errors, or remaining issues are documented.
- `wiki_reindex` was run when search freshness mattered.
- A search smoke check confirms the refreshed index can find expected content.
