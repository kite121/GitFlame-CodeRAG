"""Ranking metrics for retrieval experiments."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from math import log2

from gitflame_coderag.schemas import RetrievalResult


def compute_recall_at_k(
    results: Sequence[RetrievalResult],
    relevant_chunk_ids: Collection[str],
    k: int,
) -> float:
    relevant = _relevant_set(relevant_chunk_ids)
    if not relevant:
        return 0.0

    retrieved = set(_top_unique_chunk_ids(results, k))
    return len(retrieved & relevant) / len(relevant)


def compute_mrr(
    results: Sequence[RetrievalResult],
    relevant_chunk_ids: Collection[str],
    k: int | None = None,
) -> float:
    relevant = _relevant_set(relevant_chunk_ids)
    if not relevant:
        return 0.0

    limit = k if k is not None else len(results)
    for position, chunk_id in enumerate(_top_unique_chunk_ids(results, limit), start=1):
        if chunk_id in relevant:
            return 1.0 / position
    return 0.0


def compute_average_precision_at_k(
    results: Sequence[RetrievalResult],
    relevant_chunk_ids: Collection[str],
    k: int,
) -> float:
    relevant = _relevant_set(relevant_chunk_ids)
    if not relevant:
        return 0.0

    hits = 0
    precision_sum = 0.0
    for position, chunk_id in enumerate(_top_unique_chunk_ids(results, k), start=1):
        if chunk_id not in relevant:
            continue
        hits += 1
        precision_sum += hits / position

    denominator = min(len(relevant), max(k, 0))
    return precision_sum / denominator if denominator else 0.0


def compute_ndcg_at_k(
    results: Sequence[RetrievalResult],
    relevant_chunk_ids: Collection[str],
    k: int,
) -> float:
    relevant = _relevant_set(relevant_chunk_ids)
    if not relevant or k <= 0:
        return 0.0

    dcg = sum(
        1.0 / log2(position + 1)
        for position, chunk_id in enumerate(_top_unique_chunk_ids(results, k), start=1)
        if chunk_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(1.0 / log2(position + 1) for position in range(1, ideal_hits + 1))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def compute_map_ndcg(
    runs: Iterable[tuple[Sequence[RetrievalResult], Collection[str]]],
    k: int,
) -> dict[str, float]:
    run_list = list(runs)
    if not run_list:
        return {"map": 0.0, "ndcg": 0.0}

    average_precisions = [
        compute_average_precision_at_k(results, relevant_chunk_ids, k)
        for results, relevant_chunk_ids in run_list
    ]
    ndcg_scores = [
        compute_ndcg_at_k(results, relevant_chunk_ids, k)
        for results, relevant_chunk_ids in run_list
    ]
    query_count = len(run_list)
    return {
        "map": sum(average_precisions) / query_count,
        "ndcg": sum(ndcg_scores) / query_count,
    }


def _top_unique_chunk_ids(results: Sequence[RetrievalResult], k: int | None) -> list[str]:
    if k is not None and k <= 0:
        return []

    limit = k if k is not None else len(results)
    seen: set[str] = set()
    chunk_ids: list[str] = []
    for result in sorted(results, key=lambda item: (item.rank, item.chunk_id)):
        if result.chunk_id in seen:
            continue
        seen.add(result.chunk_id)
        chunk_ids.append(result.chunk_id)
        if len(chunk_ids) >= limit:
            break
    return chunk_ids


def _relevant_set(relevant_chunk_ids: Collection[str]) -> set[str]:
    return {chunk_id for chunk_id in relevant_chunk_ids if chunk_id}
