from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Literal, Sequence

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from hermes_memory_wiki.markdown import (
    HERMES_GENERATED_END,
    HERMES_GENERATED_START,
    OPENCLAW_GENERATED_END,
    OPENCLAW_GENERATED_START,
    parse_wiki_markdown,
)
from hermes_memory_wiki.schema import WikiClaim, WikiEvidence, WikiPageSummary
from hermes_memory_wiki.search_keyword import WikiSearchResult
from hermes_memory_wiki.vault import METADATA_DIRECTORY, read_queryable_pages

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

_OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_VALID_VECTOR_SEARCH_MODES = {
    "auto",
    "find-person",
    "route-question",
    "source-evidence",
    "raw-claim",
}


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


@dataclass
class ReindexResult:
    embedded_count: int
    skipped_count: int
    deleted_count: int
    provider: str
    model: str
    dimensions: int | None
    diagnostics: list[str]


class VectorSearchResults(list[WikiSearchResult]):
    """List-compatible vector search results with preserved diagnostics."""

    def __init__(
        self,
        results: Sequence[WikiSearchResult] = (),
        *,
        diagnostics: Sequence[str] = (),
    ) -> None:
        super().__init__(results)
        self.diagnostics = list(diagnostics)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return cosine similarity for two numeric vectors."""
    if len(a) != len(b):
        raise ValueError(
            f"dimension mismatch: left vector has {len(a)} dimensions, "
            f"right vector has {len(b)} dimensions"
        )
    dot_product = 0.0
    a_norm_squared = 0.0
    b_norm_squared = 0.0
    for left, right in zip(a, b, strict=True):
        left_float = float(left)
        right_float = float(right)
        dot_product += left_float * right_float
        a_norm_squared += left_float * left_float
        b_norm_squared += right_float * right_float
    if a_norm_squared == 0.0 or b_norm_squared == 0.0:
        return 0.0
    return dot_product / ((a_norm_squared**0.5) * (b_norm_squared**0.5))


def vector_search(
    config: MemoryWikiConfig,
    query: str,
    *,
    provider: EmbeddingProvider | None = None,
    max_results: int = 10,
    mode: str = "auto",
) -> list[WikiSearchResult]:
    """Return cosine-ranked wiki documents from the stored vector index."""
    if mode not in _VALID_VECTOR_SEARCH_MODES:
        raise ValueError(f"Unsupported vector search mode: {mode}")
    if max_results <= 0:
        return VectorSearchResults()

    diagnostics: list[str] = []
    if provider is None:
        provider, provider_diagnostics = _provider_from_config(config)
        diagnostics.extend(provider_diagnostics)
        if provider is None:
            return VectorSearchResults(diagnostics=diagnostics)

    index_path = _default_index_path(config)
    if not index_path.exists():
        diagnostics.append(f"Vector index not found: {index_path}")
        return VectorSearchResults(diagnostics=diagnostics)

    index = VectorIndex(index_path)
    stored_embeddings = _load_embeddings_for_search(index, provider)
    if not stored_embeddings:
        diagnostics.append(
            "No vector embeddings available "
            f"(provider={provider.provider}, model={provider.model})."
        )
        return VectorSearchResults(diagnostics=diagnostics)

    query_embeddings = provider.embed_texts([query])
    if len(query_embeddings) != 1:
        raise ValueError(
            "query embedding count mismatch: "
            f"expected 1, got {len(query_embeddings)}"
        )
    query_embedding = query_embeddings[0]

    scored_results: list[WikiSearchResult] = []
    for stored_embedding in stored_embeddings:
        if len(query_embedding) != len(stored_embedding.embedding):
            raise ValueError(
                "dimension mismatch for query and stored embedding: "
                f"query has {len(query_embedding)} dimensions; "
                f"{stored_embedding.document.id} has "
                f"{len(stored_embedding.embedding)} dimensions"
            )
        scored_results.append(
            _vector_result(
                stored_embedding.document,
                score=cosine_similarity(query_embedding, stored_embedding.embedding),
                mode=mode,
            )
        )

    scored_results.sort(
        key=lambda result: (-result.score, result.path, result.matched_claim_id or "")
    )
    return VectorSearchResults(scored_results[:max_results], diagnostics=diagnostics)


def _load_embeddings_for_search(
    index: VectorIndex, provider: EmbeddingProvider
) -> list[StoredEmbedding]:
    unfiltered_provider = _ProviderIdentity(
        provider=provider.provider,
        model=provider.model,
        dimensions=None,
    )
    return index.load_embeddings(unfiltered_provider)


@dataclass
class _ProviderIdentity:
    provider: str
    model: str
    dimensions: int | None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError


def _vector_result(document: SearchDocument, *, score: float, mode: str) -> WikiSearchResult:
    metadata = dict(document.metadata)
    metadata.update(
        {
            "searchType": "vector",
            "documentId": document.id,
            "documentType": document.doc_type,
        }
    )
    matched_claim_id = None
    if document.doc_type == "claim":
        raw_claim_id = document.metadata.get("claimId")
        matched_claim_id = str(raw_claim_id) if raw_claim_id else None
    return WikiSearchResult(
        corpus="wiki",
        path=document.page_path,
        title=document.title,
        kind=document.kind,
        score=float(score),
        snippet=_vector_snippet(document),
        search_mode=mode,
        matched_claim_id=matched_claim_id,
        metadata=metadata,
    )


def _vector_snippet(document: SearchDocument) -> str:
    lines = [line.strip() for line in document.text.splitlines() if line.strip()]
    if not lines:
        return ""
    if document.doc_type == "claim":
        for line in lines:
            if line.startswith("Claim:"):
                return line.removeprefix("Claim:").strip()
    for index, line in enumerate(lines):
        if line == "Body:" and index + 1 < len(lines):
            return lines[index + 1]
    return lines[0]


class VectorIndex:

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            self._create_schema(connection)

    def upsert_documents(self, docs: Sequence[SearchDocument]) -> int:
        doc_ids = [doc.id for doc in docs]
        with self._connection() as connection:
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
                cursor = connection.execute(
                    f"DELETE FROM documents WHERE id NOT IN ({placeholders})", doc_ids
                )
            else:
                cursor = connection.execute("DELETE FROM documents")
            return cursor.rowcount if cursor.rowcount >= 0 else 0

    def stale_documents_for_embedding(
        self, provider: EmbeddingProvider
    ) -> list[SearchDocument]:
        dimension_clause = ""
        parameters: list[Any] = [provider.provider, provider.model]
        if provider.dimensions is not None:
            dimension_clause = " OR e.dimensions != ?"
            parameters.append(provider.dimensions)

        with self._connection() as connection:
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

    def plan_document_sync(
        self,
        docs: Sequence[SearchDocument],
        provider: EmbeddingProvider,
        *,
        force: bool = False,
    ) -> tuple[int, list[SearchDocument]]:
        """Determine deletions and embeddings needed without mutating the index."""
        doc_ids = [doc.id for doc in docs]
        with self._connection() as connection:
            deleted_count = self._count_deleted_documents(connection, doc_ids)
            if force:
                return deleted_count, list(docs)
            embedding_rows = self._embedding_state_for_documents(
                connection, doc_ids, provider
            )

        documents_to_embed = []
        for doc in docs:
            embedding_row = embedding_rows.get(doc.id)
            if embedding_row is None:
                documents_to_embed.append(doc)
                continue
            text_hash, dimensions = embedding_row
            if text_hash != doc.text_hash:
                documents_to_embed.append(doc)
                continue
            if provider.dimensions is not None and dimensions != provider.dimensions:
                documents_to_embed.append(doc)
        return deleted_count, documents_to_embed

    def sync_documents_and_store_embeddings(
        self,
        provider: EmbeddingProvider,
        docs: Sequence[SearchDocument],
        docs_to_embed: Sequence[SearchDocument],
        embeddings: Sequence[Sequence[float]],
        *,
        embedded_at: datetime | str | None = None,
    ) -> int:
        """Apply document sync/deletions and embedding writes in one transaction."""
        embedding_rows = self._embedding_rows(
            provider, docs_to_embed, embeddings, embedded_at=embedded_at
        )
        doc_ids = [doc.id for doc in docs]
        with self._connection() as connection:
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
            deleted_count = self._delete_documents_not_in(connection, doc_ids)
            self._insert_embedding_rows(connection, embedding_rows)
            return deleted_count

    def store_embeddings(
        self,
        provider: EmbeddingProvider,
        docs: Sequence[SearchDocument],
        embeddings: Sequence[Sequence[float]],
        *,
        embedded_at: datetime | str | None = None,
    ) -> None:
        rows = self._embedding_rows(provider, docs, embeddings, embedded_at=embedded_at)
        with self._connection() as connection:
            self._insert_embedding_rows(connection, rows)

    def load_embeddings(self, provider: EmbeddingProvider) -> list[StoredEmbedding]:
        dimension_clause = ""
        parameters: list[Any] = [provider.provider, provider.model]
        if provider.dimensions is not None:
            dimension_clause = " AND e.dimensions = ?"
            parameters.append(provider.dimensions)

        with self._connection() as connection:
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

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as connection:
            with connection:
                yield connection

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
    def _count_deleted_documents(
        connection: sqlite3.Connection, doc_ids: Sequence[str]
    ) -> int:
        if doc_ids:
            placeholders = ", ".join("?" for _ in doc_ids)
            return connection.execute(
                f"SELECT COUNT(*) FROM documents WHERE id NOT IN ({placeholders})",
                list(doc_ids),
            ).fetchone()[0]
        return connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    @staticmethod
    def _delete_documents_not_in(
        connection: sqlite3.Connection, doc_ids: Sequence[str]
    ) -> int:
        if doc_ids:
            placeholders = ", ".join("?" for _ in doc_ids)
            cursor = connection.execute(
                f"DELETE FROM documents WHERE id NOT IN ({placeholders})", list(doc_ids)
            )
        else:
            cursor = connection.execute("DELETE FROM documents")
        return cursor.rowcount if cursor.rowcount >= 0 else 0

    @staticmethod
    def _embedding_state_for_documents(
        connection: sqlite3.Connection,
        doc_ids: Sequence[str],
        provider: EmbeddingProvider,
    ) -> dict[str, tuple[str, int]]:
        if not doc_ids:
            return {}
        placeholders = ", ".join("?" for _ in doc_ids)
        rows = connection.execute(
            f"""
            SELECT document_id, text_hash, dimensions
            FROM embeddings
            WHERE provider = ?
              AND model = ?
              AND document_id IN ({placeholders})
            """,
            [provider.provider, provider.model, *doc_ids],
        ).fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}

    @classmethod
    def _embedding_rows(
        cls,
        provider: EmbeddingProvider,
        docs: Sequence[SearchDocument],
        embeddings: Sequence[Sequence[float]],
        *,
        embedded_at: datetime | str | None = None,
    ) -> list[tuple[str, str, str, int, str, str, str]]:
        if len(docs) != len(embeddings):
            raise ValueError("docs and embeddings length mismatch")

        embedded_at_text = cls._format_embedded_at(embedded_at)
        rows = []
        for doc, embedding in zip(docs, embeddings, strict=True):
            vector = list(embedding)
            if provider.dimensions is not None and len(vector) != provider.dimensions:
                raise ValueError(
                    "embedding dimension mismatch: "
                    f"expected {provider.dimensions}, got {len(vector)} for document {doc.id}"
                )
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
        return rows

    @staticmethod
    def _insert_embedding_rows(
        connection: sqlite3.Connection,
        rows: Sequence[tuple[str, str, str, int, str, str, str]],
    ) -> None:
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


def reindex_vault(
    config: MemoryWikiConfig,
    provider: EmbeddingProvider | None = None,
    *,
    force: bool = False,
) -> ReindexResult:
    """Incrementally rebuild stored embeddings for queryable wiki pages."""
    diagnostics: list[str] = []
    if provider is None:
        provider, provider_diagnostics = _provider_from_config(config)
        diagnostics.extend(provider_diagnostics)
        if provider is None:
            dimensions = (
                _known_openai_dimensions(config.embeddings.model)
                if config.embeddings.provider == "openai"
                else None
            )
            return ReindexResult(
                embedded_count=0,
                skipped_count=0,
                deleted_count=0,
                provider=config.embeddings.provider,
                model=config.embeddings.model,
                dimensions=dimensions,
                diagnostics=diagnostics,
            )

    unsafe_path_diagnostic = _unsafe_vector_index_path_diagnostic(config)
    if unsafe_path_diagnostic is not None:
        return ReindexResult(
            embedded_count=0,
            skipped_count=0,
            deleted_count=0,
            provider=provider.provider,
            model=provider.model,
            dimensions=provider.dimensions,
            diagnostics=[*diagnostics, unsafe_path_diagnostic],
        )

    index = VectorIndex(_default_index_path(config))
    pages = read_queryable_pages(config.vault_path)
    documents = build_search_documents(pages)
    deleted_count, documents_to_embed = index.plan_document_sync(
        documents, provider, force=force
    )

    if not documents_to_embed:
        try:
            deleted_count = index.sync_documents_and_store_embeddings(
                provider, documents, [], []
            )
        except Exception as exc:
            diagnostics.append(_format_exception(exc))
            return ReindexResult(
                embedded_count=0,
                skipped_count=0,
                deleted_count=0,
                provider=provider.provider,
                model=provider.model,
                dimensions=provider.dimensions,
                diagnostics=diagnostics,
            )
        return ReindexResult(
            embedded_count=0,
            skipped_count=len(documents),
            deleted_count=deleted_count,
            provider=provider.provider,
            model=provider.model,
            dimensions=provider.dimensions,
            diagnostics=diagnostics,
        )

    try:
        embeddings = provider.embed_texts([document.text for document in documents_to_embed])
        deleted_count = index.sync_documents_and_store_embeddings(
            provider, documents, documents_to_embed, embeddings
        )
    except Exception as exc:
        diagnostics.append(_format_exception(exc))
        return ReindexResult(
            embedded_count=0,
            skipped_count=0,
            deleted_count=deleted_count,
            provider=provider.provider,
            model=provider.model,
            dimensions=provider.dimensions,
            diagnostics=diagnostics,
        )

    return ReindexResult(
        embedded_count=len(documents_to_embed),
        skipped_count=len(documents) - len(documents_to_embed),
        deleted_count=deleted_count,
        provider=provider.provider,
        model=provider.model,
        dimensions=provider.dimensions,
        diagnostics=diagnostics,
    )


def _format_exception(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _provider_from_config(
    config: MemoryWikiConfig,
) -> tuple[EmbeddingProvider | None, list[str]]:
    embeddings_config = config.embeddings
    if not embeddings_config.enabled:
        return None, ["Embeddings are disabled in configuration."]
    if embeddings_config.provider != "openai":
        return None, [f"Unsupported embeddings provider: {embeddings_config.provider}"]
    dimensions = _known_openai_dimensions(embeddings_config.model)
    if not os.environ.get(embeddings_config.api_key_env):
        return None, [
            "Missing API key for OpenAI embeddings provider "
            f"(provider=openai, model={embeddings_config.model}). "
            f"Set environment variable {embeddings_config.api_key_env}."
        ]
    try:
        return OpenAIEmbeddingProvider(embeddings_config, dimensions=dimensions), []
    except Exception as exc:
        return None, [_format_exception(exc)]


def _known_openai_dimensions(model: str) -> int | None:
    return _OPENAI_EMBEDDING_DIMENSIONS.get(model)


def _unsafe_vector_index_path_diagnostic(config: MemoryWikiConfig) -> str | None:
    metadata_dir = config.vault_path / METADATA_DIRECTORY
    vector_dir = metadata_dir / "vector"
    index_path = vector_dir / "index.sqlite"
    for path in (metadata_dir, vector_dir, index_path):
        if path.is_symlink():
            return f"Vector index path must not be a symlink: {path}"
    return None


def _default_index_path(config: MemoryWikiConfig) -> Path:
    return config.vault_path / METADATA_DIRECTORY / "vector" / "index.sqlite"


def build_search_documents(pages: Sequence[WikiPageSummary]) -> list[SearchDocument]:
    """Convert wiki page summaries into deterministic page and claim search documents."""
    documents: list[SearchDocument] = []
    for page in pages:
        page_text = _build_page_text(page)
        page_metadata = {
            "id": page.id,
            "kind": page.kind,
            "pageType": page.page_type,
            "entityType": page.entity_type,
            "sourceIds": list(page.source_ids),
            "aliases": list(page.aliases),
            "confidence": page.confidence,
            "status": page.status,
            "updatedAt": page.updated_at,
            "claimCount": len(page.claims),
            "questionCount": len(page.questions),
            "contradictionCount": len(page.contradictions),
        }
        person_card_metadata = _person_card_metadata(page)
        if person_card_metadata is not None:
            page_metadata["person_card"] = person_card_metadata
        documents.append(
            SearchDocument(
                id=f"page:{page.path}",
                page_path=page.path,
                kind=page.kind,
                title=page.title,
                doc_type="page",
                text=page_text,
                text_hash=_text_hash(page_text),
                metadata=page_metadata,
            )
        )

        for ordinal, claim in enumerate(page.claims):
            claim_id = _claim_document_id(page, claim, ordinal)
            claim_text = _build_claim_text(page, claim, ordinal)
            claim_metadata = {
                "id": page.id,
                "kind": page.kind,
                "pageType": page.page_type,
                "entityType": page.entity_type,
                "sourceIds": list(page.source_ids),
                "confidence": page.confidence,
                "updatedAt": page.updated_at,
                "claimId": claim.id,
                "claimOrdinal": ordinal,
                "status": claim.status,
                "claimConfidence": claim.confidence,
                "pageSourceIds": list(page.source_ids),
                "evidence": [_evidence_metadata(evidence) for evidence in claim.evidence],
            }
            person_card_metadata = _person_card_metadata(page)
            if person_card_metadata is not None:
                claim_metadata["person_card"] = person_card_metadata
            documents.append(
                SearchDocument(
                    id=claim_id,
                    page_path=page.path,
                    kind=page.kind,
                    title=page.title,
                    doc_type="claim",
                    text=claim_text,
                    text_hash=_text_hash(claim_text),
                    metadata=claim_metadata,
                )
            )
    return documents


def _build_page_text(page: WikiPageSummary) -> str:
    lines = [
        f"Title: {page.title}",
        f"Path: {page.path}",
        f"Page ID: {page.id}",
        f"Kind: {page.kind}",
        f"Page Type: {_format_optional(page.page_type)}",
        f"Entity Type: {_format_optional(page.entity_type)}",
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
        f"Page ID: {page.id}",
        f"Kind: {page.kind}",
        f"Page Type: {_format_optional(page.page_type)}",
        f"Entity Type: {_format_optional(page.entity_type)}",
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
            f"lines={_format_optional(evidence.lines)}",
            f"confidence={_format_optional(evidence.confidence)}",
            f"text={_format_optional(evidence.text)}",
        ]
        lines.append(f"- {'; '.join(fields)}")
    return lines


def _evidence_metadata(evidence: WikiEvidence) -> dict[str, Any]:
    return {
        "kind": evidence.kind,
        "sourceId": evidence.source_id,
        "path": evidence.path,
        "lines": evidence.lines,
        "confidence": evidence.confidence,
        "note": evidence.note,
        "text": evidence.text,
    }


def _person_card_metadata(page: WikiPageSummary) -> dict[str, Any] | None:
    if page.person_card is None:
        return None
    return {
        "name": page.person_card.name,
        "role": page.person_card.role,
        "bestUsedFor": list(page.person_card.best_used_for),
        "topics": list(page.person_card.topics),
        "routing": dict(page.person_card.routing),
        "routes": list(page.person_card.routes),
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
