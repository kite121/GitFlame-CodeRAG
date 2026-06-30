from gitflame_coderag.retrieval.bm25 import (
    BM25Index,
    bm25_search,
    build_bm25_index,
    build_bm25_query,
    build_bm25_text,
    rank_bm25_results,
    tokenize_for_bm25,
)
from gitflame_coderag.schemas import (
    AIConfig,
    CodeChunk,
    Issue,
    RetrievalResult,
    StructuralMetadata,
)


def make_chunk(chunk_id: str, path: str, content: str, **kwargs: object) -> CodeChunk:
    defaults = dict(
        id=chunk_id,
        repository_id="repo",
        file_id=f"repo:rev:{path}",
        path=path,
        language="python",
        chunk_type="ast",
        start_line=1,
        end_line=max(1, content.count("\n") + 1),
        content=content,
        content_hash="hash",
    )
    defaults.update(kwargs)
    return CodeChunk(**defaults)


def test_tokenize_splits_snake_and_camel_case_and_keeps_original() -> None:
    tokens = tokenize_for_bm25("handleAnalyzeIssue user_id")
    # camelCase original is preserved alongside its sub-words
    assert "handleanalyzeissue" in tokens
    assert {"handle", "analyze", "issue"} <= set(tokens)
    # snake_case is split and the original is kept
    assert {"user_id", "user", "id"} <= set(tokens)


def test_tokenize_lowercases_drops_stopwords_and_short_tokens_but_keeps_digits() -> None:
    tokens = tokenize_for_bm25("The server returns 500 if x is bad")
    assert "the" not in tokens and "is" not in tokens and "if" not in tokens
    assert "x" not in tokens  # single-character token dropped
    assert "500" in tokens  # status codes preserved
    assert "server" in tokens and "returns" in tokens


def test_build_bm25_text_includes_metadata_and_preserves_raw_content() -> None:
    chunk = make_chunk(
        "c1",
        "src/auth/tokens.py",
        "def refresh():\n    return None\n",
        node_type="function_definition",
        symbol_name="refresh",
    )
    metadata = StructuralMetadata(
        chunk_id="c1",
        imports=["jwt"],
        calls=["decode_token"],
    )

    text = build_bm25_text(chunk, metadata)

    assert "src/auth/tokens.py" in text
    assert "python" in text
    assert "refresh" in text
    assert "jwt" in text
    assert "decode_token" in text
    # raw content is embedded verbatim and never mutated
    assert chunk.content in text
    assert chunk.content == "def refresh():\n    return None\n"


def test_bm25_search_ranks_relevant_chunk_first() -> None:
    chunks = [
        make_chunk(
            "auth",
            "src/auth/tokens.py",
            "def refresh_token(jwt):\n    return decode_token(jwt)\n",
            symbol_name="refresh_token",
        ),
        make_chunk(
            "math",
            "src/utils/math.py",
            "def add(a, b):\n    return a + b\n",
            symbol_name="add",
        ),
    ]
    index = build_bm25_index(chunks)

    results = bm25_search("refresh token decode", index, top_k=2)

    assert [r.chunk_id for r in results] == ["auth", "math"]
    assert results[0].rank == 1 and results[1].rank == 2
    assert results[0].source == "bm25"
    assert results[0].bm25_score == results[0].score
    assert results[0].score > results[1].score


def test_symbol_name_match_outranks_incidental_body_match() -> None:
    # Both chunks mention "refresh" the same number of times in their body, but only `named`
    # has it as the function's name (a boosted high-signal field).
    incidental = make_chunk(
        "incidental",
        "src/handlers.py",
        "def handle():\n    return refresh()\n",
        symbol_name="handle",
    )
    named = make_chunk(
        "named",
        "src/auth.py",
        "def refresh():\n    return compute()\n",
        symbol_name="refresh",
    )
    index = build_bm25_index([incidental, named])

    results = bm25_search("refresh", index, top_k=2)

    assert results[0].chunk_id == "named"
    assert results[0].score > results[1].score


def test_file_name_match_is_boosted() -> None:
    # "tokens" appears only in the file name of the first chunk, nowhere in either body.
    on_path = make_chunk("on_path", "src/auth/tokens.py", "def f():\n    return 1\n")
    other = make_chunk("other", "src/auth/views.py", "def g():\n    return 2\n")
    index = build_bm25_index([on_path, other])

    results = bm25_search("tokens", index, top_k=2)

    assert results[0].chunk_id == "on_path"
    assert results[0].score > 0


def test_bm25_search_uses_structural_metadata_when_provided() -> None:
    chunk = make_chunk("c1", "src/app.py", "def run():\n    pass\n", symbol_name="run")
    metadata = {"c1": StructuralMetadata(chunk_id="c1", calls=["dispatch_webhook"])}
    index = build_bm25_index([chunk], metadata)

    results = bm25_search("dispatch_webhook", index, top_k=1)

    assert results and results[0].chunk_id == "c1"
    assert results[0].score > 0


def test_bm25_search_handles_empty_index_and_empty_query() -> None:
    empty_index = build_bm25_index([])
    assert isinstance(empty_index, BM25Index)
    assert empty_index.bm25 is None
    assert bm25_search("anything", empty_index, top_k=5) == []

    index = build_bm25_index([make_chunk("c1", "a.py", "def f():\n    pass\n")])
    # a query of only stop-words / short tokens yields no usable terms
    assert bm25_search("a the is", index, top_k=5) == []


def test_build_bm25_query_combines_issue_fields_and_collapses_whitespace() -> None:
    issue = Issue(
        id="repo_issue_1",
        repository_id="repo",
        title="Refresh   token fails",
        body="When the token\nis expired the call breaks",
        labels=["auth", "bug"],
    )

    query = build_bm25_query(issue, AIConfig())

    # title + body + labels are combined and whitespace is collapsed
    assert query == "Refresh token fails When the token is expired the call breaks auth bug"
    # the resulting string still tokenizes to the meaningful query terms
    assert {"refresh", "token", "expired", "auth", "bug"} <= set(tokenize_for_bm25(query))


def test_build_bm25_query_end_to_end_with_search() -> None:
    issue = Issue(
        id="repo_issue_2",
        repository_id="repo",
        title="refresh token decode",
        body="",
        labels=[],
    )
    chunks = [
        make_chunk("auth", "src/auth.py", "def refresh_token(jwt):\n    return decode(jwt)\n",
                   symbol_name="refresh_token"),
        make_chunk("math", "src/math.py", "def add(a, b):\n    return a + b\n", symbol_name="add"),
    ]
    index = build_bm25_index(chunks)

    results = bm25_search(build_bm25_query(issue, AIConfig()), index, top_k=2)

    assert results[0].chunk_id == "auth"


def test_rank_bm25_results_orders_by_score_then_chunk_id() -> None:
    results = [
        RetrievalResult(chunk_id="b", rank=1, score=1.0, source="bm25"),
        RetrievalResult(chunk_id="a", rank=2, score=5.0, source="bm25"),
        RetrievalResult(chunk_id="c", rank=3, score=5.0, source="bm25"),
    ]
    ranked = rank_bm25_results(results)
    assert [r.chunk_id for r in ranked] == ["a", "c", "b"]
