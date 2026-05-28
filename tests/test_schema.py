from hermes_memory_wiki.schema import (
    WikiClaim,
    WikiEvidence,
    WikiPageSummary,
    infer_page_kind,
    page_kind_from_path,
    to_page_summary,
)


def test_page_kind_is_derived_from_openclaw_queryable_directory():
    assert infer_page_kind("sources/interview-1.md") == "source"
    assert infer_page_kind("entities/ada-lovelace.md") == "entity"
    assert infer_page_kind("concepts/analytical-engine.md") == "concept"
    assert infer_page_kind("syntheses/history.md") == "synthesis"
    assert infer_page_kind("reports/weekly.md") == "report"
    assert infer_page_kind("misc/note.md") is None
    assert page_kind_from_path("entities/ada.md", {"pageType": "person"}) == "entity"
    assert page_kind_from_path("entities/ada.md", {"pageType": ""}) == "entity"


def test_to_page_summary_normalizes_id_title_source_ids_and_aliases():
    raw = """---
id: explicit-id
title: Ada Lovelace
sourceIds: interview-1
aliases: Countess of Lovelace
status: draft
confidence: 0.75
updatedAt: 2026-05-27
---
# Body Heading

Body text.
"""

    summary = to_page_summary("entities/ada-lovelace.md", raw)

    assert isinstance(summary, WikiPageSummary)
    assert summary.path == "entities/ada-lovelace.md"
    assert summary.kind == "entity"
    assert summary.page_type is None
    assert summary.entity_type is None
    assert summary.id == "explicit-id"
    assert summary.title == "Ada Lovelace"
    assert summary.source_ids == ["interview-1"]
    assert summary.aliases == ["Countess of Lovelace"]
    assert summary.status == "draft"
    assert summary.confidence == 0.75
    assert summary.updated_at == "2026-05-27"
    assert summary.body == "# Body Heading\n\nBody text.\n"
    assert summary.frontmatter["id"] == "explicit-id"


def test_to_page_summary_defaults_title_and_id_from_markdown_and_path():
    raw = "# Project Alpha\n\nNo frontmatter.\n"

    summary = to_page_summary("concepts/project-alpha.md", raw)

    assert summary is not None
    assert summary.kind == "concept"
    assert summary.id == "concept:project-alpha"
    assert summary.title == "Project Alpha"
    assert summary.source_ids == []
    assert summary.aliases == []


def test_to_page_summary_normalizes_claims_with_evidence_and_ignores_invalid_claims():
    raw = """---
title: Claims
claims:
  - id: c1
    text: Ada wrote the first published computer program.
    status: supported
    confidence: high
    evidence:
      - kind: source
        sourceId: source-1
        path: sources/source-1.md
        lines: [10, 12]
        confidence: 0.9
        note: annotated note
      - invalid evidence is ignored
  - text: ""
  - 42
---
Body
"""

    summary = to_page_summary("entities/ada.md", raw)

    assert summary is not None
    assert len(summary.claims) == 1
    claim = summary.claims[0]
    assert isinstance(claim, WikiClaim)
    assert claim.id == "c1"
    assert claim.text == "Ada wrote the first published computer program."
    assert claim.status == "supported"
    assert claim.confidence == "high"
    assert len(claim.evidence) == 1
    evidence = claim.evidence[0]
    assert isinstance(evidence, WikiEvidence)
    assert evidence.kind == "source"
    assert evidence.source_id == "source-1"
    assert evidence.path == "sources/source-1.md"
    assert evidence.lines == "[10, 12]"
    assert evidence.confidence == 0.9
    assert evidence.note == "annotated note"


def test_to_page_summary_normalizes_questions_and_contradictions_to_strings():
    raw = """---
title: Open Issues
questions:
  - When did Ada meet Babbage?
  - text: Should mapping questions stringify?
contradictions: Single contradiction
---
Body
"""

    summary = to_page_summary("reports/open-issues.md", raw)

    assert summary is not None
    assert summary.questions == ["When did Ada meet Babbage?", "Should mapping questions stringify?"]
    assert summary.contradictions == ["Single contradiction"]


def test_to_page_summary_supports_person_card_and_route_question_fields():
    raw = """---
pageType: entity
entityType: person
person: Ada Lovelace
role: Mathematician
bestUsedFor:
  - computing history
routing:
  priority: high
routes:
  - math
  - history
topics: algorithms
---
# Ada
"""

    summary = to_page_summary("entities/ada.md", raw)

    assert summary is not None
    assert summary.kind == "entity"
    assert summary.page_type == "entity"
    assert summary.entity_type == "person"
    assert summary.person == "Ada Lovelace"
    assert summary.role == "Mathematician"
    assert summary.best_used_for == ["computing history"]
    assert summary.routing == {"priority": "high"}
    assert summary.routes == ["math", "history"]
    assert summary.topics == ["algorithms"]
    assert summary.person_card is not None
    assert summary.person_card.name == "Ada Lovelace"
    assert summary.person_card.role == "Mathematician"


def test_person_card_mapping_preferred_over_legacy_top_level_fields():
    raw = """---
person: Legacy Name
role: Legacy Role
bestUsedFor: legacy routing
topics: legacy-topic
routing:
  legacy: route
routes: legacy-route
personCard:
  name: Ada Lovelace
  role: Mathematician
  bestUsedFor:
    - computing history
  topics:
    - algorithms
  routing:
    priority: high
  routes:
    - math
---
# Ada
"""

    summary = to_page_summary("entities/ada.md", raw)

    assert summary is not None
    assert summary.person == "Ada Lovelace"
    assert summary.role == "Mathematician"
    assert summary.best_used_for == ["computing history"]
    assert summary.topics == ["algorithms"]
    assert summary.routing == {"priority": "high"}
    assert summary.routes == ["math"]
    assert summary.person_card is not None
    assert summary.person_card.name == "Ada Lovelace"


def test_legacy_aliases_are_not_parsed_as_openclaw_fields():
    raw = """---
title: Strict Fields
source_ids: legacy-source
sourceId: legacy-source-id
source_id: legacy-source-underscore
updated_at: 2026-05-27
best_used_for: legacy routing
claims:
  - id: c1
    text: Strict claim.
    evidence:
      - type: source
        source_id: legacy-evidence-source
---
Body
"""

    summary = to_page_summary("concepts/strict.md", raw)

    assert summary is not None
    assert summary.source_ids == []
    assert summary.updated_at is None
    assert summary.best_used_for == []
    assert summary.person_card is None
    assert summary.claims[0].evidence[0].kind is None
    assert summary.claims[0].evidence[0].source_id is None


def test_entity_page_type_person_remains_broad_kind_entity_with_subtype_separate():
    raw = """---
id: entity.ada
title: Ada Lovelace
pageType: entity
entityType: person
---
# Ada
"""

    summary = to_page_summary("entities/ada.md", raw)

    assert summary is not None
    assert summary.kind == "entity"
    assert summary.page_type == "entity"
    assert summary.entity_type == "person"
