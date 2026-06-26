from gitflame_coderag.embeddings import service
from gitflame_coderag.embeddings.service import (
    DEFAULT_EMBEDDING_MODEL,
    build_embedding_text,
    embed_chunks,
    embed_query,
    extract_keywords_from_chunk,
)
from gitflame_coderag.schemas import CodeChunk, StructuralMetadata


def make_chunk() -> CodeChunk:
    return CodeChunk(
        id="chunk-1",
        repository_id="repo",
        file_id="file-1",
        path="backend/internal/app/server.go",
        language="go",
        chunk_type="ast",
        node_type="function_declaration",
        symbol_name="handleAnalyzeIssue",
        parent_symbol="Server",
        start_line=10,
        end_line=18,
        content=(
            "// Analyze issue request handler\n"
            "func handleAnalyzeIssue(issueID string) error {\n"
            '    action := "refresh recommendations"\n'
            "    return runIssueAnalysis(issueID, action)\n"
            "}"
        ),
        content_hash="hash",
    )


def test_build_embedding_text_preserves_code_and_adds_context() -> None:
    chunk = make_chunk()
    metadata = StructuralMetadata(
        chunk_id=chunk.id,
        imports=["net/http"],
        calls=["runIssueAnalysis"],
        defined_symbols=["handleAnalyzeIssue"],
        referenced_symbols=["issueID"],
    )

    text = build_embedding_text(chunk, metadata)

    assert "File: backend/internal/app/server.go" in text
    assert "Language: go" in text
    assert "Symbol: handleAnalyzeIssue" in text
    assert "Node type: function_declaration" in text
    assert "Imports: net/http" in text
    assert "Calls: runIssueAnalysis" in text
    assert "Code:\n// Analyze issue request handler" in text


def test_extract_keywords_from_chunk_splits_identifiers_comments_strings_and_path() -> None:
    keywords = extract_keywords_from_chunk(make_chunk())

    assert "handleAnalyzeIssue" in keywords.identifiers
    assert "runIssueAnalysis" in keywords.identifiers
    assert {"handle", "analyze", "issue"}.issubset(keywords.identifier_tokens)
    assert "refresh recommendations" in keywords.string_literals
    assert {"analyze", "request", "handler"}.issubset(keywords.comments_terms)
    assert {"backend", "internal", "server"}.issubset(keywords.path_tokens)


def test_embed_query_uses_embedding_adapter(monkeypatch) -> None:
    monkeypatch.setattr(service, "_embed_texts", lambda texts: [[0.1, 0.2, 0.3]])

    assert embed_query("recommendations disappear after refresh") == [0.1, 0.2, 0.3]


def test_embed_chunks_returns_schema_embeddings(monkeypatch) -> None:
    monkeypatch.setattr(service, "_embed_texts", lambda texts: [[1.0, 0.0]])

    embeddings = embed_chunks([make_chunk()])

    assert len(embeddings) == 1
    assert embeddings[0].chunk_id == "chunk-1"
    assert embeddings[0].embedding_model == DEFAULT_EMBEDDING_MODEL
    assert embeddings[0].vector == [1.0, 0.0]
