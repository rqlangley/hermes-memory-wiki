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
    - wiki_compile
    - wiki_reindex
    - wiki_lint
---

## Overview

Maintain Hermes memory wiki vaults safely with the native wiki tools. Use this skill to initialize a vault, inspect status, review existing content, apply deliberate changes, rebuild generated artifacts, refresh search indexes, and lint the result.

## When to Use

- A vault may not exist yet or needs a first-time setup.
- A session needs a health check before reading or changing wiki pages.
- A batch of edits has been applied and derived files should be rebuilt.
- Search results look stale and the index may need a refresh.
- The wiki needs validation before handing work back to the user.

## Maintenance Workflow

1. Run `wiki_status` to inspect the vault path and current page counts.
2. If the vault is absent, run `wiki_init` for the intended vault path.
3. Use `wiki_search` to locate relevant pages and `wiki_get` to inspect exact content before editing.
4. Apply minimal, scoped edits with `wiki_apply`.
5. Run `wiki_compile` after content changes so index pages and compiled views are current.
6. Run `wiki_reindex` when search data is stale or after larger updates.
7. Run `wiki_lint` and resolve reported errors before declaring maintenance complete.

## Pitfalls

- Do not edit blindly. Read relevant pages with `wiki_get` before applying changes.
- Do not skip `wiki_compile` after structural or content updates.
- Do not assume search is current if the vault has just changed; refresh with `wiki_reindex` when needed.
- Keep changes small and focused so lint findings remain easy to trace.

## Verification Checklist

- `wiki_status` reports the expected vault.
- Relevant source pages were inspected with `wiki_search` and `wiki_get`.
- Any edits were made through `wiki_apply`.
- `wiki_compile` completed after changes.
- `wiki_reindex` was run when search freshness mattered.
- `wiki_lint` reports no blocking errors.
