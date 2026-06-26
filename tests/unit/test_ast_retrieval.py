from gitflame_coderag.retrieval.ast import (
    ast_candidate_search,
    build_ast_search_terms,
    normalize_query_terms,
    normalize_symbol_term,
    score_ast_chunk,
    score_term_matches,
)
from gitflame_coderag.schemas import CodeChunk, StructuralMetadata


def make_chunk(
    chunk_id: str,
    path: str,
    symbol_name: str | None,
    start_line: int = 1,
) -> CodeChunk:
    return CodeChunk(
        id=chunk_id,
        repository_id="repo",
        file_id="file",
        path=path,
        language="python",
        chunk_type="ast",
        node_type="function_definition",
        symbol_name=symbol_name,
        start_line=start_line,
        end_line=start_line + 4,
        content=f"def {symbol_name or 'unknown'}(): pass",
        content_hash=f"hash-{chunk_id}",
    )


def test_ast_candidate_search_prioritizes_symbol_matches() -> None:
    chunks = [
        make_chunk("chunk_create_user", "services/user_service.py", "create_user"),
        make_chunk("chunk_email_ref", "services/profile.py", "update_profile", start_line=10),
    ]
    metadata_by_chunk_id = {
        "chunk_create_user": StructuralMetadata(
            chunk_id="chunk_create_user",
            defined_symbols=["create_user"],
            referenced_symbols=["email"],
        ),
        "chunk_email_ref": StructuralMetadata(
            chunk_id="chunk_email_ref",
            referenced_symbols=["email"],
        ),
    }

    results = ast_candidate_search(
        query_keywords=["create", "user", "email"],
        chunks=chunks,
        metadata_by_chunk_id=metadata_by_chunk_id,
        top_k=2,
    )

    assert [result.chunk_id for result in results] == [
        "chunk_create_user",
        "chunk_email_ref",
    ]
    assert results[0].source == "ast"
    assert results[0].ast_score == results[0].score


def test_normalize_symbol_term_splits_common_code_names() -> None:
    assert normalize_symbol_term("UserService") == ["userservice", "user", "service"]
    assert normalize_symbol_term("create_user") == ["createuser", "create", "user"]
    assert normalize_symbol_term("email-validation") == [
        "emailvalidation",
        "email",
        "validation",
    ]


def test_normalize_query_terms_removes_duplicates() -> None:
    assert normalize_query_terms(["UserService", "user_service", None]) == {
        "userservice",
        "user",
        "service",
    }


def test_score_ast_chunk_uses_field_weights() -> None:
    chunk = make_chunk("chunk_create_user", "services/user_service.py", "create_user")
    metadata = StructuralMetadata(
        chunk_id="chunk_create_user",
        defined_symbols=["create_user"],
        calls=["validate_email"],
        referenced_symbols=["email"],
    )

    score = score_ast_chunk(
        query_terms={"create", "user", "validate", "email"},
        chunk=chunk,
        metadata=metadata,
    )

    assert score == 26.0


def test_build_ast_search_terms_collects_chunk_and_metadata_terms() -> None:
    chunk = make_chunk("chunk_create_user", "services/user_service.py", "create_user")
    metadata = StructuralMetadata(
        chunk_id="chunk_create_user",
        calls=["validate_email"],
        referenced_symbols=["email"],
    )

    terms = build_ast_search_terms(chunk, metadata)

    assert {"createuser", "create", "user"}.issubset(terms["symbol_name"])
    assert {"services", "user", "service", "py"}.issubset(terms["path"])
    assert {"validateemail", "validate", "email"}.issubset(terms["calls"])
    assert "email" in terms["referenced_symbols"]


def test_score_term_matches_scores_each_field_once_per_matched_term() -> None:
    score = score_term_matches(
        query_terms={"create", "user", "email"},
        weighted_terms={
            "symbol_name": {"create", "user"},
            "referenced_symbols": {"email"},
        },
    )

    assert score == 11.0


def test_ast_candidate_search_respects_top_k_and_reranks_results() -> None:
    chunks = [
        make_chunk("chunk_low", "services/profile.py", "update_profile", start_line=20),
        make_chunk("chunk_high", "services/user_service.py", "create_user", start_line=1),
        make_chunk("chunk_mid", "services/email.py", "validate_email", start_line=10),
    ]
    metadata_by_chunk_id = {
        "chunk_low": StructuralMetadata(
            chunk_id="chunk_low",
            referenced_symbols=["email"],
        ),
        "chunk_high": StructuralMetadata(
            chunk_id="chunk_high",
            defined_symbols=["create_user"],
            referenced_symbols=["email"],
        ),
        "chunk_mid": StructuralMetadata(
            chunk_id="chunk_mid",
            defined_symbols=["validate_email"],
        ),
    }

    results = ast_candidate_search(
        query_keywords=["create", "user", "email"],
        chunks=chunks,
        metadata_by_chunk_id=metadata_by_chunk_id,
        top_k=2,
    )

    assert [result.chunk_id for result in results] == ["chunk_high", "chunk_mid"]
    assert [result.rank for result in results] == [1, 2]


def test_ast_candidate_search_returns_empty_when_nothing_matches() -> None:
    results = ast_candidate_search(
        query_keywords=["payment"],
        chunks=[make_chunk("chunk_user", "services/user_service.py", "create_user")],
        metadata_by_chunk_id={},
        top_k=5,
    )

    assert results == []
