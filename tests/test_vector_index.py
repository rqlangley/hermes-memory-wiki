from __future__ import annotations

from hermes_memory_wiki.markdown import HERMES_GENERATED_END, HERMES_GENERATED_START
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary
from hermes_memory_wiki.vector_index import build_search_documents


def test_page_document_includes_title_path_kind_claims_questions_and_body() -> None:
    page = WikiPageSummary(
        path="topics/search.md",
        kind="concept",
        id="concept:search",
        title="Search Memory",
        aliases=["Memory Search"],
        source_ids=["source-1"],
        claims=[WikiClaim(id="claim-1", text="Search uses deterministic text.")],
        questions=["How should search documents be built?"],
        contradictions=["Older notes mention non-deterministic output."],
        body="Human-authored body line.",
    )

    docs = build_search_documents([page])
    page_doc = next(doc for doc in docs if doc.doc_type == "page")

    assert page_doc.id == "page:topics/search.md"
    assert page_doc.page_path == "topics/search.md"
    assert page_doc.kind == "concept"
    assert page_doc.title == "Search Memory"
    assert "Title: Search Memory" in page_doc.text
    assert "Path: topics/search.md" in page_doc.text
    assert "Kind: concept" in page_doc.text
    assert "Aliases: Memory Search" in page_doc.text
    assert "Source IDs: source-1" in page_doc.text
    assert "Claims:\n- claim-1: Search uses deterministic text." in page_doc.text
    assert "Questions:\n- How should search documents be built?" in page_doc.text
    assert "Contradictions:\n- Older notes mention non-deterministic output." in page_doc.text
    assert "Body:\nHuman-authored body line." in page_doc.text
    assert page_doc.metadata == {
        "page_id": "concept:search",
        "source_ids": ["source-1"],
        "aliases": ["Memory Search"],
        "claim_count": 1,
        "question_count": 1,
        "contradiction_count": 1,
    }


def test_claim_document_includes_claim_text_page_title_source_ids_and_evidence() -> None:
    page = WikiPageSummary(
        path="topics/evidence.md",
        kind="concept",
        id="concept:evidence",
        title="Evidence Page",
        source_ids=["page-source"],
        claims=[
            WikiClaim(
                id="claim-evidence",
                text="Evidence is copied into claim documents.",
                status="active",
                confidence=0.9,
                evidence=[
                    WikiEvidence(
                        kind="note",
                        source_id="evidence-source",
                        path="sources/evidence.md",
                        lines=[3, 5],
                        note="important note",
                        text="quoted evidence text",
                    )
                ],
            )
        ],
    )

    docs = build_search_documents([page])
    claim_doc = next(doc for doc in docs if doc.doc_type == "claim")

    assert claim_doc.id == "claim:topics/evidence.md:claim-evidence"
    assert claim_doc.page_path == "topics/evidence.md"
    assert claim_doc.kind == "concept"
    assert claim_doc.title == "Evidence Page"
    assert "Page: Evidence Page" in claim_doc.text
    assert "Claim ID: claim-evidence" in claim_doc.text
    assert "Claim: Evidence is copied into claim documents." in claim_doc.text
    assert "Status: active" in claim_doc.text
    assert "Confidence: 0.9" in claim_doc.text
    assert "Evidence:" in claim_doc.text
    assert "source_id=evidence-source" in claim_doc.text
    assert "kind=note" in claim_doc.text
    assert "path=sources/evidence.md" in claim_doc.text
    assert "lines=3,5" in claim_doc.text
    assert "note=important note" in claim_doc.text
    assert "text=quoted evidence text" in claim_doc.text
    assert claim_doc.metadata == {
        "page_id": "concept:evidence",
        "claim_id": "claim-evidence",
        "claim_ordinal": 0,
        "status": "active",
        "confidence": 0.9,
        "page_source_ids": ["page-source"],
        "evidence": [
            {
                "kind": "note",
                "source_id": "evidence-source",
                "path": "sources/evidence.md",
                "lines": [3, 5],
                "confidence": None,
                "note": "important note",
                "text": "quoted evidence text",
            }
        ],
    }


def test_document_ids_are_deterministic() -> None:
    page = WikiPageSummary(
        path="topics/deterministic.md",
        kind="concept",
        id="concept:deterministic",
        title="Deterministic",
        claims=[WikiClaim(text="A claim without an explicit ID gets a stable ID.")],
    )

    first_ids = [doc.id for doc in build_search_documents([page])]
    second_ids = [doc.id for doc in build_search_documents([page])]

    assert first_ids == second_ids
    assert first_ids == [
        "page:topics/deterministic.md",
        "claim:topics/deterministic.md:0:bdd5b5b6a374",
    ]


def test_text_hash_changes_when_text_changes() -> None:
    original = WikiPageSummary(
        path="topics/hash.md",
        kind="concept",
        id="concept:hash",
        title="Hash",
        body="Original body.",
    )
    changed = WikiPageSummary(
        path="topics/hash.md",
        kind="concept",
        id="concept:hash",
        title="Hash",
        body="Changed body.",
    )

    original_hash = build_search_documents([original])[0].text_hash
    changed_hash = build_search_documents([changed])[0].text_hash

    assert original_hash != changed_hash


def test_generated_related_blocks_and_frontmatter_are_excluded_from_body_text() -> None:
    page = WikiPageSummary(
        path="topics/body.md",
        kind="concept",
        id="concept:body",
        title="Body",
        body=(
            "---\ntitle: Hidden Frontmatter\n---\n"
            "Human-authored body line.\n\n"
            f"{HERMES_GENERATED_START}\n"
            "Generated related text should not be embedded.\n"
            f"{HERMES_GENERATED_END}\n\n"
            "Another human body line.\n"
        ),
    )

    page_doc = build_search_documents([page])[0]

    assert "Human-authored body line." in page_doc.text
    assert "Another human body line." in page_doc.text
    assert "Hidden Frontmatter" not in page_doc.text
    assert "Generated related text should not be embedded." not in page_doc.text
    assert HERMES_GENERATED_START not in page_doc.text
    assert HERMES_GENERATED_END not in page_doc.text
