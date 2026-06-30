"""Cross-encoder reranking stage (after RRF) and final ranking.

Owner: Zhenya. This module takes the fused RRF candidates and rescores each
``(issue query, code chunk)`` pair with a cross-encoder, producing the final
reranked top-k evidence ordering.

It is intentionally decoupled from the not-yet-finished end-to-end pipeline: it
consumes ``list[RetrievalResult]`` (the RRF output contract from
:func:`gitflame_coderag.retrieval.rrf.rrf_fusion`) plus a ``chunk_id -> CodeChunk``
lookup, and returns ``list[RetrievalResult]`` with ``source="reranker"`` and
``reranker_score`` populated, ready for ``build_evidence_chunks`` to convert into
``EvidenceChunk`` objects (the ``reranker`` score maps onto ``EvidenceScores.reranker``).

The stage degrades gracefully: when the reranker model cannot be loaded (offline /
missing weights), :func:`reranker_fallback` preserves the RRF ordering so the
pipeline keeps working.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from gitflame_coderag.schemas import CodeChunk, RetrievalResult

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_DEVICE = "cpu"
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_PAIR_CHARS = 2000


class CrossEncoderLike(Protocol):
    """Minimal interface the reranker depends on.

    A real ``sentence_transformers.CrossEncoder`` satisfies it, and so does any
    lightweight stub used in tests, which keeps unit tests offline and deterministic.
    """

    def predict(self, sentences: Sequence[tuple[str, str]], **kwargs: Any) -> Any: ...


# Cache loaded models by (model_name, device) so repeated calls (e.g. per issue in
# an experiment run) do not reload the weights. ``None`` is cached too, so a failed
# load is not retried on every call.
_MODEL_CACHE: dict[tuple[str, str], CrossEncoderLike | None] = {}


def load_reranker_model(
    model_name: str = DEFAULT_RERANKER_MODEL,
    device: str = DEFAULT_DEVICE,
) -> CrossEncoderLike | None:
    """Load a cross-encoder reranker, returning ``None`` when unavailable.

    Any failure (missing ``sentence-transformers``, no network, missing weights)
    is swallowed and surfaced as ``None`` so callers can fall back to RRF order.
    """
    cache_key = (model_name, device)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    model: CrossEncoderLike | None
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name, device=device)
    except Exception:
        # Broad on purpose: import errors, download failures and backend errors
        # all mean "no reranker available" and must trigger the fallback path.
        model = None

    _MODEL_CACHE[cache_key] = model
    return model


def build_reranker_input(
    query: str,
    chunk: CodeChunk,
    max_pair_chars: int = DEFAULT_MAX_PAIR_CHARS,
) -> tuple[str, str]:
    """Build a ``(query, passage)`` pair for the cross-encoder.

    The passage prepends high-signal metadata (path, language, symbol) to the raw
    chunk content. ``chunk.content`` is never mutated; only a truncated local copy
    is used so very large chunks stay within the model's context window.
    """
    header_parts = [chunk.path, chunk.language]
    if chunk.symbol_name:
        header_parts.append(chunk.symbol_name)
    header = " ".join(part for part in header_parts if part)

    body = chunk.content
    if max_pair_chars and len(body) > max_pair_chars:
        body = body[:max_pair_chars]

    passage = f"{header}\n{body}" if header else body
    return (query, passage)


def score_query_chunk_pair(
    model: CrossEncoderLike,
    query: str,
    chunk: CodeChunk,
    max_pair_chars: int = DEFAULT_MAX_PAIR_CHARS,
) -> float:
    """Score a single ``(query, chunk)`` pair. Batch scoring is preferred in bulk."""
    pair = build_reranker_input(query, chunk, max_pair_chars)
    scores = model.predict([pair])
    return float(scores[0])


def rerank_candidates(
    query: str,
    candidates: Sequence[RetrievalResult],
    chunks_by_id: Mapping[str, CodeChunk],
    model: CrossEncoderLike | None = None,
    *,
    top_k: int,
    model_name: str = DEFAULT_RERANKER_MODEL,
    device: str = DEFAULT_DEVICE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_pair_chars: int = DEFAULT_MAX_PAIR_CHARS,
) -> list[RetrievalResult]:
    """Rescore RRF candidates with a cross-encoder and return the reranked top-k.

    ``candidates`` are the RRF results; ``chunks_by_id`` supplies the chunk content
    to score. Component scores (``bm25_score``/``dense_score``/``ast_score``/
    ``rrf_score``) are preserved for traceability; ``source`` becomes ``"reranker"``
    and ``reranker_score`` is set. When no model is available the function falls back
    to :func:`reranker_fallback` (RRF order preserved).
    """
    if not candidates:
        return []

    if model is None:
        model = load_reranker_model(model_name, device)
    if model is None:
        return reranker_fallback(candidates, top_k=top_k)

    scorable: list[RetrievalResult] = []
    pairs: list[tuple[str, str]] = []
    for candidate in candidates:
        chunk = chunks_by_id.get(candidate.chunk_id)
        if chunk is None:
            # Cannot rerank a chunk we cannot read; drop it from the reranked set.
            continue
        scorable.append(candidate)
        pairs.append(build_reranker_input(query, chunk, max_pair_chars))

    if not scorable:
        return reranker_fallback(candidates, top_k=top_k)

    raw_scores = model.predict(pairs, batch_size=batch_size)
    scored = [
        (float(score), candidate)
        for score, candidate in zip(raw_scores, scorable, strict=True)
    ]
    # Deterministic order: highest score first, ties broken by chunk_id.
    scored.sort(key=lambda item: (-item[0], item[1].chunk_id))

    reranked: list[RetrievalResult] = []
    for rank, (score, candidate) in enumerate(scored[:top_k], start=1):
        reranked.append(
            candidate.model_copy(
                update={
                    "rank": rank,
                    "score": score,
                    "source": "reranker",
                    "reranker_score": score,
                    "evidence_reason": f"reranked by cross-encoder {model_name}",
                }
            )
        )
    return reranked


def reranker_fallback(
    candidates: Sequence[RetrievalResult],
    *,
    top_k: int,
) -> list[RetrievalResult]:
    """Return the top-k candidates in RRF order when the reranker is unavailable.

    Ranks are reassigned and ``reranker_score`` stays ``None`` (the reranker did not
    run); ``source`` is left untouched so consumers can see the order came from RRF.
    """
    ordered = sorted(candidates, key=lambda c: (-c.score, c.chunk_id))
    fallback: list[RetrievalResult] = []
    for rank, candidate in enumerate(ordered[:top_k], start=1):
        fallback.append(
            candidate.model_copy(
                update={
                    "rank": rank,
                    "evidence_reason": "reranker unavailable; kept RRF order",
                }
            )
        )
    return fallback


@dataclass(frozen=True)
class RerankerCase:
    """One evaluation case for :func:`compare_rrf_vs_reranker`.

    ``gold_paths`` is the relevance label set (issue ``expected_files``); a candidate
    counts as relevant when its chunk ``path`` is in this set (chunk-level gold is
    deferred beyond Sprint 1).
    """

    query: str
    rrf_candidates: list[RetrievalResult]
    chunks_by_id: dict[str, CodeChunk]
    gold_paths: set[str] = field(default_factory=set)


def compare_rrf_vs_reranker(
    cases: Sequence[RerankerCase],
    *,
    model: CrossEncoderLike | None = None,
    model_name: str = DEFAULT_RERANKER_MODEL,
    device: str = DEFAULT_DEVICE,
    k_values: Sequence[int] = (1, 3, 5, 10),
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_pair_chars: int = DEFAULT_MAX_PAIR_CHARS,
) -> dict[str, Any]:
    """Compare RRF-only ordering against RRF + reranker on labelled cases.

    Returns aggregate (mean) ``recall@k`` and ``mrr`` for both orderings plus the
    per-metric delta. The local ``_file_recall_at_k`` / ``_mrr`` helpers are a stand
    -in for Karim's ``metrics`` module and should be swapped for it once available.
    """
    if model is None:
        model = load_reranker_model(model_name, device)

    metrics = [f"recall@{k}" for k in k_values] + ["mrr"]
    rrf_scores: dict[str, list[float]] = {name: [] for name in metrics}
    rerank_scores: dict[str, list[float]] = {name: [] for name in metrics}

    for case in cases:
        rrf_ordered = sorted(case.rrf_candidates, key=lambda c: (-c.score, c.chunk_id))
        reranked = rerank_candidates(
            case.query,
            case.rrf_candidates,
            case.chunks_by_id,
            model=model,
            top_k=len(case.rrf_candidates),
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            max_pair_chars=max_pair_chars,
        )

        rrf_paths = _ranked_paths(rrf_ordered, case.chunks_by_id)
        rerank_paths = _ranked_paths(reranked, case.chunks_by_id)

        for k in k_values:
            rrf_scores[f"recall@{k}"].append(_file_recall_at_k(rrf_paths, case.gold_paths, k))
            rerank_scores[f"recall@{k}"].append(
                _file_recall_at_k(rerank_paths, case.gold_paths, k)
            )
        rrf_scores["mrr"].append(_mrr(rrf_paths, case.gold_paths))
        rerank_scores["mrr"].append(_mrr(rerank_paths, case.gold_paths))

    rrf_summary = {name: _mean(values) for name, values in rrf_scores.items()}
    rerank_summary = {name: _mean(values) for name, values in rerank_scores.items()}
    delta = {name: rerank_summary[name] - rrf_summary[name] for name in metrics}

    return {
        "num_cases": len(cases),
        "model": model_name,
        "reranker_available": model is not None,
        "rrf": rrf_summary,
        "reranker": rerank_summary,
        "delta": delta,
    }


def _ranked_paths(
    results: Sequence[RetrievalResult],
    chunks_by_id: Mapping[str, CodeChunk],
) -> list[str]:
    """Map a ranked result list to the chunk paths in rank order."""
    paths: list[str] = []
    for result in results:
        chunk = chunks_by_id.get(result.chunk_id)
        if chunk is not None:
            paths.append(chunk.path)
    return paths


def _file_recall_at_k(ranked_paths: Sequence[str], gold_paths: set[str], k: int) -> float:
    """Fraction of gold files hit by at least one chunk in the top-k results."""
    if not gold_paths:
        return 0.0
    top_k_paths = set(ranked_paths[:k])
    return len(top_k_paths & gold_paths) / len(gold_paths)


def _mrr(ranked_paths: Sequence[str], gold_paths: set[str]) -> float:
    """Reciprocal rank of the first chunk whose path is a gold file."""
    for index, path in enumerate(ranked_paths, start=1):
        if path in gold_paths:
            return 1.0 / index
    return 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
