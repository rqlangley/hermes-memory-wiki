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
    - wiki_compile
    - wiki_lint
---

## Overview

Author wiki content by reading the existing page context, applying the smallest useful mutation, compiling derived outputs, and linting the vault. Prefer precise updates over broad rewrites.

## When to Use

- A user asks to add a new entity, topic, claim, or synthesis page.
- Existing wiki content needs a correction, clarification, or additional source-backed note.
- A draft update needs validation against existing page shape.
- A recent edit should be compiled and checked for wiki consistency.

## Authoring Workflow

1. Use `wiki_get` to read the target page or nearest related page before changing anything.
2. Prepare a minimal content change that matches the page type and vault conventions.
3. Use `wiki_apply` to create or update the page.
4. Run `wiki_compile` so generated indexes and summaries reflect the change.
5. Run `wiki_lint` to catch malformed links, metadata issues, or structural problems.
6. If lint reports errors, inspect the affected page with `wiki_get`, then apply a focused fix with `wiki_apply`.

## Pitfalls

- Do not invent details that are not supported by the conversation or retrieved wiki context.
- Do not overwrite large sections when a targeted `wiki_apply` update is enough.
- Do not claim the edit is ready until `wiki_compile` and `wiki_lint` have run after the change.
- Keep titles, identifiers, and links consistent with the existing page style.

## Verification Checklist

- Target content was inspected with `wiki_get`.
- The update was applied through `wiki_apply`.
- `wiki_compile` completed after the authoring change.
- `wiki_lint` reports the vault is valid or only has clearly explained non-blocking warnings.
