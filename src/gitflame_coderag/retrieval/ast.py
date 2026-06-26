"""Structural candidate retrieval based on AST chunk metadata."""

from __future__ import annotations

import re
from collections.abc import Iterable

from gitflame_coderag.schemas import CodeChunk, RetrievalResult, StructuralMetadata


AST_FIELD_WEIGHTS = {
    "symbol_name": 5.0,
    "defined_symbols": 4.0,
    "parent_symbol": 3.5,
    "calls": 2.5,
    "path": 2.0,
    "imports": 1.5,
    "referenced_symbols": 1.0,
    "node_type": 0.5,
    "language": 0.25,
}

MIN_TERM_LENGTH = 2
MAX_TERM_LENGTH = 64


def ast_candidate_search(
    query_keywords: list[str],
    chunks: list[CodeChunk],
    metadata_by_chunk_id: dict[str, StructuralMetadata],
    top_k: int,
) -> list[RetrievalResult]:
    """Return top-k chunks ranked by AST metadata overlap with query keywords."""

    if top_k <= 0:
        return []

    query_terms = normalize_query_terms(query_keywords)
    if not query_terms:
        return []

    ranked_results = rank_ast_candidates(
        query_terms=query_terms,
        chunks=chunks,
        metadata_by_chunk_id=metadata_by_chunk_id,
    )
    return limit_results(ranked_results, top_k)


def rank_ast_candidates(
    query_terms: set[str],
    chunks: list[CodeChunk],
    metadata_by_chunk_id: dict[str, StructuralMetadata],
) -> list[RetrievalResult]:
    """Score every chunk with already-normalized query terms."""

    if not query_terms:
        return []

    results: list[RetrievalResult] = []
    for chunk in chunks:
        metadata = metadata_by_chunk_id.get(chunk.id)
        score = score_ast_chunk(
            query_terms=query_terms,
            chunk=chunk,
            metadata=metadata,
        )
        if score <= 0:
            continue

        results.append(
            RetrievalResult(
                chunk_id=chunk.id,
                rank=1,
                score=score,
                source="ast",
                ast_score=score,
            )
        )

    return sort_ast_results(results)


def score_ast_chunk(
    query_terms: set[str],
    chunk: CodeChunk,
    metadata: StructuralMetadata | None,
) -> float:
    """Compute a weighted structural score for one chunk."""

    weighted_terms = build_ast_search_terms(chunk, metadata)
    return score_term_matches(query_terms, weighted_terms)


def build_ast_search_terms(
    chunk: CodeChunk,
    metadata: StructuralMetadata | None,
) -> dict[str, set[str]]:
    """Build normalized searchable terms grouped by structural field."""

    terms = {
        "symbol_name": normalize_query_terms([chunk.symbol_name]),
        "parent_symbol": normalize_query_terms([chunk.parent_symbol]),
        "path": normalize_query_terms(chunk.path.split("/")),
        "node_type": normalize_query_terms([chunk.node_type]),
        "language": normalize_query_terms([chunk.language]),
        "imports": set[str](),
        "calls": set[str](),
        "defined_symbols": set[str](),
        "referenced_symbols": set[str](),
    }

    if metadata is None:
        return terms

    terms["imports"] = normalize_query_terms(metadata.imports)
    terms["calls"] = normalize_query_terms(metadata.calls)
    terms["defined_symbols"] = normalize_query_terms(metadata.defined_symbols)
    terms["referenced_symbols"] = normalize_query_terms(metadata.referenced_symbols)
    return terms


def normalize_query_terms(query_keywords: Iterable[str | None]) -> set[str]:
    """Normalize issue keywords or code symbols into comparable tokens."""

    normalized: set[str] = set()
    for keyword in query_keywords:
        normalized.update(normalize_symbol_term(keyword))
    return normalized


def normalize_symbol_term(term: str | None) -> list[str]:
    """Split and normalize snake_case, kebab-case, paths, and camelCase symbols."""

    if not term:
        return []

    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", term)
    raw_tokens = re.split(r"[^A-Za-z0-9]+", spaced)

    tokens: list[str] = []
    compact = "".join(raw_tokens).lower()
    if _is_valid_term(compact):
        tokens.append(compact)

    for token in raw_tokens:
        normalized = token.lower()
        if _is_valid_term(normalized):
            tokens.append(normalized)

    return list(dict.fromkeys(tokens))


def score_term_matches(
    query_terms: set[str],
    weighted_terms: dict[str, set[str]],
) -> float:
    """Score query overlap with field-grouped AST terms."""

    score = 0.0
    for field_name, field_terms in weighted_terms.items():
        matches = query_terms.intersection(field_terms)
        if matches:
            score += AST_FIELD_WEIGHTS.get(field_name, 1.0) * len(matches)
    return score


def sort_ast_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Sort AST results and assign stable 1-based ranks."""

    ranked = sorted(results, key=lambda result: (-result.score, result.chunk_id))
    return [
        _copy_result_with_rank(result, rank)
        for rank, result in enumerate(ranked, start=1)
    ]


def limit_results(results: list[RetrievalResult], top_k: int) -> list[RetrievalResult]:
    """Return top-k results with contiguous ranks."""

    if top_k <= 0:
        return []
    return [
        _copy_result_with_rank(result, rank)
        for rank, result in enumerate(results[:top_k], start=1)
    ]


def _is_valid_term(term: str) -> bool:
    return MIN_TERM_LENGTH <= len(term) <= MAX_TERM_LENGTH


def _copy_result_with_rank(
    result: RetrievalResult,
    rank: int,
) -> RetrievalResult:
    if hasattr(result, "model_copy"):
        return result.model_copy(update={"rank": rank})
    return result.copy(update={"rank": rank})
