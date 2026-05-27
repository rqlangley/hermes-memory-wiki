from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Sequence

from hermes_memory_wiki.embeddings import EmbeddingProvider
from hermes_memory_wiki.markdown import (
    HERMES_GENERATED_END,
    HERMES_GENERATED_START,
    OPENCLAW_GENERATED_END,
    OPENCLAW_GENERATED_START,
    parse_wiki_markdown,
)
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary

_GENERATED_BLOCK_RE = re.compile(
    r"(?:"
    + re.escape(HERMES_GENERATED_START)
    + r"\n?.*?"
    + re.escape(HERMES_GENERATED_END)
    + r"\n?)|(?:"
    + re.escape(OPENCLAW_GENERATED_START)
    + r"\n?.*?"
    + re.escape(OPENCLAW_GENERATED_END)
    + r"\n?)",
    flags=re.DOTALL,
)


@dataclass
class SearchDocument:
    id: str
    page_path: str
    kind: str
    title: str
    doc_type: Literal["page", "claim"]
    text: str
    text_hash: str
    metadata: dict[str, Any]


@dataclass
class StoredEmbedding:
    document: SearchDocument
    embedding: list[float]
    provider: str
    model: str
    dimensions: int
    embedded_at: str


class VectorIndex:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)

    def upsert_documents(self, docs: Sequence[SearchDocument]) -> None:
        doc_ids = [doc.id for doc in docs]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO documents (
                  id, page_path, kind, title, doc_type, text, text_hash, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
                ON CONFLICT(id) DO UPDATE SET
                  page_path = excluded.page_path,
                  kind = excluded.kind,
                  title = excluded.title,
                  doc_type = excluded.doc_type,
                  text = excluded.text,
                  text_hash = excluded.text_hash,
                  updated_at = excluded.updated_at,
                  metadata_json = excluded.metadata_json
                """,
                [self._document_row(doc) for doc in docs],
            )
            if doc_ids:
                placeholders = ", ".join("?" for _ in doc_ids)
                connection.execute(
                    f"DELETE FROM documents WHERE id NOT IN ({placeholders})", doc_ids
                )
            else:
                connection.execute("DELETE FROM documents")

    def stale_documents_for_embedding(
        self, provider: EmbeddingProvider
    ) -> list[SearchDocument]:
        dimension_clause = ""
        parameters: list[Any] = [provider.provider, provider.model]
        if provider.dimensions is not None:
            dimension_clause = " OR e.dimensions != ?"
            parameters.append(provider.dimensions)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                  d.id, d.page_path, d.kind, d.title, d.doc_type, d.text, d.text_hash, d.metadata_json
                FROM documents d
                LEFT JOIN embeddings e
                  ON e.document_id = d.id
                 AND e.provider = ?
                 AND e.model = ?
                WHERE e.document_id IS NULL
                   OR e.text_hash != d.text_hash
                   {dimension_clause}
                ORDER BY d.id
                """,
                parameters,
            ).fetchall()
        return [self._document_from_row(row) for row in rows]

    def store_embeddings(
        self,
        provider: EmbeddingProvider,
        docs: Sequence[SearchDocument],
        embeddings: Sequence[Sequence[float]],
        *,
        embedded_at: datetime | str | None = None,
    ) -> None:
        if len(docs) != len(embeddings):
            raise ValueError("docs and embeddings length mismatch")

        embedded_at_text = self._format_embedded_at(embedded_at)
        rows = []
        for doc, embedding in zip(docs, embeddings, strict=True):
            vector = list(embedding)
            dimensions = provider.dimensions if provider.dimensions is not None else len(vector)
            rows.append(
                (
                    doc.id,
                    provider.provider,
                    provider.model,
                    dimensions,
                    json.dumps(vector),
                    embedded_at_text,
                    doc.text_hash,
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO embeddings (
                  document_id, provider, model, dimensions, embedding_json, embedded_at, text_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                  provider = excluded.provider,
                  model = excluded.model,
                  dimensions = excluded.dimensions,
                  embedding_json = excluded.embedding_json,
                  embedded_at = excluded.embedded_at,
                  text_hash = excluded.text_hash
                """,
                rows,
            )

    def load_embeddings(self, provider: EmbeddingProvider) -> list[StoredEmbedding]:
        dimension_clause = ""
        parameters: list[Any] = [provider.provider, provider.model]
        if provider.dimensions is not None:
            dimension_clause = " AND e.dimensions = ?"
            parameters.append(provider.dimensions)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                  d.id, d.page_path, d.kind, d.title, d.doc_type, d.text, d.text_hash, d.metadata_json,
                  e.embedding_json, e.provider, e.model, e.dimensions, e.embedded_at
                FROM embeddings e
                JOIN documents d ON d.id = e.document_id
                WHERE e.provider = ?
                  AND e.model = ?
                  {dimension_clause}
                ORDER BY d.id
                """,
                parameters,
            ).fetchall()

        loaded: list[StoredEmbedding] = []
        for row in rows:
            loaded.append(
                StoredEmbedding(
                    document=self._document_from_row(row[:8]),
                    embedding=json.loads(row[8]),
                    provider=row[9],
                    model=row[10],
                    dimensions=row[11],
                    embedded_at=row[12],
                )
            )
        return loaded

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY,
              page_path TEXT NOT NULL,
              kind TEXT NOT NULL,
              title TEXT NOT NULL,
              doc_type TEXT NOT NULL,
              text TEXT NOT NULL,
              text_hash TEXT NOT NULL,
              updated_at TEXT,
              metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS embeddings (
              document_id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              dimensions INTEGER NOT NULL,
              embedding_json TEXT NOT NULL,
              embedded_at TEXT NOT NULL,
              text_hash TEXT NOT NULL,
              FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_documents_page_path ON documents(page_path);
            CREATE INDEX IF NOT EXISTS idx_embeddings_provider_model ON embeddings(provider, model);
            """
        )

    @staticmethod
    def _document_row(doc: SearchDocument) -> tuple[str, str, str, str, str, str, str, str]:
        return (
            doc.id,
            doc.page_path,
            doc.kind,
            doc.title,
            doc.doc_type,
            doc.text,
            doc.text_hash,
            json.dumps(doc.metadata, sort_keys=True),
        )

    @staticmethod
    def _document_from_row(row: sqlite3.Row | tuple[Any, ...]) -> SearchDocument:
        return SearchDocument(
            id=row[0],
            page_path=row[1],
            kind=row[2],
            title=row[3],
            doc_type=row[4],
            text=row[5],
            text_hash=row[6],
            metadata=json.loads(row[7]),
        )

    @staticmethod
    def _format_embedded_at(value: datetime | str | None) -> str:
        if value is None:
            return datetime.now(UTC).isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        return value


def build_search_documents(pages: Sequence[WikiPageSummary]) -> list[SearchDocument]:
    """Convert wiki page summaries into deterministic page and claim search documents."""
    documents: list[SearchDocument] = []
    for page in pages:
        page_text = _build_page_text(page)
        documents.append(
            SearchDocument(
                id=f"page:{page.path}",
                page_path=page.path,
                kind=page.kind,
                title=page.title,
                doc_type="page",
                text=page_text,
                text_hash=_text_hash(page_text),
                metadata={
                    "page_id": page.id,
                    "source_ids": list(page.source_ids),
                    "aliases": list(page.aliases),
                    "claim_count": len(page.claims),
                    "question_count": len(page.questions),
                    "contradiction_count": len(page.contradictions),
                },
            )
        )

        for ordinal, claim in enumerate(page.claims):
            claim_id = _claim_document_id(page, claim, ordinal)
            claim_text = _build_claim_text(page, claim, ordinal)
            documents.append(
                SearchDocument(
                    id=claim_id,
                    page_path=page.path,
                    kind=page.kind,
                    title=page.title,
                    doc_type="claim",
                    text=claim_text,
                    text_hash=_text_hash(claim_text),
                    metadata={
                        "page_id": page.id,
                        "claim_id": claim.id,
                        "claim_ordinal": ordinal,
                        "status": claim.status,
                        "confidence": claim.confidence,
                        "page_source_ids": list(page.source_ids),
                        "evidence": [_evidence_metadata(evidence) for evidence in claim.evidence],
                    },
                )
            )
    return documents


def _build_page_text(page: WikiPageSummary) -> str:
    lines = [
        f"Title: {page.title}",
        f"Path: {page.path}",
        f"Kind: {page.kind}",
        f"Aliases: {_join_values(page.aliases)}",
        f"Source IDs: {_join_values(page.source_ids)}",
        "Claims:",
    ]
    lines.extend(_claim_summary_lines(page.claims))
    lines.append("Questions:")
    lines.extend(_bullet_lines(page.questions))
    lines.append("Contradictions:")
    lines.extend(_bullet_lines(page.contradictions))
    lines.extend(["Body:", _clean_body(page.body)])
    return "\n".join(lines).strip()


def _build_claim_text(page: WikiPageSummary, claim: WikiClaim, ordinal: int) -> str:
    display_claim_id = claim.id or _fallback_claim_id(claim, ordinal)
    lines = [
        f"Page: {page.title}",
        f"Path: {page.path}",
        f"Claim ID: {display_claim_id}",
        f"Claim: {claim.text}",
        f"Status: {_format_optional(claim.status)}",
        f"Confidence: {_format_optional(claim.confidence)}",
        f"Page Source IDs: {_join_values(page.source_ids)}",
        "Evidence:",
    ]
    lines.extend(_evidence_lines(claim.evidence))
    return "\n".join(lines).strip()


def _claim_summary_lines(claims: Sequence[WikiClaim]) -> list[str]:
    if not claims:
        return []
    lines: list[str] = []
    for ordinal, claim in enumerate(claims):
        if claim.id:
            lines.append(f"- {claim.id}: {claim.text}")
        else:
            lines.append(f"- {_fallback_claim_id(claim, ordinal)}: {claim.text}")
    return lines


def _bullet_lines(values: Sequence[Any]) -> list[str]:
    return [f"- {value}" for value in values]


def _evidence_lines(evidence_items: Sequence[WikiEvidence]) -> list[str]:
    lines: list[str] = []
    for evidence in evidence_items:
        fields = [
            f"source_id={_format_optional(evidence.source_id)}",
            f"kind={_format_optional(evidence.kind)}",
            f"note={_format_optional(evidence.note)}",
            f"path={_format_optional(evidence.path)}",
            f"lines={_join_values(evidence.lines, separator=',')}",
            f"confidence={_format_optional(evidence.confidence)}",
            f"text={_format_optional(evidence.text)}",
        ]
        lines.append(f"- {'; '.join(fields)}")
    return lines


def _evidence_metadata(evidence: WikiEvidence) -> dict[str, Any]:
    return {
        "kind": evidence.kind,
        "source_id": evidence.source_id,
        "path": evidence.path,
        "lines": list(evidence.lines),
        "confidence": evidence.confidence,
        "note": evidence.note,
        "text": evidence.text,
    }


def _claim_document_id(page: WikiPageSummary, claim: WikiClaim, ordinal: int) -> str:
    if claim.id:
        claim_part = claim.id
    else:
        claim_part = f"{ordinal}:{_stable_short_hash(claim.text)}"
    return f"claim:{page.path}:{claim_part}"


def _fallback_claim_id(claim: WikiClaim, ordinal: int) -> str:
    return f"claim-{ordinal}-{_stable_short_hash(claim.text)}"


def _clean_body(body: str) -> str:
    parsed_body = parse_wiki_markdown(body).body
    return _GENERATED_BLOCK_RE.sub("", parsed_body).strip()


def _join_values(values: Sequence[Any], *, separator: str = ", ") -> str:
    return separator.join(str(value) for value in values)


def _format_optional(value: Any) -> str:
    return "" if value is None else str(value)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_short_hash(text: str) -> str:
    return _text_hash(text)[:12]
