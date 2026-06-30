# Data Contracts

`src/gitflame_coderag/schemas.py` is the executable source of truth. All modules must exchange
those models or values explicitly derived from them. Do not introduce competing dictionaries with
different field names.

## Ownership

| Area | Owner | Package |
|---|---|---|
| Schemas and AST chunking | Danil | `schemas.py`, `chunking/`, `retrieval/ast.py` |
| Repository ingestion | Kirill | `config/`, `ingestion/` |
| BM25 | Zhenya | `retrieval/bm25.py` |
| Reranking and final ranking | Zhenya | `retrieval/reranker.py` |
| Embeddings and dense search | Karim | `embeddings/`, `retrieval/dense.py` |
| Persistence | Martin | `storage/`, `migrations/` |

## Function Contracts

### Ingestion

```python
load_repository_files(repo_path: Path, repository_id: str, revision: str) -> list[RepositoryFile]
load_ai_config(config_path: Path) -> dict[str, Any]
parse_ai_config(raw_config: dict[str, Any]) -> AIConfig
filter_files_by_config(files: list[RepositoryFile], config: AIConfig) -> list[RepositoryFile]
detect_language(path: Path, content: str) -> str
build_file_metadata(path: Path, content: str, repository_id: str, revision: str) -> FileMetadata
```

### Chunking

```python
chunk_file_with_ast_grep(file: RepositoryFile, config: AIConfig) -> list[CodeChunk]
chunk_file_fallback_window(file: RepositoryFile, config: AIConfig) -> list[CodeChunk]
build_chunks(files: list[RepositoryFile], config: AIConfig) -> list[CodeChunk]
extract_structural_metadata(chunk: CodeChunk) -> StructuralMetadata
```

### Search representations

```python
build_bm25_text(chunk: CodeChunk, metadata: StructuralMetadata) -> str
build_embedding_text(chunk: CodeChunk, metadata: StructuralMetadata) -> str
extract_keywords_from_chunk(chunk: CodeChunk) -> ChunkKeywords
```

### Retrieval

```python
build_bm25_index(chunks: list[CodeChunk]) -> BM25Index
bm25_search(query: str, index: BM25Index, top_k: int) -> list[RetrievalResult]
dense_search(query_vector: list[float], embeddings: list[ChunkEmbedding], top_k: int) -> list[RetrievalResult]
ast_candidate_search(keywords: list[str], chunks: list[CodeChunk], top_k: int) -> list[RetrievalResult]
rrf_fusion(rankings: list[list[RetrievalResult]], top_k: int, rrf_k: int = 60) -> list[RetrievalResult]
```

### Reranking (Sprint 2)

The reranker is a stage **after** RRF: it rescores the fused candidates with a cross-encoder and
returns the final top-k ordering. It consumes the RRF `RetrievalResult` list plus a
`chunk_id -> CodeChunk` lookup (for the chunk content) and returns `RetrievalResult` objects with
`source="reranker"` and `reranker_score` populated; component scores (`bm25_score` / `dense_score` /
`ast_score` / `rrf_score`) are preserved. Reranked results map onto `EvidenceChunk.scores.reranker`
when building final evidence. When the model is unavailable the stage falls back to RRF order.

```python
load_reranker_model(model_name: str = ..., device: str = "cpu") -> CrossEncoderLike | None
build_reranker_input(query: str, chunk: CodeChunk, max_pair_chars: int = 2000) -> tuple[str, str]
score_query_chunk_pair(model: CrossEncoderLike, query: str, chunk: CodeChunk) -> float
rerank_candidates(query: str, candidates: list[RetrievalResult], chunks_by_id: dict[str, CodeChunk], model=None, *, top_k: int, ...) -> list[RetrievalResult]
reranker_fallback(candidates: list[RetrievalResult], *, top_k: int) -> list[RetrievalResult]
compare_rrf_vs_reranker(cases: list[RerankerCase], *, model=None, k_values=(1, 3, 5, 10), ...) -> dict
```

The default reranker model is `cross-encoder/ms-marco-MiniLM-L-6-v2` (lightweight, CPU, no extra
dependencies); the model is configurable via `AIConfig.reranker` (`RerankerConfig`). Tunable
hyperparameters live there: `reranker_top_k` (RRF candidate pool fed to the reranker) and
`final_top_k` (final evidence count).

### Storage

Storage functions receive schema models and return persisted identifiers or schema models. Database
rows must not leak into retrieval and chunking packages.

```python
save_repository(repository: Repository) -> None
save_file_metadata(metadata: FileMetadata) -> None
save_chunk(chunk: CodeChunk) -> None
save_structural_metadata(metadata: StructuralMetadata) -> None
save_bm25_text(chunk_id: str, text: str) -> None
save_embedding_text(chunk_id: str, text: str) -> None
save_embedding_vector(embedding: ChunkEmbedding) -> None
save_keywords(keywords: ChunkKeywords) -> None
load_chunks_for_repository(repository_id: str, revision: str) -> list[CodeChunk]
```

## Invariants

- Raw source code and chunk content are never destructively normalized.
- Paths are repository-relative and use `/` separators.
- `start_line` and `end_line` are 1-based and inclusive.
- Every chunk belongs to exactly one file and repository revision.
- Split chunks use `parent_chunk_id` to point to the original large chunk id and
  `split_index` / `split_count` to preserve part order.
- Search texts and embeddings reference an existing `chunk_id`.
- Retrieval results always state their source and rank.
- Reranked results use `source="reranker"`, set `reranker_score`, and preserve upstream component
  scores; `reranker_score` stays `None` when the reranker did not run (fallback to RRF order).
- `expected_chunks` is not required in Sprint 1.
