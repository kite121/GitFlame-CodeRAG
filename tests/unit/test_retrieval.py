from math import log2

import pytest

from gitflame_coderag.embeddings import LIGHTWEIGHT_BASELINE_MODEL
from gitflame_coderag.retrieval import dense as dense_module
from gitflame_coderag.retrieval.dense import (
    cosine_similarity,
    dense_retrieval_pgvector,
    dense_search,
    rank_dense_results,
)
from gitflame_coderag.retrieval.metrics import (
    compute_average_precision_at_k,
    compute_map_ndcg,
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
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


def test_dense_retrieval_pgvector_embeds_query_and_uses_vector_store(monkeypatch) -> None:
    class FakeVectorStore:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def search_similar_chunks(
            self,
            query_vector: list[float],
            *,
            embedding_model: str,
            top_k: int,
            repository_id: str | None = None,
            revision: str | None = None,
        ) -> list[RetrievalResult]:
            self.calls.append(
                {
                    "query_vector": query_vector,
                    "embedding_model": embedding_model,
                    "top_k": top_k,
                    "repository_id": repository_id,
                    "revision": revision,
                }
            )
            return [
                RetrievalResult(
                    chunk_id="chunk-1",
                    rank=1,
                    score=0.9,
                    dense_score=0.9,
                    source="dense",
                )
            ]

    monkeypatch.setattr(
        dense_module,
        "embed_query",
        lambda query, **kwargs: [0.1, 0.2, 0.3],
    )
    store = FakeVectorStore()

    results = dense_retrieval_pgvector(
        "refresh recommendations",
        store,
        top_k=5,
        embedding_model=LIGHTWEIGHT_BASELINE_MODEL,
        repository_id="repo",
        revision="main",
    )

    assert [result.chunk_id for result in results] == ["chunk-1"]
    assert store.calls == [
        {
            "query_vector": [0.1, 0.2, 0.3],
            "embedding_model": LIGHTWEIGHT_BASELINE_MODEL,
            "top_k": 5,
            "repository_id": "repo",
            "revision": "main",
        }
    ]


def test_dense_retrieval_pgvector_skips_empty_query(monkeypatch) -> None:
    monkeypatch.setattr(dense_module, "embed_query", lambda query, **kwargs: [1.0])

    class FakeVectorStore:
        def search_similar_chunks(self, *args: object, **kwargs: object) -> list[RetrievalResult]:
            raise AssertionError("empty queries should not hit the vector store")

    assert dense_retrieval_pgvector("   ", FakeVectorStore(), top_k=5) == []


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


def test_retrieval_metrics_for_single_ranked_list() -> None:
    results = [
        RetrievalResult(chunk_id="a", rank=1, score=0.9, source="dense"),
        RetrievalResult(chunk_id="b", rank=2, score=0.8, source="dense"),
        RetrievalResult(chunk_id="c", rank=3, score=0.7, source="dense"),
        RetrievalResult(chunk_id="d", rank=4, score=0.6, source="dense"),
    ]
    relevant = {"b", "d", "missing"}

    assert compute_recall_at_k(results, relevant, k=3) == pytest.approx(1 / 3)
    assert compute_mrr(results, relevant, k=3) == pytest.approx(1 / 2)
    assert compute_average_precision_at_k(results, relevant, k=4) == pytest.approx(
        ((1 / 2) + (2 / 4)) / 3
    )
    dcg = (1 / log2(2 + 1)) + (1 / log2(4 + 1))
    ideal_dcg = (1 / log2(1 + 1)) + (1 / log2(2 + 1)) + (1 / log2(3 + 1))
    assert compute_ndcg_at_k(results, relevant, k=4) == pytest.approx(
        dcg / ideal_dcg
    )


def test_compute_map_ndcg_averages_runs() -> None:
    perfect = [RetrievalResult(chunk_id="a", rank=1, score=1.0, source="dense")]
    miss = [RetrievalResult(chunk_id="b", rank=1, score=1.0, source="dense")]

    scores = compute_map_ndcg(
        [
            (perfect, {"a"}),
            (miss, {"a"}),
        ],
        k=1,
    )

    assert scores == {"map": 0.5, "ndcg": 0.5}
