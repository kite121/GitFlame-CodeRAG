"""Tests for repository ingestion (Kirill's Sprint 1 functions)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitflame_coderag.config.loader import load_ai_config, parse_ai_config
from gitflame_coderag.ingestion.files import (
    _matches,
    build_file_metadata,
    detect_language,
    filter_files_by_config,
    load_repository_files,
)
from gitflame_coderag.ingestion.issues import load_issues
from gitflame_coderag.schemas import AIConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPO_ROOT / "datasets" / "repositories"


# --------------------------------------------------------------------------- #
# detect_language
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        ("main.py", "x = 1", "python"),
        ("server.go", "package main", "go"),
        ("app.tsx", "export const A = 1", "typescript"),
        ("index.js", "const a = 1", "javascript"),
        ("lib.rs", "fn main() {}", "rust"),
        ("Dockerfile", "FROM python", "dockerfile"),
        ("Makefile", "all:", "makefile"),
        ("script", "#!/usr/bin/env python3\nprint(1)", "python"),
        ("run", "#!/bin/bash\necho hi", "shell"),
        ("data.bin", "garbage", "unknown"),
    ],
)
def test_detect_language(name: str, content: str, expected: str) -> None:
    assert detect_language(Path(name), content) == expected


# --------------------------------------------------------------------------- #
# build_file_metadata
# --------------------------------------------------------------------------- #
def test_build_file_metadata_core_fields() -> None:
    content = "line1\nline2\n"
    meta = build_file_metadata(
        Path("app/main.py"),
        content,
        repository_id="repo_x",
        revision="rev1",
        relative_path="app/main.py",
    )
    assert meta.path == "app/main.py"
    assert meta.extension == ".py"
    assert meta.language == "python"
    assert meta.line_count == 2
    assert meta.size_bytes == len(content.encode("utf-8"))
    assert meta.id == "repo_x:rev1:app/main.py"
    assert len(meta.content_hash) == 64  # sha256 hex


def test_build_file_metadata_classifications() -> None:
    test_meta = build_file_metadata(
        Path("tests/test_posts.py"), "", "r", "v", relative_path="tests/test_posts.py"
    )
    assert test_meta.is_test is True

    cfg_meta = build_file_metadata(Path("repo.yml"), "", "r", "v", relative_path="repo.yml")
    assert cfg_meta.is_config is True

    doc_meta = build_file_metadata(Path("README.md"), "", "r", "v", relative_path="README.md")
    assert doc_meta.is_docs is True

    # "latest.py" must not be misread as a test file.
    normal = build_file_metadata(Path("latest.py"), "", "r", "v", relative_path="latest.py")
    assert normal.is_test is False


# --------------------------------------------------------------------------- #
# glob matching / filter_files_by_config
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("app/main.py", "app/**", True),
        ("app/api/posts.py", "app/**", True),
        ("app", "app/**", False),
        ("src/auth/routes.py", "src/**", True),
        ("app/main.py", "app/*.py", True),
        ("app/api/posts.py", "app/*.py", False),  # * does not cross '/'
        ("node_modules/react/index.js", "node_modules/**", True),
        ("a/b/c.lock", "*.lock", True),  # no-slash pattern matches basename
        ("anything/here.py", "**/*", True),
    ],
)
def test_matches(path: str, pattern: str, expected: bool) -> None:
    assert _matches(path, pattern) is expected


def test_filter_files_by_config_include_exclude() -> None:
    files = load_repository_files(
        _write_tree(
            {
                "app/main.py": "x = 1\n",
                "app/util.py": "y = 2\n",
                "node_modules/dep/index.js": "z\n",
                "dist/bundle.js": "b\n",
            }
        ),
        "repo_f",
        "rev",
    )
    config = AIConfig(include=["app/**"], exclude=["node_modules/**", "dist/**"])
    kept = {f.metadata.path for f in filter_files_by_config(files, config)}
    assert kept == {"app/main.py", "app/util.py"}


# --------------------------------------------------------------------------- #
# load_repository_files
# --------------------------------------------------------------------------- #
def _write_tree(tree: dict[str, str], base: Path | None = None) -> Path:
    base = base or Path(_tmpdir())
    for rel, content in tree.items():
        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return base


_TMP_COUNTER = {"n": 0}


def _tmpdir() -> str:
    import tempfile

    return tempfile.mkdtemp(prefix="coderag_test_")


def test_load_repository_files_reads_and_relativizes() -> None:
    root = _write_tree({"pkg/a.py": "a = 1\n", "pkg/sub/b.py": "b = 2\n"})
    files = load_repository_files(root, "repo_l", "rev")
    paths = sorted(f.metadata.path for f in files)
    assert paths == ["pkg/a.py", "pkg/sub/b.py"]
    assert all(f.raw_content for f in files)


def test_load_repository_files_skips_binary(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text("ok = 1\n", encoding="utf-8")
    (tmp_path / "bad.bin").write_bytes(b"\xff\xfe\x00\x01")
    files = load_repository_files(tmp_path, "repo_b", "rev")
    assert [f.metadata.path for f in files] == ["good.py"]


# --------------------------------------------------------------------------- #
# load_issues
# --------------------------------------------------------------------------- #
def test_load_issues_parses_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "issues.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "i1",
                        "title": "Bug",
                        "body": "boom",
                        "labels": ["bug"],
                        "expected_files": ["app/main.py"],
                    }
                ),
                "",  # blank line tolerated
                json.dumps({"id": "i2", "title": "Feature", "labels": [], "expected_files": []}),
            ]
        ),
        encoding="utf-8",
    )
    issues = load_issues(path, repository_id="repo_i")
    assert [i.id for i in issues] == ["i1", "i2"]
    assert all(i.repository_id == "repo_i" for i in issues)
    assert issues[0].expected_files == ["app/main.py"]


# --------------------------------------------------------------------------- #
# Generated dataset integrity (Kirill's deliverable)
# --------------------------------------------------------------------------- #
def _repo_dirs() -> list[Path]:
    if not DATASET_ROOT.exists():
        return []
    return sorted(p for p in DATASET_ROOT.iterdir() if p.is_dir() and (p / "repo.yml").exists())


def test_dataset_has_10_to_15_repositories() -> None:
    repos = _repo_dirs()
    assert 10 <= len(repos) <= 15, f"expected 10-15 repos, found {len(repos)}"


@pytest.mark.parametrize("repo_dir", _repo_dirs(), ids=lambda p: p.name)
def test_each_repository_is_well_formed(repo_dir: Path) -> None:
    assert (repo_dir / "repo.yml").exists()
    assert (repo_dir / "code").is_dir()
    assert (repo_dir / "issues.jsonl").exists()

    config = parse_ai_config(load_ai_config(repo_dir / "repo.yml"))
    files = load_repository_files(repo_dir / "code", repo_dir.name, "local")
    assert files, "repository has no code files"

    selected = filter_files_by_config(files, config)
    selected_paths = {f.metadata.path for f in selected}
    assert selected_paths, "config filtered out every file"

    issues = load_issues(repo_dir / "issues.jsonl", repo_dir.name)
    assert len(issues) == 7, f"{repo_dir.name} must have exactly 7 issues"

    # Every expected_file must exist in code/ and survive config filtering.
    all_paths = {f.metadata.path for f in files}
    for issue in issues:
        for expected in issue.expected_files:
            assert expected in all_paths, f"{issue.id}: missing file {expected}"
            assert expected in selected_paths, f"{issue.id}: {expected} excluded by config"
