# OpenClaw Feature Parity Implementation Plan

> **For Hermes:** Execute this plan with `software-engineering-rigor`, `subagent-driven-development`, `test-driven-development`, `receiving-code-review`, and `verification-before-completion`.

## Goal

Correct the `hermes-memory-wiki` port so it mirrors the OpenClaw `memory-wiki` plugin as closely as practical for the local wiki data model and maintenance workflow. The central correction is to restore OpenClaw's information architecture: directory-derived broad page kinds, `pageType` matching those broad kinds, entity subtypes stored separately as `entityType`, source-backed structured claims, richer generated guidance, OpenClaw-like compile outputs, and OpenClaw-like lint/search/get/apply behavior.

## Approved design

Use **Option A: strict OpenClaw semantic parity, Hermes-native implementation**.

- Reimplement behavior natively in Python/Hermes.
- Do not depend on OpenClaw at runtime.
- Do not add compatibility support for current divergent Hermes pages; this is a clean-slate correction.
- Keep Hermes-specific vector/hybrid search as an additive feature, but index an OpenClaw-compatible page/claim corpus.
- Keep Hermes metadata directory naming (`.hermes-wiki`) while mirroring OpenClaw structure and semantics.

## Explicit non-goals

- No migration path for existing divergent pages such as `entities/*.md` with `pageType: person`.
- No compatibility shim that treats arbitrary `pageType` values as broad page kinds.
- No OpenClaw bridge-mode runtime dependency.
- No importing bundled OpenClaw JS from Hermes.
- No paid/live embedding calls in the default test suite.
- No changes to Hermes core; remain an additive plugin/package.

## Source references

Inspect and cross-check against these before implementing each relevant area:

- `docs/references/openclaw-memory-wiki-source-inventory.md`
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js`
  - prompt/tool guidance around lines 734-751;
  - schemas around lines 770-828;
  - memory palace regions around lines 341-415 if implementing status/list parity later.
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js`
  - page kind inference around lines 363-370;
  - page summary fields around lines 372-407;
  - vault directories/starter files around lines 411-508;
  - compile page groups/report generation around lines 511 onward;
  - search scoring regions around lines 1376-2208;
  - apply/mutation behavior around lines 2288-2450;
  - lint behavior around lines 3051-3279.
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md`

Do not import any of these source files at runtime. They are reference material only.

## Repository and branch

Repository:

```text
/home/langley/projects/hermes-memory-wiki
```

Implementation branch:

```bash
git checkout main
git pull origin main
git checkout -b feature/openclaw-memory-wiki-parity
```

Commit after every task or tightly related task group. Push the feature branch after successful milestones.

## Architecture target

Core modules remain pure Python with Hermes registration as a thin wrapper:

```text
src/hermes_memory_wiki/
  vault.py          # init, starter files, safe path listing
  schema.py         # markdown/frontmatter -> OpenClaw-compatible summaries
  compile.py        # index/report/digest generation
  lint.py           # OpenClaw-like structure/provenance/quality checks
  apply.py          # create_synthesis/update_metadata mutations
  search_keyword.py # deterministic local scoring over OpenClaw corpus
  vector_index.py   # Hermes extension: local vector documents over same corpus
  hybrid_search.py  # Hermes extension: keyword/vector fusion
  tools.py          # Hermes tool handlers
  plugin.py         # plugin registration
```

If a module becomes too large, split only along clear boundaries; do not introduce broad abstractions before tests require them.

## Canonical data model

### Queryable directories

```text
entities/   -> entity
concepts/   -> concept
syntheses/  -> synthesis
sources/    -> source
reports/    -> report
```

### Required/support directories at init

```text
entities/
concepts/
syntheses/
sources/
reports/
_attachments/
_views/
.hermes-wiki/
.hermes-wiki/locks/
.hermes-wiki/cache/
.hermes-wiki/vector/
```

### `pageType` rule

`pageType` is required and must equal the broad kind inferred from path.

Examples:

- `entities/ada.md` -> `pageType: entity`, `entityType: person`
- `concepts/engine.md` -> `pageType: concept`
- `syntheses/wiki-schema.md` -> `pageType: synthesis`
- `sources/openclaw-source.md` -> `pageType: source`
- `reports/open-questions.md` -> `pageType: report`

### Supported page frontmatter fields

Support and preserve these OpenClaw-compatible fields:

```text
id
pageType
entityType
canonicalId
aliases
sourceIds
claims
contradictions
questions
confidence
privacyTier
personCard
relationships
bestUsedFor
notEnoughFor
sourceType
provenanceMode
sourcePath
bridgeRelativePath
bridgeWorkspaceDir
unsafeLocalConfiguredPath
unsafeLocalRelativePath
lastRefreshedAt
updatedAt
status
```

Hermes-specific metadata may remain only if it does not conflict and is documented as an extension.

### Claim schema

Claims are structured frontmatter on pages. There is no top-level `claims/` page directory.

```yaml
claims:
  - id: claim.example
    text: Example claim text.
    status: active
    confidence: 0.8
    evidence:
      - kind: source
        sourceId: source.example
        path: sources/example.md
        lines: "10-20"
        weight: 1
        note: Optional note.
        confidence: 0.9
        privacyTier: standard
        updatedAt: "2026-05-28T00:00:00Z"
    updatedAt: "2026-05-28T00:00:00Z"
```

## Verification commands

Default final verification:

```bash
python -m pytest -q
python -m compileall src tests scripts
python scripts/smoke_fake_hermes.py
```

If project tooling documents additional checks, run them too.

Live OpenAI/vector checks are opt-in only:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" pytest tests/live -v
```

Do not require live tests for final completion unless the user explicitly asks.

---

## Phase 0 — Discovery refresh and parity inventory

### Task 0.1: Refresh OpenClaw source inventory

**Objective:** Ensure the repo contains a current, implementation-useful parity inventory.

**Files:**

- Update: `docs/references/openclaw-memory-wiki-source-inventory.md`
- Optional create: `docs/openclaw-feature-parity.md`

**TDD / verification:** Documentation-only task, but verify paths and line ranges with `read_file`/`search_files` before editing. Do not invent source references.

**Required content:**

- OpenClaw vault directory list.
- OpenClaw page kind inference rules.
- OpenClaw page summary/frontmatter fields.
- OpenClaw claim/evidence schema.
- OpenClaw starter `AGENTS.md` and `WIKI.md` guidance.
- OpenClaw compile outputs/digests/reports.
- OpenClaw lint errors/warnings.
- OpenClaw apply operations.
- Explicit list of features deferred from this pass, if any.

**Commit:**

```bash
git add docs/references docs/openclaw-feature-parity.md
git commit -m "docs: refresh openclaw memory wiki parity inventory"
```

---

## Phase 1 — Schema and page-kind correction

### Task 1.1: Add RED tests for OpenClaw page taxonomy

**Objective:** Lock in the clean-slate OpenClaw semantics before production changes.

**Files:**

- Update/create: `tests/test_schema.py`
- Update/create: `tests/test_lint.py`
- Update/create: `tests/test_compile.py`

**Tests to add first:**

1. `entities/ada.md` with `pageType: entity` and `entityType: person` parses as kind/page type `entity`, subtype `person`.
2. `entities/ada.md` with `pageType: person` produces a lint error `page-type-mismatch`.
3. `concepts/engine.md` requires `pageType: concept`.
4. `syntheses/foo.md` requires `pageType: synthesis`.
5. `sources/foo.md` requires `pageType: source`.
6. `reports/foo.md` requires `pageType: report`.
7. Compile page counts group entities as `entity`, not `person`.

**RED command:**

```bash
pytest tests/test_schema.py tests/test_lint.py tests/test_compile.py -q
```

Expected: fail with current divergent behavior.

### Task 1.2: Implement directory-derived broad kind

**Objective:** Make schema parsing match OpenClaw: broad kind comes from path; `pageType` is metadata that must match broad kind.

**Files:**

- Update: `src/hermes_memory_wiki/schema.py`
- Update affected tests/factories.

**Implementation requirements:**

- Add canonical function, e.g. `infer_page_kind(relative_path: str) -> Literal["entity", "concept", "synthesis", "source", "report"] | None`.
- Use directory-derived kind for `WikiPageSummary.kind` / equivalent.
- Preserve `pageType` as a frontmatter field separately.
- Add fields for `entityType`, `canonicalId`, `privacyTier`, `personCard`, `relationships`, `bestUsedFor`, `notEnoughFor`, `provenanceMode`, `bridge*`, `unsafeLocal*`, `lastRefreshedAt`.
- Do not support `pageType: person` as a broad kind.

**GREEN command:**

```bash
pytest tests/test_schema.py -q
```

### Task 1.3: Update fixtures across the suite

**Objective:** Bring all tests and examples into the corrected schema.

**Files:**

- Update tests under `tests/`.
- Update docs/examples that currently use `pageType: person`.

**Rules:**

- Replace person page examples with `pageType: entity` + `entityType: person`.
- Keep concept pages as `pageType: concept`.
- Keep synthesis pages as `pageType: synthesis`.

**Verification:**

```bash
pytest tests/test_schema.py tests/test_compile.py tests/test_keyword_search.py tests/test_vector_index.py -q
```

**Commit:**

```bash
git add src/hermes_memory_wiki/schema.py tests docs
git commit -m "fix: align wiki page taxonomy with openclaw"
```

---

## Phase 2 — Lint parity

### Task 2.1: Add RED lint parity tests

**Objective:** Encode OpenClaw-style lint behavior.

**Files:**

- Update: `tests/test_lint.py`

**Tests:**

Errors:

- missing `id` -> `missing-id`
- duplicate page `id` -> `duplicate-id`
- duplicate claim `id` -> `duplicate-claim-id`
- missing `pageType` -> `missing-page-type`
- mismatched `pageType` -> `page-type-mismatch`
- missing title -> `missing-title`
- invalid markdown/frontmatter -> `invalid-markdown`

Warnings/issues:

- non-source/non-report page missing `sourceIds` -> `missing-source-ids`
- claim without evidence -> `claim-missing-evidence` or OpenClaw-matching code selected consistently
- low confidence page
- low confidence claim
- stale page
- stale claim
- contradiction present
- open question present
- broken wikilink
- missing provenance fields for `memory-bridge`, `memory-bridge-events`, and `memory-unsafe-local`/`unsafe-local` source types if those metadata fields are parsed.

**RED command:**

```bash
pytest tests/test_lint.py -q
```

### Task 2.2: Implement lint corrections

**Files:**

- Update: `src/hermes_memory_wiki/lint.py`
- Update: `src/hermes_memory_wiki/schema.py` if additional parsed fields are needed.

**Implementation requirements:**

- Compare `page.page_type` to inferred path kind.
- Treat broad kind as one of `entity/concept/synthesis/source/report`.
- Use severity categories close to OpenClaw: `structure`, `provenance`, `links`, `contradictions`, `open-questions`, `quality`.
- Ensure lint writes deterministic Markdown and JSON reports under `.hermes-wiki/cache/`.
- Do not silently normalize invalid schema into valid schema.

**GREEN command:**

```bash
pytest tests/test_lint.py -q
```

**Broader verification:**

```bash
pytest tests/test_schema.py tests/test_lint.py tests/test_tools.py -q
```

**Commit:**

```bash
git add src/hermes_memory_wiki/lint.py src/hermes_memory_wiki/schema.py tests
git commit -m "fix: enforce openclaw-compatible wiki lint rules"
```

---

## Phase 3 — Vault init and generated guidance parity

### Task 3.1: Add RED vault init tests

**Objective:** Ensure new vaults are initialized with OpenClaw-equivalent structure and guidance.

**Files:**

- Update: `tests/test_vault_init.py`

**Tests:**

- Creates required directories: `_attachments`, `_views`, `.hermes-wiki/locks`, `.hermes-wiki/cache`, `.hermes-wiki/vector`.
- `AGENTS.md` contains:
  - generated blocks are plugin-owned;
  - preserve human notes;
  - prefer source-backed claims;
  - prefer structured claims with evidence;
  - use `.hermes-wiki/cache/agent-digest.json` and `claims.jsonl`;
  - markdown pages are human view;
  - `entityType`, not `pageType`, stores entity subtype.
- `WIKI.md` explains architecture and taxonomy.
- `index.md` contains managed index block markers.
- Metadata state/log files are created safely.

**RED command:**

```bash
pytest tests/test_vault_init.py -q
```

### Task 3.2: Implement rich starter files

**Files:**

- Update: `src/hermes_memory_wiki/vault.py`
- Optional create: `src/hermes_memory_wiki/templates.py`

**Implementation requirements:**

- Add missing directories.
- Generate OpenClaw-equivalent `AGENTS.md` and `WIKI.md`, adjusted for Hermes names.
- Use Hermes markers:
  - `<!-- hermes:wiki:index:start -->`
  - `<!-- hermes:wiki:index:end -->`
  - `<!-- hermes:wiki:generated:start -->`
  - `<!-- hermes:wiki:generated:end -->`
  - `<!-- hermes:human:start -->`
  - `<!-- hermes:human:end -->`
  - `<!-- hermes:wiki:lint:start -->`
  - `<!-- hermes:wiki:lint:end -->`
- Preserve existing starter files if present; init should not overwrite human-edited files.

**GREEN command:**

```bash
pytest tests/test_vault_init.py -q
```

**Commit:**

```bash
git add src/hermes_memory_wiki/vault.py tests/test_vault_init.py
git commit -m "fix: expand wiki vault initialization guidance"
```

---

## Phase 4 — Compile parity

### Task 4.1: Add RED compile output tests

**Objective:** Make compile generate OpenClaw-like indexes, dashboards, and machine digests.

**Files:**

- Update: `tests/test_compile.py`

**Tests:**

- Root `index.md` totals pages and claims by broad page kind.
- Directory indexes exist:
  - `entities/index.md`
  - `concepts/index.md`
  - `sources/index.md`
  - `syntheses/index.md`
  - `reports/index.md`
- Reports exist:
  - `reports/open-questions.md`
  - `reports/contradictions.md`
  - `reports/low-confidence.md`
  - `reports/claim-health.md`
- `.hermes-wiki/cache/agent-digest.json` includes page summaries and claim counts.
- `.hermes-wiki/cache/claims.jsonl` contains one structured line per claim with page path/page id/claim id/evidence/confidence/status.
- Generated blocks are replaced deterministically without overwriting human notes.

**RED command:**

```bash
pytest tests/test_compile.py -q
```

### Task 4.2: Implement compile corrections

**Files:**

- Update: `src/hermes_memory_wiki/compile.py`
- Update: `src/hermes_memory_wiki/schema.py` if digest needs more fields.

**Implementation requirements:**

- Use compile groups: `source`, `entity`, `concept`, `synthesis`, `report`.
- Ensure report pages have `pageType: report`, stable IDs, and managed generated blocks.
- Build claim health from structured claims.
- Include questions and contradictions reports.
- Preserve human blocks outside managed markers.
- Write deterministic JSON/JSONL with stable ordering.

**GREEN command:**

```bash
pytest tests/test_compile.py -q
```

**Broader verification:**

```bash
pytest tests/test_compile.py tests/test_lint.py tests/test_reindex.py -q
```

**Commit:**

```bash
git add src/hermes_memory_wiki/compile.py src/hermes_memory_wiki/schema.py tests
git commit -m "fix: align wiki compile outputs with openclaw"
```

---

## Phase 5 — Apply/get/search parity

### Task 5.1: Add RED `wiki_apply` tests

**Objective:** Ensure mutation behavior mirrors OpenClaw's supported operations.

**Files:**

- Update: `tests/test_apply.py`

**Tests:**

- `create_synthesis` requires title, body, and at least one `sourceId`.
- Creates `syntheses/<slug>.md` with:
  - `id: synthesis.<slug>`
  - `pageType: synthesis`
  - `title`
  - `sourceIds`
  - `claims`
  - `contradictions`
  - `questions`
  - `confidence`
  - `status: active` default
  - `updatedAt`
- Body uses generated summary block and human notes block.
- `update_metadata` requires lookup.
- `update_metadata` narrowly updates `sourceIds`, `claims`, `contradictions`, `questions`, `confidence`, `status`, `updatedAt` while preserving body/human blocks.
- Unsupported create-entity/create-concept operations are not added in this parity pass unless explicitly approved later.

**RED command:**

```bash
pytest tests/test_apply.py -q
```

### Task 5.2: Implement apply parity

**Files:**

- Update: `src/hermes_memory_wiki/apply.py`
- Update: `src/hermes_memory_wiki/tools.py` if schemas/details need corrections.

**GREEN command:**

```bash
pytest tests/test_apply.py tests/test_tools.py -q
```

### Task 5.3: Add RED search/get tests

**Objective:** Search and get should expose OpenClaw-relevant metadata and lookup behavior.

**Files:**

- Update: `tests/test_keyword_search.py`
- Update: `tests/test_hybrid_search.py`
- Update: `tests/test_get.py`
- Update: `tests/test_vector_index.py`

**Tests:**

Search corpus includes:

- title
- path
- id
- aliases
- `pageType`
- `entityType`
- `sourceIds`
- body
- claims
- questions
- contradictions
- important metadata fields

Search/get behavior:

- lookup by exact path
- path without `.md`
- basename
- page ID
- title
- alias
- claim search returns matched claim ID when relevant
- result metadata includes broad kind/page type/entity type/source IDs/confidence/status/updatedAt
- vector documents use corrected broad kind and include claim documents.

**RED command:**

```bash
pytest tests/test_keyword_search.py tests/test_hybrid_search.py tests/test_get.py tests/test_vector_index.py -q
```

### Task 5.4: Implement search/get corrections

**Files:**

- Update: `src/hermes_memory_wiki/search_keyword.py`
- Update: `src/hermes_memory_wiki/hybrid_search.py`
- Update: `src/hermes_memory_wiki/vector_index.py`
- Update: `src/hermes_memory_wiki/tools.py`

**Implementation requirements:**

- Do not let old arbitrary `pageType` values define broad kind.
- Add OpenClaw-like metadata to results.
- Keep vector/hybrid search optional and deterministic in tests with fake embeddings.
- Ensure keyword fallback works without vector index/provider.

**GREEN command:**

```bash
pytest tests/test_keyword_search.py tests/test_hybrid_search.py tests/test_get.py tests/test_vector_index.py -q
```

**Commit:**

```bash
git add src/hermes_memory_wiki tests
git commit -m "fix: align wiki apply search and get behavior"
```

---

## Phase 6 — Source ingest parity, if current port has partial support

### Task 6.1: Inventory current ingest/import code

**Objective:** Decide whether source ingest is already partially present and can be finished in this pass.

**Files to inspect:**

- `src/hermes_memory_wiki/tools.py`
- `src/hermes_memory_wiki/apply.py`
- `src/hermes_memory_wiki/vault.py`
- `tests/test_import.py`
- `tests/test_smoke_workflow.py`

**Decision rule:**

- If an ingest/import tool or helper already exists, align it now.
- If not, document as a parity gap and create a follow-up issue/plan item; do not expand scope without user approval.

### Task 6.2: If in scope, add RED ingest tests

**Files:**

- Update/create: `tests/test_import.py` or `tests/test_ingest.py`

**Tests:**

- Ingest UTF-8 local file as `sources/<slug>.md`.
- Reject binary file.
- Source page frontmatter:
  - `pageType: source`
  - `id: source.<slug>`
  - `title`
  - `sourceType: local-file`
  - `sourcePath`
  - `ingestedAt`
  - `updatedAt`
  - `status: active`
- Body contains Source, Content fenced block, and human Notes block.
- Compile runs or returns files requiring compile according to existing tool design.

**Verification:**

```bash
pytest tests/test_import.py tests/test_smoke_workflow.py -q
```

**Commit if implemented:**

```bash
git add src/hermes_memory_wiki tests docs
git commit -m "fix: align source ingest with openclaw wiki model"
```

---

## Phase 7 — Skills and documentation

### Task 7.1: Add schema documentation

**Files:**

- Create: `docs/schema.md`
- Update: `docs/configuration.md`
- Update: `docs/development.md`
- Update: `docs/installation.md` if install/init behavior changed.

**`docs/schema.md` must include:**

- vault tree
- page kind inference table
- `pageType` vs `entityType`
- full frontmatter reference
- claim/evidence schema
- page templates for entity/concept/synthesis/source/report
- generated files and managed markers
- lint expectations
- compile outputs
- examples of correct and incorrect person pages

### Task 7.2: Update bundled skills

**Files:**

- Update: `src/hermes_memory_wiki/skills/wiki-search/SKILL.md`
- Update: `src/hermes_memory_wiki/skills/wiki-authoring/SKILL.md`
- Update: `src/hermes_memory_wiki/skills/wiki-maintainer/SKILL.md`

**Required skill changes:**

`wiki-search`:

- Explain when to use the wiki.
- Search first, then get exact page.
- Cite page paths/claim IDs when relevant.
- Reindex if search freshness matters.

`wiki-authoring`:

- Include schema section.
- Directory taxonomy.
- `pageType` vs `entityType`.
- Source-backed claim discipline.
- Evidence format.
- Require `sourceIds` on non-source/non-report pages.
- Compile/lint/reindex after changes.

`wiki-maintainer`:

- Maintenance loop: `wiki_status`, `wiki_compile`, `wiki_lint`, `wiki_reindex`, search smoke check.
- Generated block/human block preservation.
- Duplicate entity/concept avoidance.
- Claim health, contradiction, open-question reports.

**Tests:**

- Update `tests/test_skills.py` to assert skills mention OpenClaw-compatible schema terms and no longer imply `pageType: person` is valid.

**Verification:**

```bash
pytest tests/test_skills.py -q
```

**Commit:**

```bash
git add docs src/hermes_memory_wiki/skills tests/test_skills.py
git commit -m "docs: document openclaw-compatible wiki schema"
```

---

## Phase 8 — Tool and plugin integration

### Task 8.1: Add/adjust tool schema tests

**Files:**

- Update: `tests/test_tools.py`
- Update: `tests/test_user_plugin_layout.py`
- Update: `tests/test_smoke_workflow.py`

**Tests:**

- `wiki_status` reports corrected directories/cache/vector status.
- `wiki_compile` returns broad page counts and claim count.
- `wiki_lint` reports corrected issue categories/counts.
- `wiki_reindex` builds vectors/documents from corrected corpus.
- `wiki_search` returns OpenClaw-relevant result metadata.
- `wiki_get` returns OpenClaw-relevant page metadata.
- `wiki_apply` uses corrected mutation semantics.
- Plugin registration remains unchanged and toolset remains `memory_wiki`.

**Verification:**

```bash
pytest tests/test_tools.py tests/test_user_plugin_layout.py tests/test_smoke_workflow.py -q
```

### Task 8.2: Implement tool response corrections

**Files:**

- Update: `src/hermes_memory_wiki/tools.py`
- Update: `src/hermes_memory_wiki/plugin.py` only if skill/tool registration metadata needs updates.

**Commit:**

```bash
git add src/hermes_memory_wiki tests
git commit -m "fix: expose openclaw-compatible wiki tool metadata"
```

---

## Phase 9 — End-to-end parity smoke workflow

### Task 9.1: Add or update full fake Hermes smoke workflow

**Files:**

- Update: `scripts/smoke_fake_hermes.py`
- Update: `tests/test_smoke_workflow.py`

**Workflow:**

1. Initialize temp vault.
2. Create a source page or use source ingest if implemented.
3. Create an entity page with `pageType: entity`, `entityType: person`, `sourceIds`, and a claim with evidence.
4. Create a concept page with source-backed claim.
5. Use `wiki_apply` to create a synthesis.
6. Run compile.
7. Run lint.
8. Run reindex with fake embeddings.
9. Search by entity name, concept name, alias, and claim text.
10. Get page by ID/path/title/alias.
11. Assert generated reports/digests exist.
12. Assert no structural errors.

**Verification:**

```bash
pytest tests/test_smoke_workflow.py -q
python scripts/smoke_fake_hermes.py
```

**Commit:**

```bash
git add scripts tests
git commit -m "test: add openclaw parity smoke workflow"
```

---

## Phase 10 — Review and fix loop

### Task 10.1: Spec compliance review

Spawn a reviewer subagent with this scope:

- Compare implemented behavior against OpenClaw source references.
- Verify no clean-slate compatibility shims for old Hermes divergent schema.
- Verify page kind, `pageType`, `entityType`, claim/evidence, compile, lint, search/get/apply, starter guidance, docs, and skills match the approved design.
- Return concrete file/line issues only.

If issues are found:

1. Load/use `receiving-code-review`.
2. Spawn a fix implementer subagent for scoped fixes.
3. Run targeted tests.
4. Rerun spec compliance review.

### Task 10.2: Code quality review

Spawn a second reviewer only after spec compliance passes.

Scope:

- Python API clarity.
- Determinism.
- Test quality.
- Path safety.
- No live network in default tests.
- No unnecessary broad rewrites.
- No fragile reliance on OpenClaw installed paths at runtime.

Handle issues through `receiving-code-review` and scoped fixes.

---

## Phase 11 — Final verification and merge

### Task 11.1: Inspect repo state before final verification

```bash
git status --short --branch
git clean -ndX
```

Do not delete ignored/generated artifacts unless clearly safe and separately justified.

### Task 11.2: Run full verification

```bash
python -m pytest -q
python -m compileall src tests scripts
python scripts/smoke_fake_hermes.py
```

If installed editable package verification is appropriate:

```bash
python -m pip install -e .
python -m pytest -q
```

Optional live tests only if explicitly enabled:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" pytest tests/live -v
```

### Task 11.3: Inspect final diff/history

```bash
git status --short --branch
git log --oneline --decorate -10
git diff main...HEAD --stat
git diff main...HEAD -- docs src tests scripts pyproject.toml
```

### Task 11.4: Push and merge after validation

```bash
git push origin feature/openclaw-memory-wiki-parity
git checkout main
git pull origin main
git merge --no-ff feature/openclaw-memory-wiki-parity
git push origin main
```

If branch protection prevents direct merge, create a PR instead:

```bash
gh pr create --fill --base main --head feature/openclaw-memory-wiki-parity
```

---

## Done criteria

- New vault init mirrors OpenClaw structure with Hermes metadata naming.
- Broad page kind is inferred from directory.
- `pageType` must match broad kind.
- Entity subtype uses `entityType`.
- OpenClaw-compatible frontmatter fields are parsed/preserved.
- Structured claim/evidence model is documented, linted, compiled, and searchable.
- Compile writes indexes, reports, `agent-digest.json`, and `claims.jsonl` deterministically.
- Lint catches OpenClaw-like structural/provenance/quality issues.
- Apply/get/search/tool responses expose corrected metadata.
- Skills and docs teach the correct model.
- Default tests and fake smoke workflow pass without network credentials.
- Spec compliance review and code quality review both pass.
- Final verification passes fresh.
- Feature branch is pushed and merged to `main` only after validation.
