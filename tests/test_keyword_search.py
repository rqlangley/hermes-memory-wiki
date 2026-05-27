from __future__ import annotations

from hermes_memory_wiki.markdown import HERMES_GENERATED_END, HERMES_GENERATED_START
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary
from hermes_memory_wiki.search_keyword import build_page_search_text, build_query_tokens, build_snippet


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
        path="people/langley.md",
        kind="person",
        id="person:langley",
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
        "people/langley.md",
        "person:langley",
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
