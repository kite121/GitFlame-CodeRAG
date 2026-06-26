"""Persistence interfaces owned by the storage workstream."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Engine, text

from gitflame_coderag.schemas import (
    ChunkEmbedding,
    ChunkKeywords,
    CodeChunk,
    FileMetadata,
    Repository,
    RepositoryFile,
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
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        embedding_model = EXCLUDED.embedding_model,
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
