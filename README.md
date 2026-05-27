# Hermes-memory-wiki

Hermes-memory-wiki is a planned Hermes Agent plugin for managing a persistent markdown knowledge wiki with structured claims, provenance-aware pages, linting, generated indexes/dashboards, and built-in hybrid keyword + vector search.

This repository currently contains the approved design and implementation planning artifacts. Implementation should follow the project-local plans in [`docs/plans`](docs/plans).

## Goals

- Add wiki-management tools to Hermes Agent without modifying the default Hermes install.
- Provide OpenClaw memory-wiki-like page management, search, compile, and lint workflows.
- Build vector search in from the beginning using OpenAI embeddings, with deterministic keyword search always available as a fallback.
- Package reusable skills for wiki maintenance, authoring, and search workflows.

## Non-goals

- No OpenClaw bridge-mode port.
- No migration of the existing OpenClaw wiki vault.
- No dependency on OpenClaw at runtime.

## Planning artifacts

- [`docs/plans/2026-05-27-hermes-memory-wiki-design.md`](docs/plans/2026-05-27-hermes-memory-wiki-design.md)
- [`docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md`](docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md)
- [`docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md`](docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md)
- [`docs/references/openclaw-memory-wiki-source-inventory.md`](docs/references/openclaw-memory-wiki-source-inventory.md)
