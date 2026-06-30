import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from gitflame_coderag.schemas import (
    ChunkEmbedding,
    ChunkKeywords,
    CodeChunk,
    FileMetadata,
    Repository,
    StructuralMetadata,
)
from gitflame_coderag.storage import CodeRAGRepository, create_engine_from_url, run_migrations

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://gitflame:gitflame@localhost:5432/gitflame_coderag",
)


def _database_available() -> bool:
    try:
        engine = create_engine_from_url(DATABASE_URL)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _database_available(),
    reason="PostgreSQL database is not available",
)


@pytest.fixture
def repository() -> CodeRAGRepository:
    engine = create_engine_from_url(DATABASE_URL)
    run_migrations(engine)
    repo = CodeRAGRepository(engine)
    yield repo
    engine.dispose()


def _sample_ids() -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    repository_id = f"test_repo_{suffix}"
    file_id = f"test_file_{suffix}"
    chunk_id = f"test_chunk_{suffix}"
    return repository_id, file_id, chunk_id


def test_storage_round_trip(repository: CodeRAGRepository) -> None:
    repository_id, file_id, chunk_id = _sample_ids()
    revision = "main"

    repository.save_repository(
        Repository(
            id=repository_id,
            name="sample-repository",
            source="test",
            revision=revision,
            root_path="/tmp/sample",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    repository.save_file_metadata(
        FileMetadata(
            id=file_id,
            repository_id=repository_id,
            revision=revision,
            path="src/auth/routes.py",
            extension=".py",
            language="python",
            size_bytes=42,
            line_count=10,
            content_hash="abc123",
            is_test=False,
            is_config=False,
            is_docs=False,
        ),
        raw_content="def login():\n    return 401\n",
    )

    chunk = CodeChunk(
        id=chunk_id,
        repository_id=repository_id,
        file_id=file_id,
        path="src/auth/routes.py",
        language="python",
        chunk_type="ast",
        node_type="function_definition",
        symbol_name="login",
        parent_symbol=None,
        start_line=1,
        end_line=2,
        content="def login():\n    return 401\n",
        content_hash="chunk-hash",
        token_count=8,
    )
    repository.save_chunk(chunk)

    repository.save_structural_metadata(
        StructuralMetadata(
            chunk_id=chunk_id,
            imports=["fastapi"],
            calls=["HTTPException"],
            defined_symbols=["login"],
            referenced_symbols=["HTTPException"],
            flags={"is_handler": True, "is_test": False},
        )
    )
    repository.save_bm25_text(chunk_id, "auth login routes python handler")
    repository.save_embedding_text(
        chunk_id,
        "File: src/auth/routes.py\nLanguage: python\nSymbol: login\n\nCode:\ndef login():\n",
    )
    repository.save_embedding_vector(
        ChunkEmbedding(
            chunk_id=chunk_id,
            embedding_model="jinaai/jina-embeddings-v2-base-code",
            vector=[0.1] * 768,
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    repository.save_chunk_embedding(
        ChunkEmbedding(
            chunk_id=chunk_id,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            vector=[0.2] * 384,
            created_at=datetime(2026, 1, 3, tzinfo=UTC),
        )
    )
    repository.save_keywords(
        ChunkKeywords(
            chunk_id=chunk_id,
            identifiers=["login"],
            identifier_tokens=["login"],
            string_literals=[],
            comments_terms=[],
            path_tokens=["src", "auth", "routes"],
        )
    )

    loaded_chunks = repository.load_chunks_for_repository(repository_id, revision)

    assert len(loaded_chunks) == 1
    loaded = loaded_chunks[0]
    assert loaded.id == chunk_id
    assert loaded.symbol_name == "login"
    assert loaded.content == chunk.content

    loaded_embeddings = repository.load_chunk_embeddings(
        repository_id=repository_id,
        revision=revision,
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    assert len(loaded_embeddings) == 1
    assert loaded_embeddings[0].chunk_id == chunk_id
    assert loaded_embeddings[0].vector == pytest.approx([0.2] * 384)

    index_name = repository.create_vector_index(
        embedding_model="jinaai/jina-embeddings-v2-base-code",
        dimensions=768,
    )
    assert index_name.startswith("idx_chunk_embeddings_")

    dense_results = repository.search_similar_chunks(
        [0.1] * 768,
        embedding_model="jinaai/jina-embeddings-v2-base-code",
        top_k=1,
        repository_id=repository_id,
        revision=revision,
    )
    assert [result.chunk_id for result in dense_results] == [chunk_id]
    assert dense_results[0].source == "dense"


def test_save_search_texts_do_not_overwrite_each_other(repository: CodeRAGRepository) -> None:
    repository_id, file_id, chunk_id = _sample_ids()
    revision = "main"

    repository.save_repository(
        Repository(
            id=repository_id,
            name="sample-repository",
            revision=revision,
            root_path="/tmp/sample",
        )
    )
    repository.save_file_metadata(
        FileMetadata(
            id=file_id,
            repository_id=repository_id,
            revision=revision,
            path="src/main.py",
            extension=".py",
            language="python",
            size_bytes=1,
            line_count=1,
            content_hash="hash",
        ),
        raw_content="pass\n",
    )
    repository.save_chunk(
        CodeChunk(
            id=chunk_id,
            repository_id=repository_id,
            file_id=file_id,
            path="src/main.py",
            language="python",
            chunk_type="file",
            start_line=1,
            end_line=1,
            content="pass\n",
            content_hash="chunk-hash",
        )
    )

    repository.save_bm25_text(chunk_id, "bm25-value")
    repository.save_embedding_text(chunk_id, "embedding-value")

    with repository.engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                    SELECT bm25_text, embedding_text
                    FROM chunk_search_texts
                    WHERE chunk_id = :chunk_id
                    """
                ),
                {"chunk_id": chunk_id},
            )
            .mappings()
            .one()
        )

    assert row["bm25_text"] == "bm25-value"
    assert row["embedding_text"] == "embedding-value"
