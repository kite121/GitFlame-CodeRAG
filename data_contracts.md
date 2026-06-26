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
- `expected_chunks` is not required in Sprint 1.
