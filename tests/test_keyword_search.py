from __future__ import annotations

import pytest

from hermes_memory_wiki.markdown import HERMES_GENERATED_END, HERMES_GENERATED_START
from hermes_memory_wiki.schema import PersonCard, WikiClaim, WikiEvidence, WikiPageSummary
from hermes_memory_wiki.search_keyword import (
    build_page_search_text,
    build_query_tokens,
    build_snippet,
    keyword_search,
    score_page,
)


class _SetToken:
    def __init__(self, text: str, hash_value: int) -> None:
        self.text = text
        self.hash_value = hash_value

    def __str__(self) -> str:
        return self.text

    def __hash__(self) -> int:
        return self.hash_value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _SetToken) and self.text == other.text


def test_generated_related_blocks_removed_from_snippet_text() -> None:
    raw = (
        "Human-authored overview line.\n\n"
        f"{HERMES_GENERATED_START}\n"
        "## Related\n\n"
        "Generated related block should not appear.\n"
        f"{HERMES_GENERATED_END}\n\n"
        "Another human line.\n"
    )

    assert build_snippet(raw, "generated related") == "Human-authored overview line."


def test_frontmatter_removed_from_snippet_text() -> None:
    raw = "---\ntitle: Secret YAML Title\naliases:\n  - hidden-alias\n---\n# Visible Heading\nUseful body text.\n"

    assert build_snippet(raw, "Secret YAML") == "# Visible Heading"


def test_query_tokens_deduplicate_and_ignore_tiny_tokens() -> None:
    assert build_query_tokens("AI, ai! A b ok OK user@example.com x") == ["ai", "ok", "user@example.com"]


def test_exact_query_line_chosen_for_snippet() -> None:
    raw = "alpha beta appears separately.\nNeedle phrase appears exactly here.\nNeedle appears but phrase is split.\n"

    assert build_snippet(raw, "needle phrase") == "Needle phrase appears exactly here."


def test_fallback_snippet_chooses_first_meaningful_body_line() -> None:
    raw = "\n---\n\n# First meaningful body line\nSecond body line.\n"

    assert build_snippet(raw, "missing") == "# First meaningful body line"


def test_page_search_text_includes_summary_fields_claims_and_evidence() -> None:
    page = WikiPageSummary(
        path="entities/langley.md",
        kind="entity",
        id="entity.langley",
        page_type="entity",
        entity_type="person",
        title="Langley",
        source_ids=["source-alpha"],
        aliases=["LGL"],
        questions=["How should Langley be routed?"],
        contradictions=["Conflicting routing note"],
        best_used_for=["Python tests"],
        routing={"code": ["pytest", "review"], "ops": {"deploy": "manual"}},
        routes=["memory"],
        topics=["wiki search"],
        person="Langley Human",
        role="Developer",
        claims=[
            WikiClaim(
                id="claim-1",
                text="Prefers deterministic snippets.",
                evidence=[
                    WikiEvidence(
                        kind="note",
                        source_id="source-beta",
                        path="notes/snippets.md",
                        lines=[12, 18],
                        note="Evidence note",
                        text="Evidence text",
                    )
                ],
            )
        ],
    )

    search_text = build_page_search_text(page)

    for expected in [
        "Langley",
        "entities/langley.md",
        "entity.langley",
        "person",
        "source-alpha",
        "LGL",
        "How should Langley be routed?",
        "Conflicting routing note",
        "Python tests",
        "pytest",
        "manual",
        "memory",
        "wiki search",
        "Langley Human",
        "Developer",
        "claim-1",
        "Prefers deterministic snippets.",
        "note",
        "source-beta",
        "notes/snippets.md",
        "12",
        "18",
        "Evidence note",
        "Evidence text",
    ]:
        assert expected in search_text


def test_page_search_text_includes_body_without_generated_blocks() -> None:
    page = WikiPageSummary(
        path="topics/search.md",
        kind="topic",
        id="topic:search",
        title="Search",
        body=(
            "Human-authored body text should be searchable.\n\n"
            f"{HERMES_GENERATED_START}\n"
            "Generated related text should be omitted.\n"
            f"{HERMES_GENERATED_END}\n\n"
            "Another human-authored body line.\n"
        ),
    )

    search_text = build_page_search_text(page)

    assert "Human-authored body text should be searchable." in search_text
    assert "Another human-authored body line." in search_text
    assert "Generated related text should be omitted." not in search_text


def test_page_search_text_sorts_set_values_by_string_representation() -> None:
    page = WikiPageSummary(
        path="topics/routing.md",
        kind="topic",
        id="topic:routing",
        title="Routing",
        routing={"tokens": {_SetToken("beta-token", 0), _SetToken("alpha-token", 1)}},
    )

    search_text = build_page_search_text(page)

    assert search_text.index("alpha-token") < search_text.index("beta-token")


def _page(
    path: str,
    title: str,
    *,
    body: str = "",
    page_id: str | None = None,
    source_ids: list[str] | None = None,
    claims: list[WikiClaim] | None = None,
    aliases: list[str] | None = None,
) -> WikiPageSummary:
    return WikiPageSummary(
        path=path,
        kind="page",
        id=page_id or f"page:{path}",
        title=title,
        body=body,
        source_ids=source_ids or [],
        claims=claims or [],
        aliases=aliases or [],
    )


def test_exact_title_match_outranks_body_only_match() -> None:
    title_page = _page("topics/needle-title.md", "Needle Phrase", body="unrelated body")
    body_page = _page("topics/needle-body.md", "Other Title", body="Needle Phrase appears only in body.")

    results = keyword_search([body_page, title_page], "Needle Phrase")

    assert [result.path for result in results] == ["topics/needle-title.md", "topics/needle-body.md"]
    assert results[0].score > results[1].score


def test_id_and_path_match_boosts_score() -> None:
    plain = _page("topics/plain.md", "Plain", body="routing token")
    boosted = _page("topics/routing-token.md", "Plain", page_id="page:routing-token", body="routing token")

    assert score_page(boosted, "routing-token") > score_page(plain, "routing-token")


def test_claim_text_match_returns_matched_claim_metadata() -> None:
    page = _page(
        "topics/preferences.md",
        "Preferences",
        claims=[WikiClaim(id="claim-prefers-pytest", text="Prefers pytest for deterministic validation.")],
    )

    result = keyword_search([page], "prefers pytest")[0]

    assert result.matched_claim_id == "claim-prefers-pytest"
    assert result.snippet == "Prefers pytest for deterministic validation."
    assert result.metadata["matchedClaim"]["id"] == "claim-prefers-pytest"


def test_confidence_boosts_claim_score() -> None:
    low = _page("topics/low.md", "Low", claims=[WikiClaim(id="low", text="Uses pytest", confidence=0.1)])
    high = _page("topics/high.md", "High", claims=[WikiClaim(id="high", text="Uses pytest", confidence=0.9)])

    assert score_page(high, "uses pytest") > score_page(low, "uses pytest")


def test_stale_and_contested_claims_score_lower() -> None:
    fresh = _page(
        "topics/fresh.md",
        "Fresh",
        claims=[WikiClaim(id="fresh", text="Uses pytest", status="active", raw={"freshnessLevel": "fresh"})],
    )
    stale_contested = _page(
        "topics/stale.md",
        "Stale",
        claims=[WikiClaim(id="stale", text="Uses pytest", status="contested", raw={"freshnessLevel": "stale"})],
    )

    assert score_page(fresh, "uses pytest") > score_page(stale_contested, "uses pytest")


def test_body_occurrence_boost_is_capped() -> None:
    capped = _page("topics/many.md", "Many", body="needle " * 100)
    below_cap = _page("topics/few.md", "Few", body="needle " * 5)

    assert score_page(capped, "needle") - score_page(below_cap, "needle") == 5


def test_nonmatching_pages_score_zero_and_are_filtered() -> None:
    page = _page("topics/other.md", "Other", body="No relevant content here.")

    assert score_page(page, "absent-token") == 0
    assert keyword_search([page], "absent-token") == []


def test_find_person_mode_boosts_person_like_pages_and_identifier_matches() -> None:
    person = WikiPageSummary(
        path="entities/langley.md",
        kind="entity",
        id="entity.langley",
        page_type="entity",
        entity_type="person",
        title="Langley",
        body="Knows atlas routing.",
        aliases=["LGL"],
        person="Langley Human",
        person_card=PersonCard(name="Langley Human"),
    )
    plain = _page("topics/langley.md", "Langley topic", body="Knows atlas routing.")

    assert score_page(person, "langley", mode="find-person") > score_page(person, "langley", mode="auto")
    assert score_page(plain, "langley", mode="find-person") < score_page(plain, "langley", mode="auto")
    assert keyword_search([plain, person], "langley", mode="find-person")[0].path == "entities/langley.md"


def test_route_question_mode_boosts_routing_and_best_used_for_matches() -> None:
    routed = WikiPageSummary(
        path="entities/routing-owner.md",
        kind="entity",
        id="entity.routing-owner",
        page_type="entity",
        entity_type="person",
        title="Routing Owner",
        body="General ownership notes mention invoice triage.",
        best_used_for=["invoice escalation"],
        routing={"billing": ["invoice triage", "refund decisions"]},
        routes=["billing"],
        person_card=PersonCard(best_used_for=["invoice escalation"], routing={"billing": ["invoice triage"]}),
    )
    body_only = _page("topics/body-only.md", "Body only", body="invoice triage")

    assert score_page(routed, "invoice triage", mode="route-question") > score_page(routed, "invoice triage", mode="auto")
    assert keyword_search([body_only, routed], "invoice triage", mode="route-question")[0].path == "entities/routing-owner.md"


def test_source_evidence_mode_boosts_source_pages_and_evidence_matches() -> None:
    source = WikiPageSummary(
        path="sources/interview-2026.md",
        kind="source",
        id="source:interview-2026",
        title="Interview 2026",
        body="Q2 budget evidence notes.",
        source_ids=["interview-2026"],
    )
    evidence_page = _page(
        "topics/budget.md",
        "Budget",
        claims=[
            WikiClaim(
                id="claim-budget",
                text="Budget owner is Morgan.",
                evidence=[WikiEvidence(kind="source", source_id="interview-2026", path="sources/interview-2026.md", note="Q2 budget evidence")],
            )
        ],
    )

    assert score_page(source, "interview-2026", mode="source-evidence") > score_page(source, "interview-2026", mode="auto")
    assert score_page(evidence_page, "q2 budget evidence", mode="source-evidence") > score_page(
        evidence_page, "q2 budget evidence", mode="auto"
    )


def test_source_evidence_mode_boosts_evidence_text_matches() -> None:
    page = _page(
        "topics/evidence-text.md",
        "Evidence text",
        claims=[
            WikiClaim(
                id="claim-evidence-text",
                text="Claim text does not contain the queried phrase.",
                evidence=[WikiEvidence(text="needle evidence phrase")],
            )
        ],
    )

    assert score_page(page, "needle evidence phrase", mode="source-evidence") > score_page(
        page, "needle evidence phrase", mode="auto"
    )


def test_raw_claim_mode_prioritizes_pages_with_matching_claims() -> None:
    claim_page = _page(
        "topics/claim.md",
        "Claim page",
        claims=[WikiClaim(id="claim-needle", text="Needle claim belongs here.")],
    )
    body_page = _page("topics/body.md", "Needle claim belongs here", body="Needle claim belongs here.")

    assert score_page(claim_page, "needle claim", mode="raw-claim") > score_page(claim_page, "needle claim", mode="auto")
    assert keyword_search([body_page, claim_page], "needle claim", mode="raw-claim")[0].path == "topics/claim.md"


def test_invalid_keyword_search_mode_raises_value_error() -> None:
    page = _page("topics/needle.md", "Needle", body="needle")

    with pytest.raises(ValueError, match="Unsupported keyword search mode"):
        score_page(page, "needle", mode="not-a-mode")
    with pytest.raises(ValueError, match="Unsupported keyword search mode"):
        keyword_search([page], "needle", mode="not-a-mode")


def test_invalid_keyword_search_mode_raises_value_error_for_empty_pages() -> None:
    with pytest.raises(ValueError, match="Unsupported keyword search mode"):
        keyword_search([], "needle", mode="not-a-mode")
