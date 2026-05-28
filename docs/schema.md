# OpenClaw-Compatible Wiki Schema

`hermes-memory-wiki` stores Markdown pages in an OpenClaw-compatible information architecture while using Hermes-native tooling and metadata directories. The schema is clean-slate: broad page kind comes from the page directory, and entity subtypes are stored separately.

## Vault tree

A initialized vault contains queryable content directories, human/helper files, and Hermes metadata:

```text
<vault>/
  AGENTS.md
  WIKI.md
  index.md
  inbox.md
  entities/
    index.md
  concepts/
    index.md
  syntheses/
    index.md
  sources/
    index.md
  reports/
    index.md
    open-questions.md
    contradictions.md
    low-confidence.md
    claim-health.md
  _attachments/
  _views/
  .hermes-wiki/
    locks/
    cache/
      agent-digest.json
      claims.jsonl
      search-docs.jsonl
      compile.log.jsonl
      lint-report.md
      lint-report.json
    vector/
```

Only immediate Markdown files under `entities/`, `concepts/`, `syntheses/`, `sources/`, and `reports/` are queryable wiki pages. Directory `index.md` pages are generated views, not corpus pages.

## Page kind inference

Page kind is inferred from the first path segment. `pageType` must match the inferred broad kind.

| Path pattern | Inferred kind | Required `pageType` | Notes |
| --- | --- | --- | --- |
| `entities/*.md` | `entity` | `entity` | Use `entityType` for person, organization, project, system, product, etc. |
| `concepts/*.md` | `concept` | `concept` | Durable ideas, terms, systems of thought. |
| `syntheses/*.md` | `synthesis` | `synthesis` | Cross-page summaries, decisions, analyses. |
| `sources/*.md` | `source` | `source` | Evidence/source records. |
| `reports/*.md` | `report` | `report` | Generated or maintained health/report pages. |

## `pageType` vs `entityType`

`pageType` is the broad page kind and is constrained by directory. It is not a subtype field.

`entityType` is only for entity subtypes. A person page must be represented as:

```yaml
pageType: entity
entityType: person
```

Do not write `pageType: person`; lint reports this as `page-type-mismatch` for files under `entities/`.

## Full frontmatter reference

Supported OpenClaw-compatible fields are preserved by the parser and/or surfaced in summaries and compiled cache files:

| Field | Type | Applies to | Purpose |
| --- | --- | --- | --- |
| `id` | string | all pages | Stable page ID. Required by lint. |
| `title` | string | all pages | Human-readable title. Required by lint. |
| `pageType` | string | all queryable pages | Must equal inferred broad kind. Required by lint. |
| `entityType` | string | entity pages | Entity subtype such as `person`, `organization`, `project`, `system`. |
| `canonicalId` | string | entity/concept pages | Stable canonical identity for duplicate avoidance. |
| `aliases` | list of strings | all pages | Alternate names for lookup/search. |
| `sourceIds` | list of strings | entity/concept/synthesis pages | Source page IDs supporting this page. Required by authoring discipline for non-source/non-report pages. |
| `claims` | list of claim objects | entity/concept/synthesis/source pages | Structured assertions with evidence. |
| `contradictions` | list | all pages | Known contradictions or contested notes. |
| `questions` | list | all pages | Open questions surfaced in reports. |
| `confidence` | number | pages/claims/evidence | Confidence score; low values are lint/report signals. |
| `privacyTier` | string | pages/evidence | Privacy classification such as `standard` or `sensitive`. |
| `personCard` | mapping | person entities | Optional richer person summary metadata. |
| `person` | string | person entities | Parsed into `personCard.name` compatibility summary. |
| `role` | string | person entities | Parsed into `personCard.role` compatibility summary. |
| `relationships` | list | entities | Relationships to other pages/entities. |
| `bestUsedFor` | list | entities/concepts | Routing hints for when the page is useful. |
| `notEnoughFor` | list | entities/concepts | Routing hints for when the page is insufficient. |
| `sourceType` | string | source pages | Kind of source, e.g. note, document, URL, transcript. |
| `provenanceMode` | string | source pages | How the source path/provenance should be interpreted. |
| `sourcePath` | string | source pages | Source file/path/URL reference. |
| `bridgeRelativePath` | string | source pages | Compatibility provenance field preserved when present. |
| `bridgeWorkspaceDir` | string | source pages | Compatibility provenance field preserved when present. |
| `unsafeLocalConfiguredPath` | string | source pages | Explicit local provenance field; treat as potentially sensitive. |
| `unsafeLocalRelativePath` | string | source pages | Explicit local provenance field; treat as potentially sensitive. |
| `lastRefreshedAt` | timestamp string | source pages | Last time source metadata/content was refreshed. |
| `updatedAt` | timestamp string | all pages/claims/evidence | Last update timestamp. |
| `status` | string | all pages/claims | Lifecycle state such as `active`, `draft`, `archived`, `contested`. |

Hermes extensions may exist when they do not conflict with these fields. `.hermes-wiki/` and `.hermes-wiki/vector/` are Hermes-native metadata/cache locations.

## Claim and evidence schema

Claims live in page frontmatter. There is no top-level `claims/` page directory.

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

Evidence entries should point at source pages or source-relative locations. Use stable `sourceId` values where possible and include `path` plus `lines` for precise citation.

## Page templates

### Entity page

```markdown
---
id: entity.ada
title: Ada Lovelace
pageType: entity
entityType: person
canonicalId: person.ada-lovelace
aliases:
  - Ada
sourceIds:
  - source.ada-notes
claims:
  - id: claim.ada.role
    text: Ada is documented as an example person entity.
    status: active
    confidence: 0.9
    evidence:
      - kind: source
        sourceId: source.ada-notes
        path: sources/ada-notes.md
        lines: "4-8"
        weight: 1
    updatedAt: "2026-05-28T00:00:00Z"
status: active
updatedAt: "2026-05-28T00:00:00Z"
---
# Ada Lovelace

Human notes outside generated blocks.
```

### Concept page

```markdown
---
id: concept.memory-wiki
title: Memory Wiki
pageType: concept
aliases:
  - wiki memory
sourceIds:
  - source.design-notes
claims: []
status: active
---
# Memory Wiki
```

### Synthesis page

```markdown
---
id: synthesis.schema-summary
title: Schema Summary
pageType: synthesis
sourceIds:
  - source.design-notes
  - source.lint-results
claims: []
questions: []
status: active
---
# Schema Summary
```

### Source page

```markdown
---
id: source.design-notes
title: Design Notes
pageType: source
sourceType: document
sourcePath: docs/design-notes.md
provenanceMode: repository
lastRefreshedAt: "2026-05-28T00:00:00Z"
status: active
---
# Design Notes
```

### Report page

```markdown
---
id: report.open-questions
title: Open Questions
pageType: report
status: active
updatedAt: "2026-05-28T00:00:00Z"
---
# Open Questions

## Generated

<!-- hermes:wiki:open-questions:start -->
- No open questions right now.
<!-- hermes:wiki:open-questions:end -->
```

## Generated files and managed markers

`wiki_compile` creates or updates generated Markdown and cache outputs. Human prose should live outside managed blocks or inside explicit human blocks.

Generated markers use this shape:

```text
<!-- hermes:wiki:<name>:start -->
...
<!-- hermes:wiki:<name>:end -->
```

Human-preservation markers are:

```text
<!-- hermes:human:start -->
...
<!-- hermes:human:end -->
```

Lint markers are:

```text
<!-- hermes:wiki:lint:start -->
...
<!-- hermes:wiki:lint:end -->
```

Generated/managed outputs include root and directory indexes, report pages, `.hermes-wiki/cache/*`, and `.hermes-wiki/vector/*` when vector reindexing is enabled.

## Lint expectations

`wiki_lint` checks structural, provenance, quality, contradictions, open-question, broken-link, duplicate, and vector-index health. Important expectations:

- Every queryable page has non-empty `id`, `title`, and `pageType`.
- `pageType` equals the directory-derived kind.
- IDs and claim IDs are not duplicated.
- Claims should have evidence; missing evidence is reported.
- Low confidence and stale claims are surfaced for review.
- Broken wiki links, contradiction notes, and open questions are reported.
- Vector index issues are reported when indexed documents are missing or stale.

## Compile outputs

`wiki_compile` writes deterministic generated views and machine-readable cache files:

- `index.md`: root page counts and directory links.
- `entities/index.md`, `concepts/index.md`, `syntheses/index.md`, `sources/index.md`, `reports/index.md`: directory indexes.
- `reports/open-questions.md`: pages with open questions.
- `reports/contradictions.md`: contradiction notes and contested claim clusters.
- `reports/low-confidence.md`: low-confidence pages and claims.
- `reports/claim-health.md`: missing evidence, contested, stale, or unknown claim health records.
- `.hermes-wiki/cache/agent-digest.json`: page counts, claim count, claim health, and page summaries.
- `.hermes-wiki/cache/claims.jsonl`: structured claim stream.
- `.hermes-wiki/cache/search-docs.jsonl`: indexed search documents.
- `.hermes-wiki/cache/compile.log.jsonl`: compile update log.

Page counts are by broad kind (`entity`, not `person`).

## Correct and incorrect person pages

Correct person page:

```yaml
id: entity.ada
title: Ada Lovelace
pageType: entity
entityType: person
sourceIds:
  - source.ada-notes
```

Incorrect person page:

```yaml
id: entity.ada
title: Ada Lovelace
pageType: person
sourceIds:
  - source.ada-notes
```

The incorrect page is invalid because `entities/ada.md` infers kind `entity`, so lint expects `pageType: entity`.
