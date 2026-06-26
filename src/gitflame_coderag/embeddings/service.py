"""Embedding model adapter owned by the embeddings workstream."""

from __future__ import annotations

import re
from collections.abc import Iterable

from gitflame_coderag.schemas import (
    ChunkEmbedding,
    ChunkKeywords,
    CodeChunk,
    StructuralMetadata,
)

DEFAULT_EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-code"

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STRING_RE = re.compile(
    r"""
    (?P<quote>['"])
    (?P<value>(?:\\.|(?! (?P=quote) ).)*)
    (?P=quote)
    """,
    re.VERBOSE | re.DOTALL,
)
_LINE_COMMENT_RE = re.compile(r"(?://|#)\s*(?P<comment>.*)")
_BLOCK_COMMENT_RE = re.compile(r"/\*(?P<comment>.*?)\*/", re.DOTALL)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]*")

_CODE_KEYWORDS = {
    "and",
    "as",
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "def",
    "default",
    "defer",
    "del",
    "do",
    "else",
    "enum",
    "except",
    "export",
    "extends",
    "false",
    "finally",
    "for",
    "from",
    "func",
    "function",
    "go",
    "if",
    "import",
    "in",
    "interface",
    "let",
    "match",
    "nil",
    "none",
    "not",
    "null",
    "or",
    "package",
    "pass",
    "private",
    "protected",
    "public",
    "raise",
    "return",
    "select",
    "self",
    "static",
    "struct",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "type",
    "var",
    "while",
    "with",
    "yield",
}

_COMMENT_STOPWORDS = _CODE_KEYWORDS | {
    "a",
    "an",
    "are",
    "be",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}

_MODEL_CACHE: dict[str, object] = {}


def build_embedding_text(chunk: CodeChunk, metadata: StructuralMetadata) -> str:
    header = [
        f"File: {chunk.path}",
        f"Language: {chunk.language}",
        f"Symbol: {chunk.symbol_name or ''}",
        f"Parent symbol: {chunk.parent_symbol or ''}",
        f"Node type: {chunk.node_type or ''}",
    ]
    if metadata.imports:
        header.append(f"Imports: {', '.join(metadata.imports)}")
    if metadata.calls:
        header.append(f"Calls: {', '.join(metadata.calls)}")
    if metadata.defined_symbols:
        header.append(f"Defined symbols: {', '.join(metadata.defined_symbols)}")
    if metadata.referenced_symbols:
        header.append(f"Referenced symbols: {', '.join(metadata.referenced_symbols)}")
    return "\n".join(header) + f"\n\nCode:\n{chunk.content}"


def extract_keywords_from_chunk(chunk: CodeChunk) -> ChunkKeywords:
    identifiers = _dedupe(
        identifier
        for identifier in [
            chunk.symbol_name,
            chunk.parent_symbol,
            *_IDENTIFIER_RE.findall(chunk.content),
        ]
        if identifier and identifier.lower() not in _CODE_KEYWORDS
    )
    identifier_tokens = _dedupe(
        token
        for identifier in identifiers
        for token in _split_identifier(identifier)
        if token not in _CODE_KEYWORDS
    )
    string_literals = _dedupe(
        _clean_literal(match.group("value")) for match in _STRING_RE.finditer(chunk.content)
    )
    comments_terms = _dedupe(
        token
        for comment in _extract_comments(chunk.content)
        for token in _WORD_RE.findall(comment.lower())
        if len(token) > 1 and token not in _COMMENT_STOPWORDS
    )
    path_tokens = _dedupe(
        token
        for part in re.split(r"[/.\-_]+", chunk.path)
        for token in _split_identifier(part)
        if token and token not in _CODE_KEYWORDS
    )

    return ChunkKeywords(
        chunk_id=chunk.id,
        identifiers=identifiers,
        identifier_tokens=identifier_tokens,
        string_literals=string_literals,
        comments_terms=comments_terms,
        path_tokens=path_tokens,
    )


def embed_text(text: str) -> list[float]:
    return _embed_texts([text])[0]


def embed_chunks(chunks: list[CodeChunk]) -> list[ChunkEmbedding]:
    if not chunks:
        return []

    texts = [
        build_embedding_text(chunk, StructuralMetadata(chunk_id=chunk.id))
        for chunk in chunks
    ]
    vectors = _embed_texts(texts)
    return [
        ChunkEmbedding(
            chunk_id=chunk.id,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            vector=vector,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]


def embed_query(query: str) -> list[float]:
    return embed_text(query)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model(DEFAULT_EMBEDDING_MODEL)
    vectors = model.encode(  # type: ignore[attr-defined]
        texts,
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [vector.astype(float).tolist() for vector in vectors]


def _load_model(model_name: str) -> object:
    cached_model = _MODEL_CACHE.get(model_name)
    if cached_model is not None:
        return cached_model

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, trust_remote_code=True)
    _MODEL_CACHE[model_name] = model
    return model


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _split_identifier(identifier: str) -> list[str]:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier)
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", normalized)
    raw_parts = re.split(r"[^A-Za-z0-9]+", normalized)
    return [
        part.lower()
        for part in raw_parts
        if part and not part.isdigit() and len(part) > 1
    ]


def _clean_literal(value: str) -> str:
    return " ".join(value.split())


def _extract_comments(content: str) -> list[str]:
    comments = [match.group("comment") for match in _BLOCK_COMMENT_RE.finditer(content)]
    comments.extend(match.group("comment") for match in _LINE_COMMENT_RE.finditer(content))
    return comments
