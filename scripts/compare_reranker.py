"""Reproducible RRF vs RRF+reranker comparison on a dataset repository.

Owner: Zhenya. Builds an in-memory retrieval stack (BM25 + AST -> RRF) without a
database or embeddings, applies the cross-encoder reranker, and reports Recall@k /
MRR for RRF-only vs RRF + reranker across every issue in the repository.

Usage:
    uv run python scripts/compare_reranker.py datasets/repositories/repo_001_fastapi_blog
    uv run python scripts/compare_reranker.py <repo_dir> --json out.json

When the reranker model cannot be loaded (offline), the comparison still runs and
reports the fallback (reranker order == RRF order).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gitflame_coderag.chunking.pipeline import build_chunks
from gitflame_coderag.config.loader import load_ai_config, parse_ai_config
from gitflame_coderag.ingestion import (
    filter_files_by_config,
    load_issues,
    load_repository_files,
)
from gitflame_coderag.pipelines.retrieve_issue import build_issue_query
from gitflame_coderag.retrieval.ast import ast_candidate_search
from gitflame_coderag.retrieval.bm25 import (
    BM25Index,
    bm25_search,
    build_bm25_index,
    build_bm25_query,
    tokenize_for_bm25,
)
from gitflame_coderag.retrieval.reranker import (
    RerankerCase,
    compare_rrf_vs_reranker,
    rerank_candidates,
)
from gitflame_coderag.retrieval.rrf import rrf_fusion
from gitflame_coderag.schemas import AIConfig, CodeChunk, Issue, RetrievalResult


def build_rrf_candidates(
    issue: Issue,
    chunks: list[CodeChunk],
    bm25_index: BM25Index,
    config: AIConfig,
    *,
    bm25_top_k: int,
    ast_top_k: int,
    rrf_k: int,
    pool: int,
) -> list[RetrievalResult]:
    """Fuse BM25 and AST candidate rankings into an RRF pool for one issue."""
    query = build_bm25_query(issue, config)
    bm25_results = bm25_search(query, bm25_index, bm25_top_k)
    keywords = tokenize_for_bm25(query)
    # Empty structural metadata: AST still scores on path / symbol / node_type / language.
    ast_results = ast_candidate_search(keywords, chunks, {}, ast_top_k)
    return rrf_fusion([bm25_results, ast_results], top_k=pool, rrf_k=rrf_k)


def _print_report(report: dict[str, Any], repository_id: str, num_chunks: int) -> None:
    print(
        f"Repository: {repository_id}  "
        f"(chunks={num_chunks}, issues={report['num_cases']})"
    )
    print(f"Reranker model: {report['model']}  available={report['reranker_available']}")
    if not report["reranker_available"]:
        print("NOTE: reranker model unavailable -> reranker order == RRF order (fallback).")

    header = f"{'metric':<12}{'RRF':>10}{'RRF+RR':>10}{'delta':>10}"
    print(header)
    print("-" * len(header))
    for name in report["rrf"]:
        print(
            f"{name:<12}{report['rrf'][name]:>10.4f}"
            f"{report['reranker'][name]:>10.4f}{report['delta'][name]:>+10.4f}"
        )


def _print_final_evidence(case: RerankerCase, *, model_name: str, device: str, top_k: int) -> None:
    """Show the final reranked top-k evidence for one issue (end-to-end demo)."""
    final = rerank_candidates(
        case.query,
        case.rrf_candidates,
        case.chunks_by_id,
        top_k=top_k,
        model_name=model_name,
        device=device,
    )
    print(f"\nFinal reranked top-{top_k} evidence for first issue:")
    for result in final:
        chunk = case.chunks_by_id.get(result.chunk_id)
        path = chunk.path if chunk else result.chunk_id
        print(f"  #{result.rank}  score={result.score:.4f}  {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_dir",
        type=Path,
        help="Dataset repository dir containing code/, repo.yml, issues.jsonl",
    )
    parser.add_argument("--repository-id", default=None)
    parser.add_argument("--revision", default="local")
    parser.add_argument("--model", default=None, help="Override reranker model name")
    parser.add_argument("--device", default=None, help="Override reranker device")
    parser.add_argument("--bm25-top-k", type=int, default=50)
    parser.add_argument("--ast-top-k", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--reranker-top-k", type=int, default=None, help="RRF pool size")
    parser.add_argument("--final-top-k", type=int, default=None)
    parser.add_argument("--k-values", type=int, nargs="+", default=[1, 3, 5, 10])
    parser.add_argument("--json", default=None, help="Optional path to save the JSON report")
    args = parser.parse_args()

    repo_dir: Path = args.repo_dir
    repository_id = args.repository_id or repo_dir.name
    config = parse_ai_config(load_ai_config(repo_dir / "repo.yml"))
    rr = config.reranker
    model_name = args.model or rr.model
    device = args.device or rr.device
    pool = args.reranker_top_k or rr.reranker_top_k
    final_top_k = args.final_top_k or rr.final_top_k

    files = load_repository_files(repo_dir / "code", repository_id, args.revision)
    selected = filter_files_by_config(files, config)
    chunks = build_chunks(selected, config)
    chunks_by_id = {chunk.id: chunk for chunk in chunks}
    bm25_index = build_bm25_index(chunks)
    issues = load_issues(repo_dir / "issues.jsonl", repository_id)

    cases = [
        RerankerCase(
            query=build_issue_query(issue),
            rrf_candidates=build_rrf_candidates(
                issue,
                chunks,
                bm25_index,
                config,
                bm25_top_k=args.bm25_top_k,
                ast_top_k=args.ast_top_k,
                rrf_k=args.rrf_k,
                pool=pool,
            ),
            chunks_by_id=chunks_by_id,
            gold_paths=set(issue.expected_files),
        )
        for issue in issues
    ]

    report = compare_rrf_vs_reranker(
        cases,
        model_name=model_name,
        device=device,
        k_values=tuple(args.k_values),
    )
    _print_report(report, repository_id, len(chunks))
    if cases:
        _print_final_evidence(cases[0], model_name=model_name, device=device, top_k=final_top_k)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report to {args.json}")


if __name__ == "__main__":
    main()
