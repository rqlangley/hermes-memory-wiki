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

Maintain Hermes memory wiki vaults safely with the native wiki tools and the OpenClaw-compatible schema. Use this skill to initialize a vault, inspect status, ingest source material, review content, preserve human-authored notes, rebuild generated artifacts, refresh search indexes, and validate health.

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
3. Run `wiki_ingest` when a local file, conversation summary, or pasted text should become a managed source page.
4. Run `wiki_compile` after content changes so indexes, reports, and cache files are current.
5. Run `wiki_lint` and resolve blocking schema, link, duplicate, provenance, or vector issues.
6. Run `wiki_reindex` when search freshness matters or after larger updates.
7. Perform a search smoke check with `wiki_search` for a known page, source ID, or recent claim term.
8. Use `wiki_get` to inspect exact content before any follow-up `wiki_apply` fixes.

## Schema and Preservation Rules

- Keep broad page kinds aligned with directories: `entities/` -> `pageType: entity`, `concepts/` -> `pageType: concept`, `syntheses/` -> `pageType: synthesis`, `sources/` -> `pageType: source`, `reports/` -> `pageType: report`.
- Use `entityType` for subtypes such as `person`; do not create alternate broad page types.
- Avoid duplicate entity and concept pages by searching existing titles, aliases, canonical IDs, and claim text before creating new pages.
- Preserve human blocks and notes outside generated regions. Do not rewrite human-maintained prose when only generated output needs refresh.
- Treat generated blocks as tool-owned. Generated markers include `<!-- hermes:wiki:...:start -->` / `<!-- hermes:wiki:...:end -->`; human markers include `<!-- hermes:human:start -->` / `<!-- hermes:human:end -->`.
- Keep source-backed `claims` healthy: stable claim IDs, evidence entries, confidence, status, and freshness timestamps where available.

## Reports to Review

`wiki_compile` maintains report pages for:

- Claim health: missing evidence, stale claims, contested claims, and low confidence claims.
- Contradictions: explicit contradiction notes and contested claim statuses.
- Open questions: unresolved page questions that need source or decision follow-up.
- Low confidence: weak page-level or claim-level confidence.

Use these reports to plan targeted `wiki_apply` fixes, not broad rewrites.

## Pitfalls

- Do not edit blindly. Read relevant pages with `wiki_get` before applying changes.
- Do not skip `wiki_compile` after structural or content updates.
- Do not assume search is current if the vault has just changed; refresh with `wiki_reindex` when needed.
- Do not remove human blocks while replacing generated blocks.
- Keep changes small and focused so lint findings remain easy to trace.

## Verification Checklist

- `wiki_status` reports the expected vault.
- Relevant pages were inspected with `wiki_search` and `wiki_get`.
- Source ingestion used `wiki_ingest` when applicable, and other edits were made through `wiki_apply`.
- `wiki_compile` completed after changes.
- `wiki_lint` reports no blocking errors, or remaining issues are documented.
- `wiki_reindex` was run when search freshness mattered.
- A search smoke check confirms the refreshed index can find expected content.
