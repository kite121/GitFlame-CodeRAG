"""Repository ingestion: file loading, language detection, filtering, metadata.

Owner: Kirill (see ``data_contracts.md``). All functions match the contracts in
``data_contracts.md`` and exchange the shared schemas from ``schemas.py``.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from gitflame_coderag.schemas import AIConfig, FileMetadata, RepositoryFile

LANGUAGES_BY_EXTENSION = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".h": "c",
    ".hpp": "cpp",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".mjs": "javascript",
    ".php": "php",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".sh": "shell",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
}

# Files identified by name rather than extension.
LANGUAGES_BY_FILENAME = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}

# Map common shebang interpreters to languages for extension-less scripts.
SHEBANG_LANGUAGES = {
    "python": "python",
    "python3": "python",
    "node": "javascript",
    "bash": "shell",
    "sh": "shell",
    "ruby": "ruby",
}

CONFIG_NAMES = {"dockerfile", "makefile", "pyproject.toml", "package.json"}
CONFIG_EXTENSIONS = {".yml", ".yaml", ".toml", ".ini", ".cfg"}
DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt"}

_TEST_NAME = re.compile(r"(^|[._-])(test|tests|spec)([._-]|$)")


def detect_language(path: Path, content: str) -> str:
    """Best-effort language detection from extension, filename, then shebang."""
    name = path.name.lower()
    if name in LANGUAGES_BY_FILENAME:
        return LANGUAGES_BY_FILENAME[name]

    language = LANGUAGES_BY_EXTENSION.get(path.suffix.lower())
    if language is not None:
        return language

    # Extension-less or unknown extension: inspect a shebang line.
    if content.startswith("#!"):
        first_line = content.splitlines()[0]
        interpreter = first_line.rsplit("/", 1)[-1].split()
        # Handle "/usr/bin/env python3" by taking the last meaningful token.
        token = interpreter[-1] if interpreter else ""
        if token in SHEBANG_LANGUAGES:
            return SHEBANG_LANGUAGES[token]

    return "unknown"


def build_file_metadata(
    path: Path,
    content: str,
    repository_id: str,
    revision: str,
    *,
    relative_path: str | None = None,
) -> FileMetadata:
    """Build :class:`FileMetadata` for a single file.

    ``relative_path`` (repository-relative, ``/``-separated) is preferred for the
    stored path; otherwise ``path`` is used. Raw content is never normalized.
    """
    repo_path = (relative_path or path.as_posix()).replace("\\", "/")
    lowered = repo_path.lower()
    encoded = content.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    file_id = f"{repository_id}:{revision}:{repo_path}"
    suffix = path.suffix.lower()
    name = path.name.lower()
    return FileMetadata(
        id=file_id,
        repository_id=repository_id,
        revision=revision,
        path=repo_path,
        extension=suffix,
        language=detect_language(path, content),
        size_bytes=len(encoded),
        line_count=len(content.splitlines()),
        content_hash=digest,
        is_test=bool(_TEST_NAME.search(path.stem.lower())) or "/test" in f"/{lowered}",
        is_config=name in CONFIG_NAMES or suffix in CONFIG_EXTENSIONS,
        is_docs=suffix in DOC_EXTENSIONS or "/docs/" in f"/{lowered}/",
    )


def load_repository_files(
    repo_path: Path,
    repository_id: str,
    revision: str,
) -> list[RepositoryFile]:
    """Load every readable text file under ``repo_path`` as a RepositoryFile.

    Binary files and unreadable paths are skipped. Paths are stored
    repository-relative with ``/`` separators. ``.git`` is always skipped.
    """
    repo_path = Path(repo_path)
    files: list[RepositoryFile] = []
    for path in sorted(item for item in repo_path.rglob("*") if item.is_file()):
        if ".git" in path.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # Binary or unreadable file.
        relative_path = path.relative_to(repo_path).as_posix()
        metadata = build_file_metadata(
            path,
            content,
            repository_id,
            revision,
            relative_path=relative_path,
        )
        files.append(RepositoryFile(metadata=metadata, raw_content=content))
    return files


def filter_files_by_config(
    files: list[RepositoryFile],
    config: AIConfig,
) -> list[RepositoryFile]:
    """Keep files matching any include pattern and no exclude pattern."""
    include = config.include or ["**/*"]
    exclude = config.exclude or []
    selected: list[RepositoryFile] = []
    for file in files:
        path = file.metadata.path
        if any(_matches(path, pattern) for pattern in include) and not any(
            _matches(path, pattern) for pattern in exclude
        ):
            selected.append(file)
    return selected


@lru_cache(maxsize=512)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    """Compile a gitignore-style glob into a regex.

    ``**`` crosses directory separators, ``*`` and ``?`` do not. ``**/`` matches
    zero or more leading directories.
    """
    i, n = 0, len(pattern)
    out = ["^"]
    while i < n:
        char = pattern[i]
        if char == "*":
            if pattern[i : i + 2] == "**":
                if pattern[i : i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def _matches(path: str, pattern: str) -> bool:
    """Return True if a repository-relative path matches a glob pattern.

    Patterns without a ``/`` also match against the file's basename so that
    rules like ``*.lock`` apply at any directory depth.
    """
    compiled = _compile_glob(pattern)
    if compiled.match(path):
        return True
    if "/" not in pattern:
        return bool(compiled.match(path.rsplit("/", 1)[-1]))
    return False
