# Source Ingest and Conversation Authoring Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add deterministic `wiki_ingest`, conversation-summary sources, typed `wiki_apply` entity/concept upserts, and updated authoring workflow guidance.

**Architecture:** Keep the tool layer deterministic. Add `ingest.py` for source-page creation/refresh, extend `apply.py` with typed page upserts, expose `wiki_ingest` through `tools.py`, and update skills/docs so the LLM/agent uses these tools to capture conversation knowledge as sources and apply source-backed wiki updates.

**Tech Stack:** Python 3.11+, PyYAML, pytest, Hermes user-plugin tool registration.

**Branch strategy:** Create a feature branch from `main`: `feat/source-ingest-conversation-authoring`. Commit after each task. Push the branch and open/merge only after tests and review pass.

---

## Task 1: Create feature branch and baseline test run

**Objective:** Establish clean starting state and confirm baseline before changes.

**Files:** None.

**Step 1: Check git state**

Run:

```bash
git status --short
git branch --show-current
```

Expected: note any existing uncommitted plan files. Do not overwrite user work.

**Step 2: Create branch**

Run:

```bash
git checkout main
git pull --ff-only
git checkout -b feat/source-ingest-conversation-authoring
```

Expected: branch created.

**Step 3: Run baseline tests**

Run:

```bash
python -m pytest -q
```

Expected: current offline suite passes or only known skips. If it fails, stop and report before coding.

**Step 4: Commit plan artifacts if not already committed**

Run:

```bash
git add docs/plans/2026-05-28-source-ingest-and-conversation-authoring-design.md docs/plans/2026-05-28-source-ingest-and-conversation-authoring-implementation-plan.md docs/plans/2026-05-28-source-ingest-and-conversation-authoring-execution-handoff.md
git commit -m "docs: plan source ingest and conversation authoring"
```

Expected: docs commit or no-op if already committed.

---

## Task 2: Add failing ingest tests for local-file sources

**Objective:** Define local-file source ingestion behavior before implementation.

**Files:**
- Create: `tests/test_ingest.py`
- Test: `tests/test_ingest.py`

**Step 1: Write failing tests**

Create `tests/test_ingest.py` with tests for:

- local text file ingests to `sources/<slug>.md`
- frontmatter contains `pageType: source`, `id: source.<slug>`, `title`, `sourceType: local-file`, `sourcePath`, `ingestedAt`, `updatedAt`, `status: active`
- body contains source metadata and fenced content
- ingest result reports `created=True`, `changed=True`, path/id/title/bytes

Use existing helpers from `markdown.py` for parsing.

Suggested starting test shape:

```python
from __future__ import annotations

from pathlib import Path

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.ingest import ingest_source
from hermes_memory_wiki.markdown import parse_wiki_markdown
from hermes_memory_wiki.vault import initialize_vault


def _config(root: Path) -> MemoryWikiConfig:
    return MemoryWikiConfig(vault_path=root)


def test_ingest_local_file_creates_source_page(tmp_path):
    vault = tmp_path / "vault"
    source = tmp_path / "notes" / "README.md"
    source.parent.mkdir()
    source.write_text("# Project Notes\n\nImportant source text.\n", encoding="utf-8")
    initialize_vault(_config(vault))

    result = ingest_source(_config(vault), {"sourceType": "local-file", "inputPath": str(source), "title": "Project Notes"})

    assert result.created is True
    assert result.changed is True
    assert result.path == "sources/project-notes.md"
    assert result.id == "source.project-notes"
    doc = parse_wiki_markdown((vault / result.path).read_text(encoding="utf-8"))
    assert doc.frontmatter["pageType"] == "source"
    assert doc.frontmatter["id"] == "source.project-notes"
    assert doc.frontmatter["title"] == "Project Notes"
    assert doc.frontmatter["sourceType"] == "local-file"
    assert doc.frontmatter["sourcePath"] == str(source.resolve())
    assert doc.frontmatter["status"] == "active"
    assert "ingestedAt" in doc.frontmatter
    assert "updatedAt" in doc.frontmatter
    assert "## Source" in doc.body
    assert "## Content" in doc.body
    assert "```text" in doc.body
    assert "Important source text." in doc.body
```

**Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_ingest.py -q
```

Expected: FAIL because `hermes_memory_wiki.ingest` does not exist.

**Step 3: Commit failing tests?**

Do not commit failing tests alone unless using a dedicated red commit convention. Prefer proceed to Task 3 and commit green implementation with tests.

---

## Task 3: Implement minimal local-file ingest core

**Objective:** Make local-file source ingestion tests pass.

**Files:**
- Create: `src/hermes_memory_wiki/ingest.py`
- Modify: none initially
- Test: `tests/test_ingest.py`

**Step 1: Implement `ingest.py`**

Create dataclasses and helpers:

```python
@dataclass(frozen=True)
class IngestResult:
    path: str
    id: str
    title: str
    source_type: str
    created: bool
    changed: bool
    bytes: int
```

Implement:

```python
def ingest_source(config: MemoryWikiConfig, raw: Mapping[str, Any]) -> IngestResult:
    ...
```

Implementation requirements:

- require `sourceType`
- support `local-file`
- require `inputPath` for local-file
- title defaults to input basename without extension, with `-`/`_` converted to spaces
- slugify title using the same algorithm as `apply.py` if practical; if private, extract to a shared helper or duplicate with TODO only if necessary
- output relative path is `sources/<slug>.md`
- output path uses `safe_join(config.vault_path, relative_path)`
- parse existing page if present and preserve existing `id` and `ingestedAt`
- reject binary-looking files containing NUL in first 4096 bytes
- render body with `# {title}`, `## Source`, `## Content`, fenced `text` block, and human notes via `ensure_human_notes_block`
- write only if rendered text differs

**Step 2: Run tests**

Run:

```bash
python -m pytest tests/test_ingest.py -q
```

Expected: PASS.

**Step 3: Run focused regression**

Run:

```bash
python -m pytest tests/test_markdown.py tests/test_paths.py tests/test_vault_init.py -q
```

Expected: PASS.

**Step 4: Commit**

```bash
git add src/hermes_memory_wiki/ingest.py tests/test_ingest.py
git commit -m "feat: ingest local files as wiki sources"
```

---

## Task 4: Add ingest idempotence, human-note preservation, and binary rejection tests

**Objective:** Harden local-file ingest semantics.

**Files:**
- Modify: `tests/test_ingest.py`
- Modify: `src/hermes_memory_wiki/ingest.py`

**Step 1: Write failing tests**

Add tests that verify:

1. Re-ingesting unchanged source returns `changed=False`.
2. Re-ingesting after manually editing human notes preserves those notes.
3. Re-ingesting a page with custom existing id preserves that id.
4. Binary-looking input raises `ValueError` with clear message.

**Step 2: Run focused tests**

```bash
python -m pytest tests/test_ingest.py -q
```

Expected: FAIL for any missing behavior.

**Step 3: Implement minimal fixes**

Update `ingest.py` to preserve human marker blocks by using existing `ensure_human_notes_block`/managed generated block helpers. If the current `replace_managed_block` only supports one generated block and is sufficient, use it for the source content block heading `Content`. Otherwise add a small helper in `ingest.py` that preserves human notes while replacing the generated block.

**Step 4: Verify**

```bash
python -m pytest tests/test_ingest.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/ingest.py tests/test_ingest.py
git commit -m "test: harden source ingest refresh behavior"
```

---

## Task 5: Add conversation-summary/text source ingest

**Objective:** Allow the agent to capture conversation-derived knowledge as a source page without raw file writes.

**Files:**
- Modify: `tests/test_ingest.py`
- Modify: `src/hermes_memory_wiki/ingest.py`

**Step 1: Write failing tests**

Add tests for:

- `sourceType: conversation-summary` requires `title` and `body`
- writes `sourceType: conversation-summary`
- stores optional `sessionId`, `messageRange`, and `sourcePath` frontmatter when supplied
- body includes the agent-supplied summary under generated content
- `sourceType: text` works similarly but without conversation fields

Example expected call:

```python
result = ingest_source(
    _config(vault),
    {
        "sourceType": "conversation-summary",
        "title": "User guidance: memory wiki authoring",
        "body": "- The user wants conversations to be usable as source evidence.\n",
        "sessionId": "session-123",
        "messageRange": "user:12-assistant:18",
    },
)
```

**Step 2: Run tests to verify failure**

```bash
python -m pytest tests/test_ingest.py -q
```

Expected: FAIL for unsupported source type.

**Step 3: Implement support**

Update `ingest.py`:

- normalize `body` from raw mapping
- for non-file source types, byte count is UTF-8 byte length of body
- `sourcePath` is optional provenance text, not used for reading
- render source section with source type and provenance fields

**Step 4: Verify**

```bash
python -m pytest tests/test_ingest.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/ingest.py tests/test_ingest.py
git commit -m "feat: ingest conversation summaries as wiki sources"
```

---

## Task 6: Register and test `wiki_ingest` tool

**Objective:** Expose ingest functionality through Hermes tools.

**Files:**
- Modify: `src/hermes_memory_wiki/tools.py`
- Modify: `tests/test_tools.py`

**Step 1: Write failing tool tests**

In `tests/test_tools.py`:

- Add `wiki_ingest` to `EXPECTED_TOOLS`.
- Assert schema has required `sourceType`.
- Assert `sourceType` enum includes `local-file`, `conversation-summary`, `text`.
- Add a handler test using a temporary source file and vault path.
- Add a handler test using conversation-summary body.
- Assert response details include compile summary because tool should compile after ingest.

**Step 2: Run focused tests**

```bash
python -m pytest tests/test_tools.py -q
```

Expected: FAIL because tool is not registered.

**Step 3: Implement tool**

In `tools.py`:

- import `ingest_source`
- add `_spec("wiki_ingest", ...)` before `wiki_apply` or after `wiki_get`
- schema fields: `vaultPath`, `sourceType`, `title`, `inputPath`, `body`, `sessionId`, `messageRange`, `sourcePath`
- implement `wiki_ingest(args)`:
  - `initialize_vault(config)`
  - call `ingest_source(config, raw)`
  - call `compile_vault(config)`
  - return `_response(...)` with result plus compile summary

**Step 4: Verify**

```bash
python -m pytest tests/test_tools.py tests/test_ingest.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/tools.py tests/test_tools.py
git commit -m "feat: expose wiki source ingest tool"
```

---

## Task 7: Add failing typed upsert tests for entity pages

**Objective:** Define deterministic entity page creation/update behavior.

**Files:**
- Modify: `tests/test_apply.py`
- Modify later: `src/hermes_memory_wiki/apply.py`

**Step 1: Write failing tests**

Add tests for `op: upsert_entity`:

- requires `title`, `body`, non-empty `sourceIds`, and `entityType`
- writes `entities/<slug>.md`
- default id `entity.<slug>`
- frontmatter includes `pageType: entity`, `entityType`, `sourceIds`, `claims`, `aliases`, `status`, `confidence`, `updatedAt`
- body includes generated summary block and human notes block
- update by same title preserves existing id and human notes
- optional `lookup` updates an existing entity path and refuses wrong broad page type

**Step 2: Run focused failure**

```bash
python -m pytest tests/test_apply.py -q
```

Expected: FAIL for unsupported op.

---

## Task 8: Implement `upsert_entity`

**Objective:** Make entity upsert tests pass.

**Files:**
- Modify: `src/hermes_memory_wiki/apply.py`
- Test: `tests/test_apply.py`

**Step 1: Extend mutation dataclass**

Add fields:

- `entity_type: str | None`
- `aliases: list[str]`

Consider a `page_kind` or operation-specific helper rather than overloading too much.

**Step 2: Extend normalization**

In `normalize_mutation`:

- recognize `upsert_entity`
- require title/body/sourceIds/entityType
- optional lookup, claims, aliases, questions, contradictions, confidence, status
- reuse existing `_claims`, `_string_list`, `_optional_confidence`

**Step 3: Implement apply helper**

Add `_apply_upsert_entity(config, mutation)`:

- if lookup supplied, resolve via `get_page`; require kind/pageType entity
- else deterministic path from title slug
- parse existing page if present
- preserve existing id when present
- write frontmatter and body
- replace managed block with heading `Summary`
- ensure human notes block

**Step 4: Verify**

```bash
python -m pytest tests/test_apply.py -q
```

Expected: PASS or only concept tests still absent.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/apply.py tests/test_apply.py
git commit -m "feat: upsert entity wiki pages"
```

---

## Task 9: Add and implement typed upsert for concept pages

**Objective:** Add source-backed concept page creation/update.

**Files:**
- Modify: `tests/test_apply.py`
- Modify: `src/hermes_memory_wiki/apply.py`

**Step 1: Write failing concept tests**

Add tests for `op: upsert_concept`:

- requires `title`, `body`, and non-empty `sourceIds`
- writes `concepts/<slug>.md`
- id defaults to `concept.<slug>`
- no `entityType`
- includes claims/questions/contradictions/confidence/status/updatedAt
- preserves human notes and existing id on refresh
- lookup update refuses wrong page type

**Step 2: Run tests**

```bash
python -m pytest tests/test_apply.py -q
```

Expected: FAIL until implemented.

**Step 3: Implement shared typed upsert helper**

Refactor common entity/concept code into `_apply_upsert_typed_page(config, mutation, kind)` or similar to avoid duplication.

**Step 4: Verify**

```bash
python -m pytest tests/test_apply.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/apply.py tests/test_apply.py
git commit -m "feat: upsert concept wiki pages"
```

---

## Task 10: Update `wiki_apply` tool schema and handler tests for typed upserts

**Objective:** Expose typed upserts through model-callable tool schema.

**Files:**
- Modify: `src/hermes_memory_wiki/tools.py`
- Modify: `tests/test_tools.py`

**Step 1: Write failing schema tests**

Update assertions:

- `wiki_apply` op enum includes `upsert_entity`, `upsert_concept`
- schema includes `entityType` and `aliases`
- handler can upsert an entity in a temp vault and response includes compile summary

**Step 2: Run tests**

```bash
python -m pytest tests/test_tools.py -q
```

Expected: FAIL until schema updated.

**Step 3: Implement schema changes**

Add properties in `tools.py`:

- `entityType`: string
- `aliases`: array of strings
- update `op` enum
- improve description: deterministic mutations for syntheses, typed entity/concept pages, and metadata repair

**Step 4: Verify**

```bash
python -m pytest tests/test_tools.py tests/test_apply.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/tools.py tests/test_tools.py
git commit -m "feat: expose typed wiki page upserts"
```

---

## Task 11: Add workflow integration smoke test

**Objective:** Prove conversation source → entity/concept upsert → compile/search/get works together.

**Files:**
- Modify: `tests/test_smoke_workflow.py` or create `tests/test_authoring_workflow.py`

**Step 1: Write integration test**

Use registered tool handlers or core functions to:

1. Initialize temp vault.
2. Call `wiki_ingest` with `sourceType: conversation-summary` and body containing user guidance.
3. Call `wiki_apply` with `op: upsert_entity` or `upsert_concept`, using the source id returned by ingest.
4. Call `wiki_search` keyword mode for a term from the page.
5. Call `wiki_get` for the page id.
6. Call `wiki_lint` and assert no errors.

**Step 2: Run test**

```bash
python -m pytest tests/test_authoring_workflow.py -q
```

Expected: PASS after feature implementation.

**Step 3: Commit**

```bash
git add tests/test_authoring_workflow.py
git commit -m "test: cover conversation source authoring workflow"
```

---

## Task 12: Update README and docs

**Objective:** Document new tools and deterministic/LLM split.

**Files:**
- Modify: `README.md`
- Modify: `docs/schema.md` if present
- Modify: `docs/openclaw-feature-parity.md` if present
- Modify: `docs/development.md` if test counts/commands need updates

**Step 1: Update README tool list**

Add `wiki_ingest` to runtime toolset list.

**Step 2: Add authoring workflow section**

Document:

- tools are deterministic
- agent discretion creates source summaries and mutations
- use `wiki_ingest` for local/conversation sources
- use `wiki_apply create_synthesis`, `upsert_entity`, `upsert_concept`, `update_metadata` for structured changes

**Step 3: Update parity notes**

Explain that `wiki_ingest` mirrors OpenClaw `openclaw wiki ingest` for local files and adds Hermes conversation-summary/text source ingestion.

**Step 4: Run docs-related tests if any**

```bash
python -m pytest tests/test_skills.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/schema.md docs/openclaw-feature-parity.md docs/development.md
git commit -m "docs: document source ingest authoring workflow"
```

Adjust `git add` paths to existing modified docs only.

---

## Task 13: Update bundled and native skill guidance

**Objective:** Teach future agents to use `wiki_ingest` and typed upserts instead of direct Markdown writes.

**Files:**
- Modify: `src/hermes_memory_wiki/skills/wiki-authoring/SKILL.md`
- Modify: `src/hermes_memory_wiki/skills/wiki-maintainer/SKILL.md`
- Modify: `src/hermes_memory_wiki/skills/wiki-search/SKILL.md` only if search workflow changes
- Modify copied native skills under `~/.hermes/skills/memory-wiki/...` only after code/docs are done and with explicit sync step; avoid committing those external paths.

**Step 1: Update skill text**

`wiki-authoring` must say:

- use `wiki_get`/`wiki_search` before editing
- use `wiki_ingest` for local files, text, and conversation summaries
- source summaries from conversations are source pages and should be cited by `sourceIds`
- use `wiki_apply upsert_entity`/`upsert_concept` for typed source-backed pages
- use `create_synthesis` for cross-source synthesis
- tools are deterministic; the LLM chooses content and claims
- run compile/lint/reindex verification loop

**Step 2: Update tests**

If `tests/test_skills.py` checks content, update or add assertions for `wiki_ingest`, `conversation-summary`, and typed upsert mentions.

**Step 3: Run tests**

```bash
python -m pytest tests/test_skills.py -q
```

Expected: PASS.

**Step 4: Commit**

```bash
git add src/hermes_memory_wiki/skills tests/test_skills.py
git commit -m "docs: teach source-backed wiki authoring workflow"
```

---

## Task 14: Full offline verification

**Objective:** Verify all deterministic functionality before review.

**Files:** None.

**Step 1: Run compileall**

```bash
python -m compileall src tests
```

Expected: no syntax errors.

**Step 2: Run full offline suite**

```bash
python -m pytest -q
```

Expected: all offline tests pass with expected skips.

**Step 3: Run optional smoke through actual tools**

If a smoke script exists, run it without live OpenAI. Otherwise rely on `tests/test_authoring_workflow.py`.

**Step 4: Commit fixes if needed**

If verification required fixes, commit them with a focused message.

---

## Task 15: Review cycle

**Objective:** Use two-stage review before claiming complete.

**Files:** Any files flagged by reviewers.

**Step 1: Spec compliance review**

Delegate or perform a review against:

- `docs/plans/2026-05-28-source-ingest-and-conversation-authoring-design.md`
- this implementation plan
- acceptance criteria

Reviewer should answer: does implementation satisfy A, B, C and non-goals?

**Step 2: Code quality review**

Review for:

- path safety
- deterministic behavior
- test coverage
- no hidden LLM calls
- DRY/YAGNI
- skill/docs accuracy
- no accidental external-profile writes

**Step 3: Fix review issues**

Use `receiving-code-review` workflow if issues are found. Commit fixes.

**Step 4: Final verification**

Run:

```bash
python -m compileall src tests
python -m pytest -q
```

Expected: PASS.

**Step 5: Push branch**

```bash
git push -u origin feat/source-ingest-conversation-authoring
```

Open a PR if desired, or merge to main only after validation passes.

---

## Final acceptance checklist

- [ ] `wiki_ingest` registered and tested.
- [ ] `wiki_ingest` supports `local-file`.
- [ ] `wiki_ingest` supports `conversation-summary`.
- [ ] `wiki_ingest` supports `text` or the implementation explicitly documents why it deferred generic text.
- [ ] Ingest refresh preserves human notes and existing id.
- [ ] `wiki_apply` supports `upsert_entity`.
- [ ] `wiki_apply` supports `upsert_concept`.
- [ ] Typed upserts are deterministic and source-backed.
- [ ] No internal LLM calls were added to tools.
- [ ] Compile runs after ingest/apply writes.
- [ ] Skills/docs explain deterministic tools + LLM-discretion workflow.
- [ ] Offline tests pass.
- [ ] Review completed.
