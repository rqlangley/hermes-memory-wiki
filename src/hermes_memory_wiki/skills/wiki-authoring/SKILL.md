---
name: wiki-authoring
description: Use when creating or updating Hermes memory wiki content from verified context while preserving vault structure and validating the resulting pages.
version: 0.1.0
author: Nous Research
license: MIT
metadata:
  tools:
    - wiki_get
    - wiki_apply
    - wiki_ingest
    - wiki_compile
    - wiki_lint
---

## Overview

Author OpenClaw-compatible memory wiki content by reading existing context, ingesting source material when needed, applying the smallest useful mutation, compiling derived outputs, linting the vault, and refreshing search indexes when a tool workflow allows it. Prefer precise source-backed updates over broad rewrites.

## When to Use

- A user asks to add a new entity, concept, claim, source, report note, or synthesis page.
- Existing wiki content needs a correction, clarification, or additional source-backed note.
- A draft update needs validation against the OpenClaw-compatible schema.
- A recent edit should be compiled and checked for wiki consistency.

## Schema Essentials

Directory taxonomy defines broad page kind:

- `entities/` pages use `pageType: entity`.
- `concepts/` pages use `pageType: concept`.
- `syntheses/` pages use `pageType: synthesis`.
- `sources/` pages use `pageType: source`.
- `reports/` pages use `pageType: report`.

Use `entityType`, not `pageType`, for entity subtypes. A person page is an entity page with `entityType: person`; organizations, projects, systems, and products are also subtypes under `pageType: entity`.

Required discipline:

- Keep `id`, `title`, and `pageType` in frontmatter.
- Put `sourceIds` on non-source/non-report pages so claims can be traced to source pages.
- Prefer structured `claims` over unsupported prose-only assertions.
- Give each claim a stable `id`, clear `text`, `status`, `confidence`, and `updatedAt` when known.
- Add `evidence` entries for source-backed claims.

Evidence format example:

```yaml
claims:
  - id: claim.ada.role
    text: Ada is the project lead for the memory wiki work.
    status: active
    confidence: 0.9
    evidence:
      - kind: source
        sourceId: source.project-notes
        path: sources/project-notes.md
        lines: "12-18"
        weight: 1
        note: Project notes identify the role.
        confidence: 0.9
        privacyTier: standard
        updatedAt: "2026-05-28T00:00:00Z"
    updatedAt: "2026-05-28T00:00:00Z"
```

## Authoring Workflow

1. Use `wiki_get` to read the target page or nearest related page before changing anything.
2. Check for an existing entity/concept/source to avoid duplicate pages.
3. Prepare a minimal content change that matches the directory taxonomy and schema.
4. Use `wiki_ingest` for source pages from local files, conversation summaries, or pasted text before citing them.
5. Use `wiki_apply` to create or update synthesis/metadata pages.
6. Run `wiki_compile` so generated indexes, reports, and cache files reflect the change.
7. Run `wiki_lint` to catch malformed links, metadata issues, provenance gaps, or structural problems.
8. If search freshness matters after the edit, use the maintenance workflow to run `wiki_reindex` before relying on search.
9. If lint reports errors, inspect the affected page with `wiki_get`, then apply a focused fix with `wiki_apply`.

## Pitfalls

- Do not invent details that are not supported by the conversation, source pages, or retrieved wiki context.
- Do not overwrite large sections when a targeted `wiki_apply` update is enough.
- Do not treat a person as its own broad page kind; use `pageType: entity` plus `entityType: person`.
- Do not omit `sourceIds` from entity, concept, or synthesis pages unless the page is intentionally unsourced and the limitation is explicit.
- Do not claim the edit is ready until `wiki_compile` and `wiki_lint` have run after the change.

## Verification Checklist

- Target content was inspected with `wiki_get`.
- New source material was captured with `wiki_ingest` when applicable, and the update was applied through `wiki_apply`.
- Frontmatter uses the correct broad `pageType` and any entity subtype uses `entityType`.
- Claims have source-backed evidence when possible and non-source/non-report pages list `sourceIds`.
- `wiki_compile` completed after the authoring change.
- `wiki_lint` reports the vault is valid or only has clearly explained non-blocking warnings.
