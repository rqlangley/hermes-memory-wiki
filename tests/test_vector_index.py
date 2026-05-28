from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass

import pytest

from hermes_memory_wiki.markdown import HERMES_GENERATED_END, HERMES_GENERATED_START
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary
from hermes_memory_wiki.vector_index import SearchDocument, VectorIndex, build_search_documents


@dataclass(frozen=True)
class StubEmbeddingProvider:
    provider: str = "stub"
    model: str = "stub-model"
    dimensions: int | None = 3

    def embed_texts(self, texts):  # pragma: no cover - protocol shape only
        return [[float(index)] * (self.dimensions or 1) for index, _ in enumerate(texts)]


def _doc(
    doc_id: str,
    *,
    page_path: str = "topics/example.md",
    title: str = "Example",
    text: str | None = None,
    text_hash: str | None = None,
    metadata: dict | None = None,
) -> SearchDocument:
    text_value = text or f"Text for {doc_id}"
    return SearchDocument(
        id=doc_id,
        page_path=page_path,
        kind="concept",
        title=title,
        doc_type="page",
        text=text_value,
        text_hash=text_hash or f"hash-{doc_id}",
        metadata=metadata or {"ordinal": doc_id},
    )


def test_vector_index_creates_sqlite_schema(tmp_path) -> None:
    db_path = tmp_path / "nested" / "vector.sqlite3"

    VectorIndex(db_path)

    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        document_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(documents)")
        ]
        embedding_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(embeddings)")
        ]

    assert {"documents", "embeddings"} <= tables
    assert "idx_documents_page_path" in indexes
    assert "idx_embeddings_provider_model" in indexes
    assert document_columns == [
        "id",
        "page_path",
        "kind",
        "title",
        "doc_type",
        "text",
        "text_hash",
        "updated_at",
        "metadata_json",
    ]
    assert embedding_columns == [
        "document_id",
        "provider",
        "model",
        "dimensions",
        "embedding_json",
        "embedded_at",
        "text_hash",
    ]


def test_vector_index_upserts_documents(tmp_path) -> None:
    index = VectorIndex(tmp_path / "vector.sqlite3")
    original = _doc("page:one", text="Original text", metadata={"version": 1})
    changed = _doc("page:one", text="Changed text", text_hash="hash-changed", metadata={"version": 2})

    index.upsert_documents([original])
    index.upsert_documents([changed])

    with sqlite3.connect(tmp_path / "vector.sqlite3") as connection:
        rows = connection.execute(
            "SELECT id, text, text_hash, metadata_json FROM documents"
        ).fetchall()

    assert rows == [
        ("page:one", "Changed text", "hash-changed", json.dumps({"version": 2}, sort_keys=True))
    ]


def test_vector_index_stores_embeddings(tmp_path) -> None:
    provider = StubEmbeddingProvider()
    doc = _doc("page:one")
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([doc])

    index.store_embeddings(provider, [doc], [[0.1, 0.2, 0.3]], embedded_at="2026-05-27T12:00:00+00:00")

    with sqlite3.connect(tmp_path / "vector.sqlite3") as connection:
        rows = connection.execute(
            """
            SELECT document_id, provider, model, dimensions, embedding_json, embedded_at, text_hash
            FROM embeddings
            """
        ).fetchall()

    assert rows == [
        (
            "page:one",
            "stub",
            "stub-model",
            3,
            json.dumps([0.1, 0.2, 0.3]),
            "2026-05-27T12:00:00+00:00",
            doc.text_hash,
        )
    ]


def test_vector_index_rejects_embedding_count_mismatch(tmp_path) -> None:
    provider = StubEmbeddingProvider()
    doc = _doc("page:one")
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([doc])

    try:
        index.store_embeddings(provider, [doc], [])
    except ValueError as error:
        assert "docs and embeddings length mismatch" in str(error)
    else:  # pragma: no cover - failure path
        raise AssertionError("Expected ValueError")


def test_vector_index_rejects_embedding_dimension_mismatch_without_storing(tmp_path) -> None:
    provider = StubEmbeddingProvider(dimensions=3)
    doc = _doc("page:one")
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([doc])

    with pytest.raises(ValueError, match="embedding dimension mismatch"):
        index.store_embeddings(provider, [doc], [[0.1, 0.2]])

    with sqlite3.connect(tmp_path / "vector.sqlite3") as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    assert row_count == 0


def test_vector_index_closes_sqlite_connections_after_operations(tmp_path) -> None:
    fd_path = "/proc/self/fd"
    if not os.path.isdir(fd_path):
        pytest.skip("/proc/self/fd is unavailable")

    db_path = tmp_path / "vector.sqlite3"
    provider = StubEmbeddingProvider()
    doc = _doc("page:one")
    index = VectorIndex(db_path)

    def open_sqlite_fds() -> int:
        count = 0
        for fd_name in os.listdir(fd_path):
            try:
                target = os.readlink(os.path.join(fd_path, fd_name))
            except OSError:
                continue
            if str(db_path) in target:
                count += 1
        return count

    assert open_sqlite_fds() == 0

    for _ in range(25):
        index.upsert_documents([doc])
        index.store_embeddings(provider, [doc], [[0.1, 0.2, 0.3]])
        assert index.stale_documents_for_embedding(provider) == []
        assert len(index.load_embeddings(provider)) == 1

    assert open_sqlite_fds() == 0


def test_vector_index_skips_unchanged_embeddings_by_hash_provider_model(tmp_path) -> None:
    provider = StubEmbeddingProvider(provider="stub", model="model-a", dimensions=3)
    other_model = StubEmbeddingProvider(provider="stub", model="model-b", dimensions=3)
    doc = _doc("page:one")
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([doc])
    index.store_embeddings(provider, [doc], [[0.1, 0.2, 0.3]])

    assert index.stale_documents_for_embedding(provider) == []
    assert index.stale_documents_for_embedding(other_model) == [doc]

    changed = _doc("page:one", text="Changed text", text_hash="hash-changed")
    index.upsert_documents([changed])

    assert index.stale_documents_for_embedding(provider) == [changed]


def test_vector_index_marks_embedding_stale_when_dimensions_differ(tmp_path) -> None:
    doc = _doc("page:one")
    stored_provider = StubEmbeddingProvider(dimensions=3)
    larger_provider = StubEmbeddingProvider(dimensions=4)
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([doc])
    index.store_embeddings(stored_provider, [doc], [[0.1, 0.2, 0.3]])

    assert index.stale_documents_for_embedding(larger_provider) == [doc]


def test_vector_index_deletes_stale_documents_no_longer_present(tmp_path) -> None:
    provider = StubEmbeddingProvider()
    keep = _doc("page:keep")
    remove = _doc("page:remove")
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([keep, remove])
    index.store_embeddings(provider, [keep, remove], [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    index.upsert_documents([keep])

    with sqlite3.connect(tmp_path / "vector.sqlite3") as connection:
        document_ids = [row[0] for row in connection.execute("SELECT id FROM documents")]
        embedding_ids = [row[0] for row in connection.execute("SELECT document_id FROM embeddings")]

    assert document_ids == ["page:keep"]
    assert embedding_ids == ["page:keep"]


def test_vector_index_deletes_stale_claim_and_page_documents_for_removed_page(tmp_path) -> None:
    provider = StubEmbeddingProvider()
    keep = _doc("page:keep", page_path="topics/keep.md")
    remove_page = _doc("page:remove", page_path="topics/remove.md")
    remove_claim = SearchDocument(
        id="claim:topics/remove.md:claim-one",
        page_path="topics/remove.md",
        kind="concept",
        title="Remove",
        doc_type="claim",
        text="Claim text for removed page",
        text_hash="hash-removed-claim",
        metadata={"claim_id": "claim-one"},
    )
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents([keep, remove_page, remove_claim])
    index.store_embeddings(
        provider,
        [keep, remove_page, remove_claim],
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]],
    )

    deleted_count = index.upsert_documents([keep])

    with sqlite3.connect(tmp_path / "vector.sqlite3") as connection:
        document_ids = [row[0] for row in connection.execute("SELECT id FROM documents ORDER BY id")]
        embedding_ids = [row[0] for row in connection.execute("SELECT document_id FROM embeddings ORDER BY document_id")]

    assert deleted_count == 2
    assert document_ids == ["page:keep"]
    assert embedding_ids == ["page:keep"]


def test_vector_index_loads_all_embeddings_for_provider_model(tmp_path) -> None:
    provider = StubEmbeddingProvider(provider="stub", model="model-a", dimensions=3)
    other_provider = StubEmbeddingProvider(provider="other", model="model-a", dimensions=3)
    docs = [
        _doc("page:b", page_path="topics/b.md", metadata={"rank": 2}),
        _doc("page:a", page_path="topics/a.md", metadata={"rank": 1}),
        _doc("page:c", page_path="topics/c.md", metadata={"rank": 3}),
    ]
    index = VectorIndex(tmp_path / "vector.sqlite3")
    index.upsert_documents(docs)
    index.store_embeddings(provider, docs[:2], [[0.2, 0.2, 0.2], [0.1, 0.1, 0.1]])
    index.store_embeddings(other_provider, [docs[2]], [[9.0, 9.0, 9.0]])

    loaded = index.load_embeddings(provider)

    assert [item.document.id for item in loaded] == ["page:a", "page:b"]
    assert [item.embedding for item in loaded] == [[0.1, 0.1, 0.1], [0.2, 0.2, 0.2]]
    assert loaded[0].document.metadata == {"rank": 1}


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
