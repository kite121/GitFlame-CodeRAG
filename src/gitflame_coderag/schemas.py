"""Shared data contracts used by every CodeRAG module."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Repository(ContractModel):
    id: str
    name: str
    source: str | None = None
    revision: str
    root_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FileMetadata(ContractModel):
    id: str
    repository_id: str
    revision: str
    path: str
    extension: str
    language: str
    size_bytes: int = Field(ge=0)
    line_count: int = Field(ge=0)
    content_hash: str
    is_test: bool = False
    is_config: bool = False
    is_docs: bool = False


class RepositoryFile(ContractModel):
    metadata: FileMetadata
    raw_content: str


class Issue(ContractModel):
    id: str
    repository_id: str
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    expected_files: list[str] = Field(default_factory=list)


class ChunkingConfig(ContractModel):
    strategy: str = "ast_aware"
    fallback_strategy: str = "fixed_window"
    max_chunk_lines: int = Field(default=80, ge=1)
    overlap_lines: int = Field(default=10, ge=0)
    include_metadata: bool = True


class RetrievalConfig(ContractModel):
    top_k: int = Field(default=10, ge=1)
    use_bm25: bool = True
    use_dense: bool = True
    use_ast_candidates: bool = True
    fusion_method: str = "rrf"


class EmbeddingConfig(ContractModel):
    model: str = "jinaai/jina-embeddings-v2-base-code"
    normalize_vectors: bool = True
    batch_size: int = Field(default=32, ge=1)


class AIConfig(ContractModel):
    version: int = 1
    include: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude: list[str] = Field(default_factory=list)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


class CodeChunk(ContractModel):
    id: str
    parent_chunk_id: str | None = None
    split_index: int | None = Field(default=None, ge=1)
    split_count: int | None = Field(default=None, ge=1)
    repository_id: str
    file_id: str
    path: str
    language: str
    chunk_type: Literal["ast", "fixed_window", "file"]
    node_type: str | None = None
    symbol_name: str | None = None
    parent_symbol: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content: str
    content_hash: str
    token_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_split_metadata(self) -> "CodeChunk":
        split_fields = (self.parent_chunk_id, self.split_index, self.split_count)
        if not any(value is not None for value in split_fields):
            return self

        if self.parent_chunk_id is None or self.split_index is None or self.split_count is None:
            raise ValueError(
                "parent_chunk_id, split_index, and split_count must be set together"
            )
        if self.split_index > self.split_count:
            raise ValueError("split_index must be less than or equal to split_count")
        return self


class StructuralMetadata(ContractModel):
    chunk_id: str
    imports: list[str] = Field(default_factory=list)
    calls: list[str] = Field(default_factory=list)
    defined_symbols: list[str] = Field(default_factory=list)
    referenced_symbols: list[str] = Field(default_factory=list)
    flags: dict[str, bool] = Field(default_factory=dict)


class ChunkSearchTexts(ContractModel):
    chunk_id: str
    bm25_text: str
    embedding_text: str


class ChunkKeywords(ContractModel):
    chunk_id: str
    identifiers: list[str] = Field(default_factory=list)
    identifier_tokens: list[str] = Field(default_factory=list)
    string_literals: list[str] = Field(default_factory=list)
    comments_terms: list[str] = Field(default_factory=list)
    path_tokens: list[str] = Field(default_factory=list)


class ChunkEmbedding(ContractModel):
    chunk_id: str
    embedding_model: str
    vector: list[float]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrievalRun(ContractModel):
    id: str
    repository_id: str
    issue_id: str
    query_text: str
    query_keywords: list[str] = Field(default_factory=list)
    top_k: int = Field(ge=1)
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrievalResult(ContractModel):
    chunk_id: str
    rank: int = Field(ge=1)
    score: float
    source: Literal["bm25", "dense", "ast", "rrf"]
    bm25_score: float | None = None
    dense_score: float | None = None
    ast_score: float | None = None
    rrf_score: float | None = None
    evidence_reason: str | None = None


class EvidenceScores(ContractModel):
    bm25: float | None = None
    dense: float | None = None
    ast: float | None = None
    rrf: float | None = None


class EvidenceChunk(ContractModel):
    chunk_id: str
    repository_id: str
    path: str
    language: str
    node_type: str | None = None
    symbol_name: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content: str
    scores: EvidenceScores = Field(default_factory=EvidenceScores)
    evidence_reason: str
