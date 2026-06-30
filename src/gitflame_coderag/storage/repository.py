"""Persistence interfaces owned by the storage workstream."""

from __future__ import annotations

import json
import re
from hashlib import sha1
from typing import Any

from sqlalchemy import Engine, text

from gitflame_coderag.schemas import (
    ChunkEmbedding,
    ChunkKeywords,
    CodeChunk,
    FileMetadata,
    Repository,
    RepositoryFile,
    RetrievalResult,
    StructuralMetadata,
)


class CodeRAGRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save_repository(self, repository: Repository) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO repositories (id, name, source, revision, root_path, created_at)
                    VALUES (:id, :name, :source, :revision, :root_path, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        source = EXCLUDED.source,
                        revision = EXCLUDED.revision,
                        root_path = EXCLUDED.root_path,
                        created_at = EXCLUDED.created_at
                    """
                ),
                {
                    "id": repository.id,
                    "name": repository.name,
                    "source": repository.source,
                    "revision": repository.revision,
                    "root_path": repository.root_path,
                    "created_at": repository.created_at,
                },
            )

    def save_file_metadata(self, metadata: FileMetadata, *, raw_content: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO repository_files (
                        id,
                        repository_id,
                        revision,
                        path,
                        language,
                        extension,
                        size_bytes,
                        line_count,
                        content_hash,
                        raw_content,
                        is_test,
                        is_config,
                        is_docs
                    )
                    VALUES (
                        :id,
                        :repository_id,
                        :revision,
                        :path,
                        :language,
                        :extension,
                        :size_bytes,
                        :line_count,
                        :content_hash,
                        :raw_content,
                        :is_test,
                        :is_config,
                        :is_docs
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        repository_id = EXCLUDED.repository_id,
                        revision = EXCLUDED.revision,
                        path = EXCLUDED.path,
                        language = EXCLUDED.language,
                        extension = EXCLUDED.extension,
                        size_bytes = EXCLUDED.size_bytes,
                        line_count = EXCLUDED.line_count,
                        content_hash = EXCLUDED.content_hash,
                        raw_content = EXCLUDED.raw_content,
                        is_test = EXCLUDED.is_test,
                        is_config = EXCLUDED.is_config,
                        is_docs = EXCLUDED.is_docs
                    """
                ),
                {
                    "id": metadata.id,
                    "repository_id": metadata.repository_id,
                    "revision": metadata.revision,
                    "path": metadata.path,
                    "language": metadata.language,
                    "extension": metadata.extension,
                    "size_bytes": metadata.size_bytes,
                    "line_count": metadata.line_count,
                    "content_hash": metadata.content_hash,
                    "raw_content": raw_content,
                    "is_test": metadata.is_test,
                    "is_config": metadata.is_config,
                    "is_docs": metadata.is_docs,
                },
            )

    def save_repository_file(self, file: RepositoryFile) -> None:
        self.save_file_metadata(file.metadata, raw_content=file.raw_content)

    def save_chunk(self, chunk: CodeChunk) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO code_chunks (
                        id,
                        repository_id,
                        file_id,
                        path,
                        language,
                        chunk_type,
                        node_type,
                        symbol_name,
                        parent_symbol,
                        start_line,
                        end_line,
                        content,
                        content_hash,
                        token_count
                    )
                    VALUES (
                        :id,
                        :repository_id,
                        :file_id,
                        :path,
                        :language,
                        :chunk_type,
                        :node_type,
                        :symbol_name,
                        :parent_symbol,
                        :start_line,
                        :end_line,
                        :content,
                        :content_hash,
                        :token_count
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        repository_id = EXCLUDED.repository_id,
                        file_id = EXCLUDED.file_id,
                        path = EXCLUDED.path,
                        language = EXCLUDED.language,
                        chunk_type = EXCLUDED.chunk_type,
                        node_type = EXCLUDED.node_type,
                        symbol_name = EXCLUDED.symbol_name,
                        parent_symbol = EXCLUDED.parent_symbol,
                        start_line = EXCLUDED.start_line,
                        end_line = EXCLUDED.end_line,
                        content = EXCLUDED.content,
                        content_hash = EXCLUDED.content_hash,
                        token_count = EXCLUDED.token_count
                    """
                ),
                {
                    "id": chunk.id,
                    "repository_id": chunk.repository_id,
                    "file_id": chunk.file_id,
                    "path": chunk.path,
                    "language": chunk.language,
                    "chunk_type": chunk.chunk_type,
                    "node_type": chunk.node_type,
                    "symbol_name": chunk.symbol_name,
                    "parent_symbol": chunk.parent_symbol,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "token_count": chunk.token_count,
                },
            )

    def save_structural_metadata(self, metadata: StructuralMetadata) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chunk_structural_metadata (
                        chunk_id,
                        imports,
                        calls,
                        defined_symbols,
                        referenced_symbols,
                        flags
                    )
                    VALUES (
                        :chunk_id,
                        CAST(:imports AS jsonb),
                        CAST(:calls AS jsonb),
                        CAST(:defined_symbols AS jsonb),
                        CAST(:referenced_symbols AS jsonb),
                        CAST(:flags AS jsonb)
                    )
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        imports = EXCLUDED.imports,
                        calls = EXCLUDED.calls,
                        defined_symbols = EXCLUDED.defined_symbols,
                        referenced_symbols = EXCLUDED.referenced_symbols,
                        flags = EXCLUDED.flags
                    """
                ),
                {
                    "chunk_id": metadata.chunk_id,
                    "imports": json.dumps(metadata.imports),
                    "calls": json.dumps(metadata.calls),
                    "defined_symbols": json.dumps(metadata.defined_symbols),
                    "referenced_symbols": json.dumps(metadata.referenced_symbols),
                    "flags": json.dumps(metadata.flags),
                },
            )

    def save_bm25_text(self, chunk_id: str, text_value: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chunk_search_texts (chunk_id, bm25_text, embedding_text)
                    VALUES (:chunk_id, :bm25_text, '')
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        bm25_text = EXCLUDED.bm25_text
                    """
                ),
                {"chunk_id": chunk_id, "bm25_text": text_value},
            )

    def save_embedding_text(self, chunk_id: str, text_value: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chunk_search_texts (chunk_id, bm25_text, embedding_text)
                    VALUES (:chunk_id, '', :embedding_text)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        embedding_text = EXCLUDED.embedding_text
                    """
                ),
                {"chunk_id": chunk_id, "embedding_text": text_value},
            )

    def save_embedding_vector(self, embedding: ChunkEmbedding) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chunk_embeddings (
                        chunk_id,
                        embedding_model,
                        embedding,
                        created_at
                    )
                    VALUES (
                        :chunk_id,
                        :embedding_model,
                        :embedding,
                        :created_at
                    )
                    ON CONFLICT (chunk_id, embedding_model) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        created_at = EXCLUDED.created_at
                    """
                ),
                {
                    "chunk_id": embedding.chunk_id,
                    "embedding_model": embedding.embedding_model,
                    "embedding": embedding.vector,
                    "created_at": embedding.created_at,
                },
            )

    def save_chunk_embedding(self, embedding: ChunkEmbedding) -> None:
        self.save_embedding_vector(embedding)

    def load_chunk_embeddings(
        self,
        *,
        repository_id: str | None = None,
        revision: str | None = None,
        embedding_model: str | None = None,
    ) -> list[ChunkEmbedding]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        e.chunk_id,
                        e.embedding_model,
                        e.embedding,
                        e.created_at
                    FROM chunk_embeddings AS e
                    INNER JOIN code_chunks AS c ON c.id = e.chunk_id
                    INNER JOIN repository_files AS f ON f.id = c.file_id
                    WHERE (:repository_id IS NULL OR c.repository_id = :repository_id)
                      AND (:revision IS NULL OR f.revision = :revision)
                      AND (:embedding_model IS NULL OR e.embedding_model = :embedding_model)
                    ORDER BY e.chunk_id, e.embedding_model
                    """
                ),
                {
                    "repository_id": repository_id,
                    "revision": revision,
                    "embedding_model": embedding_model,
                },
            ).mappings()

            return [_row_to_chunk_embedding(row) for row in rows]

    def create_vector_index(
        self,
        *,
        embedding_model: str,
        dimensions: int,
        method: str = "hnsw",
        distance: str = "cosine",
        lists: int = 100,
        m: int = 16,
        ef_construction: int = 64,
    ) -> str:
        if dimensions <= 0:
            raise ValueError("vector index dimensions must be positive")
        if method not in {"hnsw", "ivfflat"}:
            raise ValueError("vector index method must be 'hnsw' or 'ivfflat'")
        opclass = {
            "cosine": "vector_cosine_ops",
            "l2": "vector_l2_ops",
            "ip": "vector_ip_ops",
        }.get(distance)
        if opclass is None:
            raise ValueError("vector index distance must be 'cosine', 'l2', or 'ip'")
        if lists <= 0 or m <= 0 or ef_construction <= 0:
            raise ValueError("vector index tuning parameters must be positive")

        index_name = _vector_index_name(embedding_model, dimensions, method, distance)
        with_clause = (
            f"WITH (lists = {lists})"
            if method == "ivfflat"
            else f"WITH (m = {m}, ef_construction = {ef_construction})"
        )
        model_literal = _quote_sql_literal(embedding_model)
        query = f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON chunk_embeddings
            USING {method} ((embedding::vector({dimensions})) {opclass})
            {with_clause}
            WHERE embedding_model = {model_literal}
        """
        with self.engine.begin() as connection:
            connection.execute(text(query))
        return index_name

    def search_similar_chunks(
        self,
        query_vector: list[float],
        *,
        embedding_model: str,
        top_k: int,
        repository_id: str | None = None,
        revision: str | None = None,
    ) -> list[RetrievalResult]:
        if top_k <= 0 or not query_vector:
            return []

        vector = [float(value) for value in query_vector]
        dimensions = len(vector)
        query = f"""
            SELECT
                e.chunk_id,
                1.0 - (
                    (e.embedding::vector({dimensions}))
                    <=> CAST(:query_vector AS vector({dimensions}))
                ) AS score
            FROM chunk_embeddings AS e
            INNER JOIN code_chunks AS c ON c.id = e.chunk_id
            INNER JOIN repository_files AS f ON f.id = c.file_id
            WHERE e.embedding_model = :embedding_model
              AND (:repository_id IS NULL OR c.repository_id = :repository_id)
              AND (:revision IS NULL OR f.revision = :revision)
            ORDER BY
                (e.embedding::vector({dimensions}))
                    <=> CAST(:query_vector AS vector({dimensions})),
                e.chunk_id
            LIMIT :top_k
        """
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(query),
                {
                    "query_vector": vector,
                    "embedding_model": embedding_model,
                    "repository_id": repository_id,
                    "revision": revision,
                    "top_k": top_k,
                },
            ).mappings()

            return [
                RetrievalResult(
                    chunk_id=row["chunk_id"],
                    rank=rank,
                    score=float(row["score"]),
                    dense_score=float(row["score"]),
                    source="dense",
                )
                for rank, row in enumerate(rows, start=1)
            ]

    def save_keywords(self, keywords: ChunkKeywords) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chunk_keywords (
                        chunk_id,
                        identifiers,
                        identifier_tokens,
                        string_literals,
                        comments_terms,
                        path_tokens
                    )
                    VALUES (
                        :chunk_id,
                        CAST(:identifiers AS jsonb),
                        CAST(:identifier_tokens AS jsonb),
                        CAST(:string_literals AS jsonb),
                        CAST(:comments_terms AS jsonb),
                        CAST(:path_tokens AS jsonb)
                    )
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        identifiers = EXCLUDED.identifiers,
                        identifier_tokens = EXCLUDED.identifier_tokens,
                        string_literals = EXCLUDED.string_literals,
                        comments_terms = EXCLUDED.comments_terms,
                        path_tokens = EXCLUDED.path_tokens
                    """
                ),
                {
                    "chunk_id": keywords.chunk_id,
                    "identifiers": json.dumps(keywords.identifiers),
                    "identifier_tokens": json.dumps(keywords.identifier_tokens),
                    "string_literals": json.dumps(keywords.string_literals),
                    "comments_terms": json.dumps(keywords.comments_terms),
                    "path_tokens": json.dumps(keywords.path_tokens),
                },
            )

    def load_chunks_for_repository(self, repository_id: str, revision: str) -> list[CodeChunk]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        c.id,
                        c.repository_id,
                        c.file_id,
                        c.path,
                        c.language,
                        c.chunk_type,
                        c.node_type,
                        c.symbol_name,
                        c.parent_symbol,
                        c.start_line,
                        c.end_line,
                        c.content,
                        c.content_hash,
                        c.token_count
                    FROM code_chunks AS c
                    INNER JOIN repository_files AS f ON c.file_id = f.id
                    WHERE c.repository_id = :repository_id
                      AND f.revision = :revision
                    ORDER BY c.path, c.start_line
                    """
                ),
                {"repository_id": repository_id, "revision": revision},
            ).mappings()

            return [_row_to_code_chunk(row) for row in rows]


def _row_to_code_chunk(row: Any) -> CodeChunk:
    return CodeChunk(
        id=row["id"],
        repository_id=row["repository_id"],
        file_id=row["file_id"],
        path=row["path"],
        language=row["language"],
        chunk_type=row["chunk_type"],
        node_type=row["node_type"],
        symbol_name=row["symbol_name"],
        parent_symbol=row["parent_symbol"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        content=row["content"],
        content_hash=row["content_hash"],
        token_count=row["token_count"],
    )


def _row_to_chunk_embedding(row: Any) -> ChunkEmbedding:
    return ChunkEmbedding(
        chunk_id=row["chunk_id"],
        embedding_model=row["embedding_model"],
        vector=_coerce_vector(row["embedding"]),
        created_at=row["created_at"],
    )


def _coerce_vector(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, str):
        stripped = value.strip("[]")
        if not stripped:
            return []
        return [float(part.strip()) for part in stripped.split(",")]
    return [float(part) for part in value]


def _vector_index_name(
    embedding_model: str,
    dimensions: int,
    method: str,
    distance: str,
) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", embedding_model).strip("_").lower()
    slug = slug[:24] or "model"
    digest = sha1(embedding_model.encode("utf-8")).hexdigest()[:10]
    return f"idx_chunk_embeddings_{slug}_{dimensions}_{method}_{distance}_{digest}"[:63]


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
