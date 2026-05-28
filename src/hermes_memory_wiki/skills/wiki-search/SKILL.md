---
name: wiki-search
description: Use when finding, retrieving, and validating information in a Hermes memory wiki vault before answering or deciding whether indexes need refresh.
version: 0.1.0
author: Nous Research
license: MIT
metadata:
  tools:
    - wiki_search
    - wiki_get
    - wiki_status
    - wiki_reindex
---

## Overview

Search the Hermes memory wiki with a read-first workflow. Use this skill when the answer may depend on stored wiki knowledge, prior project memory, source-backed claims, or compiled wiki indexes.

## When to Use

- The user asks about stored wiki knowledge, prior work, project memory, entities, concepts, sources, reports, or syntheses.
- You need to locate source-backed claims or exact claim IDs before answering.
- You need a page path to cite or to feed into an authoring/maintenance workflow.
- Search returns too few results and recent edits may not be indexed yet.

## Search Workflow

1. Run `wiki_status` if the vault path, page count, or readiness is uncertain.
2. Search first with `wiki_search` using a concise query and appropriate result limit.
3. Open promising results with `wiki_get`; snippets are discovery hints, not the authoritative page.
4. Cite wiki page paths and claim IDs when they support an answer, for example `entities/ada.md` or `claim.ada.role`.
5. Refine with names, aliases, page paths, source IDs, or claim terms from retrieved pages when needed.
6. If freshness matters after recent edits or a compiled index looks stale, run `wiki_reindex`, then repeat `wiki_search`.
7. Base answers on retrieved content and state uncertainty when pages, evidence, or claims are incomplete.

## Pitfalls

- Do not answer from snippets alone when exact page text matters; use `wiki_get`.
- Do not run `wiki_reindex` repeatedly unless there is a freshness reason.
- Do not assume an empty result means no knowledge exists; try narrower and broader `wiki_search` queries.
- Confirm vault readiness with `wiki_status` when failures suggest a missing or uninitialized vault.

## Verification Checklist

- `wiki_status` was used when vault readiness was unclear.
- Relevant records were discovered with `wiki_search`.
- Exact page content was checked with `wiki_get` before making final claims.
- Page paths and claim IDs were cited when relevant.
- `wiki_reindex` was used only when search freshness was a plausible issue.
