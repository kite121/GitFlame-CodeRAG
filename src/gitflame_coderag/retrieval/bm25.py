"""BM25 retrieval owned by the BM25 workstream.

This module turns :class:`~gitflame_coderag.schemas.CodeChunk` objects into a sparse lexical
index and answers issue queries with ranked :class:`~gitflame_coderag.schemas.RetrievalResult`
items. Raw chunk content is never mutated: the BM25 representation is a separate, derived text as
required by ``data_contracts.md`` and ``context.md``.

Public contract (see ``data_contracts.md``):

    build_bm25_text(chunk, metadata) -> str
    tokenize_for_bm25(text) -> list[str]
    build_bm25_index(chunks) -> BM25Index
    build_bm25_query(issue, config) -> str
    bm25_search(query, index, top_k) -> list[RetrievalResult]
    rank_bm25_results(results) -> list[RetrievalResult]
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Plus

from gitflame_coderag.schemas import (
    AIConfig,
    CodeChunk,
    Issue,
    RetrievalResult,
    StructuralMetadata,
)

# Split a raw text into candidate tokens on anything that is not a letter, digit, or underscore.
_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z_]+")

# Sub-token boundaries inside an identifier: lower/digit -> Upper ("handleIssue") and the
# acronym tail boundary Upper -> Upper+lower ("HTTPServer" -> "HTTP", "Server").
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

_MIN_TOKEN_LEN = 2

# BM25 hyper-parameters. These are the BM25Plus library defaults, surfaced as named constants so
# they are an explicit, documented tuning point. `b` controls length normalization; code chunks
# vary a lot in length and length is a weak relevance signal, so lowering `b` (toward ~0.5) is a
# likely win — but should be validated against precision@k / recall@k in Sprint 2 rather than
# guessed here. `k1` controls term-frequency saturation.
BM25_K1 = 1.5
BM25_B = 0.75

# Field boosting for code search: high-signal fields are repeated so a lexical match on a
# function/file name outranks an incidental mention buried in the body. BM25 term-frequency
# saturates, so these are deliberately gentle multipliers, not hard overrides.
_PATH_WEIGHT = 3  # file name (basename) is the strongest single path signal
_SYMBOL_WEIGHT = 3  # the chunk's own symbol / parent symbol
_DEFINED_WEIGHT = 2  # symbols the chunk defines (per structural metadata)

# Conservative grammatical stop-words. Only natural-language filler is removed so that issue
# queries are cleaner; programming keywords are intentionally kept and left to BM25's IDF.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with",
        "is", "are", "be", "by", "as", "it", "this", "that", "these", "those",
        "from", "into", "when", "then", "than", "but", "not", "no", "so", "if",
    }
)


@dataclass
class BM25Index:
    """In-memory BM25 index over chunks.

    ``chunk_ids[i]`` is the chunk that produced document ``i`` in ``bm25``. ``bm25`` is ``None``
    only when the index is empty (no chunks were supplied).

    We use ``BM25Plus`` rather than ``BM25Okapi``: its IDF ``log((N + 1) / n)`` stays positive even
    on the small corpora a single repository produces, where Okapi's ``log((N - n + 0.5) / (n +
    0.5))`` collapses to zero or negative scores and breaks ranking.
    """

    chunk_ids: list[str]
    bm25: BM25Plus | None


def _split_identifier(token: str) -> list[str]:
    """Split ``snake_case`` and ``camelCase`` identifiers into their sub-words."""
    parts: list[str] = []
    for piece in token.split("_"):
        if piece:
            parts.extend(part for part in _CAMEL_BOUNDARY.split(piece) if part)
    return parts


def tokenize_for_bm25(text: str) -> list[str]:
    """Normalize and tokenize ``text`` for BM25.

    For each raw token we keep the lower-cased original identifier *and* its ``snake_case`` /
    ``camelCase`` sub-words, so that both ``handleAnalyzeIssue`` and ``analyze`` match. Tokens
    shorter than two characters and a small set of grammatical stop-words are dropped; pure
    digit tokens (e.g. HTTP status codes) are preserved.
    """
    tokens: list[str] = []
    for raw in _TOKEN_SPLIT.split(text):
        if not raw:
            continue
        seen: set[str] = set()
        candidates = [raw.lower()]
        parts = _split_identifier(raw)
        if len(parts) > 1:
            candidates.extend(part.lower() for part in parts)
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if len(candidate) < _MIN_TOKEN_LEN or candidate in _STOPWORDS:
                continue
            tokens.append(candidate)
    return tokens


def build_bm25_text(chunk: CodeChunk, metadata: StructuralMetadata) -> str:
    """Build the lexical search representation for a chunk.

    Combines path, language, node type, symbol names and structural signals (imports, calls,
    defined/referenced symbols) with the raw chunk content. High-signal fields (file name, symbol
    names, defined symbols) are repeated so a name match outranks an incidental body mention; see
    the ``_*_WEIGHT`` constants. The original ``chunk.content`` is left untouched; tokenization and
    normalization happen later in :func:`tokenize_for_bm25`.
    """
    basename = chunk.path.rsplit("/", 1)[-1]
    parts: list[str] = [chunk.path, chunk.language]
    parts += [basename] * _PATH_WEIGHT
    if chunk.node_type:
        parts.append(chunk.node_type)
    for symbol in (chunk.symbol_name, chunk.parent_symbol):
        if symbol:
            parts += [symbol] * _SYMBOL_WEIGHT
    for symbol in metadata.defined_symbols:
        parts += [symbol] * _DEFINED_WEIGHT
    parts += metadata.imports
    parts += metadata.calls
    parts += metadata.referenced_symbols
    parts.append(chunk.content)
    return "\n".join(part for part in parts if part)


def build_bm25_index(
    chunks: list[CodeChunk],
    metadata: dict[str, StructuralMetadata] | None = None,
) -> BM25Index:
    """Build a BM25 index over ``chunks``.

    ``metadata`` is an optional ``chunk_id -> StructuralMetadata`` mapping; when a chunk has no
    entry (or the mapping is omitted) an empty :class:`StructuralMetadata` is used, so the index
    still builds from the chunk's own fields. Document order matches ``chunks``.
    """
    metadata = metadata or {}
    chunk_ids: list[str] = []
    corpus: list[list[str]] = []
    for chunk in chunks:
        chunk_meta = metadata.get(chunk.id) or StructuralMetadata(chunk_id=chunk.id)
        chunk_ids.append(chunk.id)
        corpus.append(tokenize_for_bm25(build_bm25_text(chunk, chunk_meta)))
    bm25 = BM25Plus(corpus, k1=BM25_K1, b=BM25_B) if corpus else None
    return BM25Index(chunk_ids=chunk_ids, bm25=bm25)


def build_bm25_query(issue: Issue, config: AIConfig) -> str:
    """Build the BM25 query text from an issue.

    BM25 owns its own query construction (the contract is ``build_bm25_query(issue, config)``) so
    the lexical ranker can shape the query independently of the dense and AST rankers. We combine
    the issue title, body and labels and collapse whitespace; lexical normalization (lower-casing,
    ``snake_case`` / ``camelCase`` splitting) is deferred to :func:`tokenize_for_bm25` so the query
    and the index use identical token rules.

    ``config`` is part of the shared contract and reserved for query shaping (field selection,
    expansion) once :class:`AIConfig` grows BM25 query options; it is unused in Sprint 1.
    """
    del config
    fields = [issue.title, issue.body, *issue.labels]
    return " ".join(" ".join(fields).split())


def bm25_search(query: str, index: BM25Index, top_k: int) -> list[RetrievalResult]:
    """Return the ``top_k`` chunks most relevant to ``query`` by BM25 score.

    ``query`` is the query text (typically produced by :func:`build_bm25_query`). It is tokenized
    with the same rules as the index. Results are ranked by descending score with ``chunk_id`` as a
    deterministic tie-breaker, and carry ``source="bm25"`` plus the raw BM25 score in both
    ``score`` and ``bm25_score``.
    """
    if index.bm25 is None or not index.chunk_ids:
        return []
    query_tokens = tokenize_for_bm25(query)
    if not query_tokens:
        return []
    scores = index.bm25.get_scores(query_tokens)
    paired = zip(index.chunk_ids, scores, strict=True)
    ranked = sorted(paired, key=lambda item: (-item[1], item[0]))[:top_k]
    return [
        RetrievalResult(
            chunk_id=chunk_id,
            rank=rank,
            score=float(score),
            bm25_score=float(score),
            source="bm25",
        )
        for rank, (chunk_id, score) in enumerate(ranked, start=1)
    ]


def rank_bm25_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    return sorted(results, key=lambda result: (-result.score, result.chunk_id))
