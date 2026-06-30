"""Dense retrieval interfaces owned by the embeddings workstream."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from gitflame_coderag.embeddings import DEFAULT_EMBEDDING_MODEL, embed_query
from gitflame_coderag.schemas import ChunkEmbedding, RetrievalResult


class DenseVectorStore(Protocol):
    def search_similar_chunks(
        self,
        query_vector: list[float],
        *,
        embedding_model: str,
        top_k: int,
        repository_id: str | None = None,
        revision: str | None = None,
    ) -> list[RetrievalResult]: ...


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if len(vector_a) != len(vector_b):
        raise ValueError("cosine similarity requires vectors with equal dimensions")

    a = np.asarray(vector_a, dtype=np.float32)
    b = np.asarray(vector_b, dtype=np.float32)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def dense_search(
    query_vector: list[float],
    embeddings: list[ChunkEmbedding],
    top_k: int,
) -> list[RetrievalResult]:
    if top_k <= 0:
        return []

    scored = [
        (embedding.chunk_id, cosine_similarity(query_vector, embedding.vector))
        for embedding in embeddings
    ]
    ranked = sorted(scored, key=lambda item: (-item[1], item[0]))[:top_k]
    return [
        RetrievalResult(
            chunk_id=chunk_id,
            rank=rank,
            score=score,
            dense_score=score,
            source="dense",
        )
        for rank, (chunk_id, score) in enumerate(ranked, start=1)
    ]


def dense_retrieval_pgvector(
    query: str,
    vector_store: DenseVectorStore,
    top_k: int,
    *,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    repository_id: str | None = None,
    revision: str | None = None,
) -> list[RetrievalResult]:
    if top_k <= 0 or not query.strip():
        return []

    query_vector = embed_query(query, model_name=embedding_model)
    return vector_store.search_similar_chunks(
        query_vector,
        embedding_model=embedding_model,
        top_k=top_k,
        repository_id=repository_id,
        revision=revision,
    )


def rank_dense_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    ranked = sorted(results, key=lambda result: (-result.score, result.chunk_id))
    return [
        result.model_copy(update={"rank": rank, "source": "dense", "dense_score": result.score})
        for rank, result in enumerate(ranked, start=1)
    ]
