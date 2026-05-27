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

Search the Hermes memory wiki with a read-first workflow. Start by checking vault status when needed, search for relevant pages, retrieve exact page content, and refresh indexes if results appear stale.

## When to Use

- The user asks about stored wiki knowledge or prior project memory.
- You need to locate entities, claims, topics, or syntheses before taking action.
- Search returns too few results and the vault may need an index refresh.
- You must cite exact wiki page content rather than relying on snippets.

## Search Workflow

1. Run `wiki_status` if the vault path, page count, or readiness is uncertain.
2. Use `wiki_search` with a concise query and an appropriate result limit.
3. Open promising results with `wiki_get` to inspect authoritative page content.
4. Refine the query with names, titles, or keywords from retrieved pages when needed.
5. If search appears stale after recent edits, run `wiki_reindex`, then repeat `wiki_search`.
6. Base answers on retrieved content, and mention uncertainty when pages are incomplete.

## Pitfalls

- Do not answer from snippets alone when exact page text matters; use `wiki_get`.
- Do not run `wiki_reindex` repeatedly unless there is a freshness reason.
- Do not assume an empty result means no knowledge exists; try narrower and broader `wiki_search` queries.
- Confirm vault readiness with `wiki_status` when failures suggest a missing or uninitialized vault.

## Verification Checklist

- `wiki_status` was used when vault readiness was unclear.
- Relevant records were discovered with `wiki_search`.
- Final claims were checked against full content from `wiki_get`.
- `wiki_reindex` was used only when index freshness was a plausible issue.
