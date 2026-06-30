from collections.abc import Sequence
from typing import Any

import pytest

from gitflame_coderag.retrieval import reranker
from gitflame_coderag.retrieval.reranker import (
    RerankerCase,
    build_reranker_input,
    compare_rrf_vs_reranker,
    rerank_candidates,
    reranker_fallback,
    score_query_chunk_pair,
)
from gitflame_coderag.schemas import CodeChunk, RetrievalResult


class DummyCrossEncoder:
    """Offline stand-in for ``sentence_transformers.CrossEncoder``.

    Scores each ``(query, passage)`` pair by the first marker substring found in the
    passage, which lets tests pin an exact reranked order without downloading weights.
    """

    def __init__(self, marker_scores: dict[str, float]) -> None:
        self.marker_scores = marker_scores
        self.calls: list[dict[str, Any]] = []

    def predict(self, sentences: Sequence[tuple[str, str]], **kwargs: Any) -> list[float]:
        self.calls.append({"sentences": list(sentences), "kwargs": kwargs})
        scores: list[float] = []
        for _query, passage in sentences:
            score = 0.0
            for marker, value in self.marker_scores.items():
                if marker in passage:
                    score = value
                    break
            scores.append(score)
        return scores


def make_chunk(chunk_id: str, path: str, content: str, **kwargs: object) -> CodeChunk:
    defaults = dict(
        id=chunk_id,
        repository_id="repo",
        file_id=f"repo:rev:{path}",
        path=path,
        language="python",
        chunk_type="ast",
        start_line=1,
        end_line=max(1, content.count("\n") + 1),
        content=content,
        content_hash="hash",
    )
    defaults.update(kwargs)
    return CodeChunk(**defaults)


def make_result(chunk_id: str, score: float, rank: int = 1, **kwargs: object) -> RetrievalResult:
    defaults: dict[str, object] = dict(
        chunk_id=chunk_id, rank=rank, score=score, source="rrf", rrf_score=score
    )
    defaults.update(kwargs)
    return RetrievalResult(**defaults)


def test_build_reranker_input_includes_metadata_and_truncates() -> None:
    chunk = make_chunk(
        "c1", "src/auth/tokens.py", "X" * 5000, symbol_name="refresh", language="python"
    )

    query, passage = build_reranker_input("refresh token", chunk, max_pair_chars=100)

    assert query == "refresh token"
    assert "src/auth/tokens.py" in passage
    assert "python" in passage
    assert "refresh" in passage
    # body is truncated, header + newline + 100 body chars
    assert passage.endswith("X" * 100)
    assert "X" * 101 not in passage
    # raw content is never mutated
    assert chunk.content == "X" * 5000


def test_reranker_fallback_keeps_rrf_order_and_reassigns_ranks() -> None:
    candidates = [
        make_result("low", 0.1, rank=3),
        make_result("high", 0.9, rank=1),
        make_result("mid", 0.5, rank=2),
    ]

    result = reranker_fallback(candidates, top_k=2)

    assert [r.chunk_id for r in result] == ["high", "mid"]
    assert [r.rank for r in result] == [1, 2]
    # reranker did not run: scores untouched, source stays rrf
    assert all(r.reranker_score is None for r in result)
    assert all(r.source == "rrf" for r in result)
    assert "reranker unavailable" in result[0].evidence_reason


def test_rerank_candidates_reorders_by_model_score() -> None:
    chunks = {
        "c1": make_chunk("c1", "a.py", "marker M1"),
        "c2": make_chunk("c2", "b.py", "marker M2"),
        "c3": make_chunk("c3", "c.py", "marker M3"),
    }
    candidates = [
        make_result("c1", 0.9, rank=1, bm25_score=8.0),
        make_result("c2", 0.5, rank=2),
        make_result("c3", 0.1, rank=3),
    ]
    model = DummyCrossEncoder({"M3": 9.0, "M1": 5.0, "M2": 1.0})

    result = rerank_candidates("q", candidates, chunks, model=model, top_k=3)

    assert [r.chunk_id for r in result] == ["c3", "c1", "c2"]
    assert [r.rank for r in result] == [1, 2, 3]
    assert all(r.source == "reranker" for r in result)
    # reranker score is set and mirrored into the primary score field
    assert result[0].reranker_score == 9.0
    assert result[0].score == 9.0
    # component scores survive for traceability
    c1 = next(r for r in result if r.chunk_id == "c1")
    assert c1.bm25_score == 8.0
    assert c1.rrf_score == 0.9
    assert c1.reranker_score == 5.0


def test_rerank_candidates_respects_top_k() -> None:
    chunks = {
        "c1": make_chunk("c1", "a.py", "marker M1"),
        "c2": make_chunk("c2", "b.py", "marker M2"),
    }
    candidates = [make_result("c1", 0.9, rank=1), make_result("c2", 0.5, rank=2)]
    model = DummyCrossEncoder({"M2": 9.0, "M1": 1.0})

    result = rerank_candidates("q", candidates, chunks, model=model, top_k=1)

    assert len(result) == 1
    assert result[0].chunk_id == "c2"


def test_rerank_candidates_empty_returns_empty() -> None:
    model = DummyCrossEncoder({})
    assert rerank_candidates("q", [], {}, model=model, top_k=5) == []


def test_rerank_candidates_skips_unknown_chunk_ids() -> None:
    chunks = {"c1": make_chunk("c1", "a.py", "marker M1")}
    candidates = [make_result("c1", 0.9, rank=1), make_result("missing", 0.5, rank=2)]
    model = DummyCrossEncoder({"M1": 5.0})

    result = rerank_candidates("q", candidates, chunks, model=model, top_k=5)

    assert [r.chunk_id for r in result] == ["c1"]


def test_rerank_candidates_falls_back_when_model_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reranker, "load_reranker_model", lambda *a, **k: None)
    chunks = {"c1": make_chunk("c1", "a.py", "x"), "c2": make_chunk("c2", "b.py", "y")}
    candidates = [make_result("c1", 0.9, rank=1), make_result("c2", 0.5, rank=2)]

    result = rerank_candidates("q", candidates, chunks, model=None, top_k=2)

    assert [r.chunk_id for r in result] == ["c1", "c2"]
    assert all(r.source == "rrf" for r in result)
    assert all(r.reranker_score is None for r in result)


def test_score_query_chunk_pair() -> None:
    chunk = make_chunk("c1", "a.py", "marker M1")
    model = DummyCrossEncoder({"M1": 7.5})

    assert score_query_chunk_pair(model, "q", chunk) == 7.5


def test_compare_rrf_vs_reranker_reports_metrics_and_delta() -> None:
    chunks = {
        "irrelevant": make_chunk("irrelevant", "src/irrelevant.py", "marker ALPHA"),
        "relevant": make_chunk("relevant", "src/relevant.py", "marker BETA"),
    }
    candidates = [
        make_result("irrelevant", 0.9, rank=1),
        make_result("relevant", 0.1, rank=2),
    ]
    # Reranker pushes the relevant chunk above the irrelevant one.
    model = DummyCrossEncoder({"BETA": 10.0, "ALPHA": 1.0})
    case = RerankerCase(
        query="q",
        rrf_candidates=candidates,
        chunks_by_id=chunks,
        gold_paths={"src/relevant.py"},
    )

    report = compare_rrf_vs_reranker([case], model=model, k_values=(1, 3))

    assert report["num_cases"] == 1
    assert report["reranker_available"] is True
    # RRF ranks the irrelevant file first; reranker fixes it.
    assert report["rrf"]["recall@1"] == 0.0
    assert report["reranker"]["recall@1"] == 1.0
    assert report["rrf"]["mrr"] == 0.5
    assert report["reranker"]["mrr"] == 1.0
    assert report["delta"]["mrr"] == 0.5


def test_compare_rrf_vs_reranker_empty_cases() -> None:
    report = compare_rrf_vs_reranker([], model=DummyCrossEncoder({}), k_values=(1, 3))

    assert report["num_cases"] == 0
    assert report["rrf"]["mrr"] == 0.0
    assert report["delta"]["recall@1"] == 0.0
