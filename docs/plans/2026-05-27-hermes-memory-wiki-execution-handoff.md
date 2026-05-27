# Hermes-memory-wiki Execution Handoff

**Date:** 2026-05-27

## Project

```text
/home/langley/projects/Hermes-memory-wiki
```

Remote:

```text
https://github.com/rqlangley/Hermes-memory-wiki
```

Private GitHub repo created with `gh repo create`.

## Current state

This repo contains planning artifacts only. Implementation has not started.

Important files:

```text
README.md
docs/plans/2026-05-27-hermes-memory-wiki-design.md
docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md
docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md
docs/references/openclaw-memory-wiki-source-inventory.md
```

## Approved design summary

Build **Hermes-memory-wiki**, a native Hermes Agent plugin that adds memory-wiki tools and skills without modifying Hermes core.

Required capabilities:

- initialize/manage a markdown wiki vault;
- structured page schema for sources/entities/concepts/syntheses/reports;
- `wiki_status`, `wiki_search`, `wiki_get`, `wiki_apply`, `wiki_lint`;
- additional `wiki_init`, `wiki_compile`, `wiki_reindex` tools;
- deterministic keyword search based on OpenClaw memory-wiki behavior;
- built-in optional OpenAI vector search from the beginning;
- hybrid search default when embeddings are available;
- graceful fallback to keyword search when embeddings/API key are unavailable;
- plugin-provided skills for maintenance, authoring, and search.

Non-goals:

- no OpenClaw bridge mode;
- no migration of existing OpenClaw wiki;
- no runtime dependency on OpenClaw;
- no automatic private session/memory ingestion;
- no Hermes core modifications.

## OpenClaw source references

Use only as reference material, never runtime dependencies.

Inventory:

```text
docs/references/openclaw-memory-wiki-source-inventory.md
```

Primary local files:

```text
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/config-U1dUmpXj.js
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md
/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/obsidian-vault-maintainer/SKILL.md
```

Key observed fact: OpenClaw memory-wiki local wiki search is keyword/scoring based. OpenClaw embeddings belong to shared memorySearch/memory-core; Hermes-memory-wiki should implement its own wiki vector index using OpenAI.

## Required workflow

Use strict software engineering workflow:

1. Create implementation branch:

```bash
cd /home/langley/projects/Hermes-memory-wiki
git checkout -b feat/initial-hermes-memory-wiki-plugin
```

2. Follow the implementation plan:

```text
docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md
```

3. Use TDD for every code task:
   - failing test;
   - verify failure;
   - implement minimal code;
   - verify pass;
   - commit.

4. Use subagent-driven-development:
   - implementation subagent per task or small phase;
   - spec compliance review first;
   - code quality review second;
   - fix issues before proceeding.

5. Do not implement bridge mode or OpenClaw runtime imports.

6. Push branch and open PR after final verification.

## Final verification commands

At minimum:

```bash
cd /home/langley/projects/Hermes-memory-wiki
python -m pytest -q
python -m compileall src tests
python -m pip install -e .
python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
git status --short
```

Optional live OpenAI embeddings test only if explicitly allowed and an API key is configured:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" pytest tests/live -v
```

## Pasteable fresh-chat prompt

```text
You are implementing Hermes-memory-wiki in /home/langley/projects/Hermes-memory-wiki.

Load these skills before acting: software-engineering-rigor, subagent-driven-development, test-driven-development, verification-before-completion, requesting-code-review, receiving-code-review, github-pr-workflow.

Read these project-local artifacts first:
- docs/plans/2026-05-27-hermes-memory-wiki-design.md
- docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md
- docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md
- docs/references/openclaw-memory-wiki-source-inventory.md

Goal: implement a native Hermes Agent plugin named Hermes-memory-wiki. It must add wiki tools and skills without modifying Hermes core. It must include keyword search plus OpenAI-backed vector search from the beginning, with hybrid search default and keyword fallback when embeddings are unavailable.

Non-goals: no OpenClaw bridge mode, no migration of the existing OpenClaw wiki, no OpenClaw runtime dependency, no automatic private session/memory ingestion.

Start by creating branch feat/initial-hermes-memory-wiki-plugin. Then execute the implementation plan task-by-task using TDD. Commit after each task or small task group. Use subagent-driven development and two-stage review: spec compliance first, code quality second. Before claiming completion, run final verification from the handoff and push the branch to origin.
```
