# Retrieval Experiments

Sprint 2 experiments will compare:

1. BM25 only;
2. dense retrieval only;
3. AST candidates only;
4. BM25 + dense;
5. BM25 + dense + AST candidates using RRF.

Dense retrieval should run with two embedding models:

- primary code model: `jinaai/jina-embeddings-v2-base-code`;
- lightweight baseline: `sentence-transformers/all-MiniLM-L6-v2`.

The pgvector storage layer keeps embeddings under `(chunk_id, embedding_model)`, so both models
can be indexed and evaluated without overwriting each other. Model-specific vector indexes should
be created with `CodeRAGRepository.create_vector_index(embedding_model=..., dimensions=...)`.

Planned metrics: Recall@k, MRR, MAP, nDCG@k, and latency.
