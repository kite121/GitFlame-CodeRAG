CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT,
    revision TEXT NOT NULL,
    root_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repository_files (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    revision TEXT NOT NULL,
    path TEXT NOT NULL,
    language TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    line_count INTEGER NOT NULL CHECK (line_count >= 0),
    content_hash TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    is_test BOOLEAN NOT NULL DEFAULT false,
    is_config BOOLEAN NOT NULL DEFAULT false,
    is_docs BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (repository_id, revision, path)
);

CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_files JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS code_chunks (
    id TEXT PRIMARY KEY,
    parent_chunk_id TEXT,
    split_index INTEGER CHECK (split_index IS NULL OR split_index > 0),
    split_count INTEGER CHECK (split_count IS NULL OR split_count > 0),
    repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL REFERENCES repository_files(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    language TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    node_type TEXT,
    symbol_name TEXT,
    parent_symbol TEXT,
    start_line INTEGER NOT NULL CHECK (start_line > 0),
    end_line INTEGER NOT NULL CHECK (end_line >= start_line),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0 CHECK (token_count >= 0),
    CHECK (
        (
            parent_chunk_id IS NULL
            AND split_index IS NULL
            AND split_count IS NULL
        )
        OR (
            parent_chunk_id IS NOT NULL
            AND split_index IS NOT NULL
            AND split_count IS NOT NULL
            AND split_index <= split_count
        )
    )
);

CREATE TABLE IF NOT EXISTS chunk_structural_metadata (
    chunk_id TEXT PRIMARY KEY REFERENCES code_chunks(id) ON DELETE CASCADE,
    imports JSONB NOT NULL DEFAULT '[]'::jsonb,
    calls JSONB NOT NULL DEFAULT '[]'::jsonb,
    defined_symbols JSONB NOT NULL DEFAULT '[]'::jsonb,
    referenced_symbols JSONB NOT NULL DEFAULT '[]'::jsonb,
    flags JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS chunk_search_texts (
    chunk_id TEXT PRIMARY KEY REFERENCES code_chunks(id) ON DELETE CASCADE,
    bm25_text TEXT NOT NULL DEFAULT '',
    embedding_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id TEXT PRIMARY KEY REFERENCES code_chunks(id) ON DELETE CASCADE,
    embedding_model TEXT NOT NULL,
    embedding VECTOR(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunk_keywords (
    chunk_id TEXT PRIMARY KEY REFERENCES code_chunks(id) ON DELETE CASCADE,
    identifiers JSONB NOT NULL DEFAULT '[]'::jsonb,
    identifier_tokens JSONB NOT NULL DEFAULT '[]'::jsonb,
    string_literals JSONB NOT NULL DEFAULT '[]'::jsonb,
    comments_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    path_tokens JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS retrieval_runs (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    issue_id TEXT REFERENCES issues(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    query_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_k INTEGER NOT NULL CHECK (top_k > 0),
    retrieval_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retrieval_results (
    id BIGSERIAL PRIMARY KEY,
    retrieval_run_id TEXT NOT NULL REFERENCES retrieval_runs(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL REFERENCES code_chunks(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL CHECK (rank > 0),
    bm25_score DOUBLE PRECISION,
    dense_score DOUBLE PRECISION,
    ast_score DOUBLE PRECISION,
    rrf_score DOUBLE PRECISION,
    evidence_reason TEXT,
    UNIQUE (retrieval_run_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_repository_files_repo_revision
    ON repository_files(repository_id, revision);
CREATE INDEX IF NOT EXISTS idx_code_chunks_repo_path
    ON code_chunks(repository_id, path);
CREATE INDEX IF NOT EXISTS idx_code_chunks_repository_id
    ON code_chunks(repository_id);
CREATE INDEX IF NOT EXISTS idx_code_chunks_parent
    ON code_chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_results_run_rank
    ON retrieval_results(retrieval_run_id, rank);
