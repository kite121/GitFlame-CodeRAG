import pytest

from gitflame_coderag.retrieval.dense import (
    cosine_similarity,
    dense_search,
    rank_dense_results,
)
from gitflame_coderag.retrieval.rrf import rrf_fusion
from gitflame_coderag.schemas import ChunkEmbedding, RetrievalResult


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_handles_zero_and_dimension_mismatch() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    with pytest.raises(ValueError, match="equal dimensions"):
        cosine_similarity([1.0], [1.0, 0.0])


def test_dense_search_returns_top_k_ranked_results() -> None:
    embeddings = [
        ChunkEmbedding(chunk_id="b", embedding_model="model", vector=[0.8, 0.2]),
        ChunkEmbedding(chunk_id="a", embedding_model="model", vector=[1.0, 0.0]),
        ChunkEmbedding(chunk_id="c", embedding_model="model", vector=[0.0, 1.0]),
    ]

    results = dense_search([1.0, 0.0], embeddings, top_k=2)

    assert [result.chunk_id for result in results] == ["a", "b"]
    assert [result.rank for result in results] == [1, 2]
    assert all(result.source == "dense" for result in results)
    assert all(result.dense_score == result.score for result in results)


def test_rank_dense_results_sorts_and_reassigns_ranks() -> None:
    results = [
        RetrievalResult(chunk_id="b", rank=7, score=0.5, source="dense"),
        RetrievalResult(chunk_id="a", rank=3, score=0.9, source="dense"),
    ]

    ranked = rank_dense_results(results)

    assert [(result.chunk_id, result.rank) for result in ranked] == [("a", 1), ("b", 2)]
    assert results[0].rank == 7


def test_rrf_rewards_chunks_returned_by_multiple_rankers() -> None:
    bm25 = [
        RetrievalResult(chunk_id="a", rank=1, score=10.0, source="bm25"),
        RetrievalResult(chunk_id="b", rank=2, score=8.0, source="bm25"),
    ]
    dense = [
        RetrievalResult(chunk_id="b", rank=1, score=0.9, source="dense"),
        RetrievalResult(chunk_id="c", rank=2, score=0.8, source="dense"),
    ]

    fused = rrf_fusion([bm25, dense], top_k=3)

    assert fused[0].chunk_id == "b"
    assert fused[0].source == "rrf"
