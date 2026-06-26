import fnmatch
import hashlib
from pathlib import Path

from gitflame_coderag.schemas import AIConfig, FileMetadata, RepositoryFile

LANGUAGES_BY_EXTENSION = {
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".php": "php",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
}

CONFIG_NAMES = {"dockerfile", "makefile", "pyproject.toml", "package.json"}
DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt"}


def detect_language(path: Path, content: str) -> str:
    del content  # Reserved for future shebang/content detection.
    return LANGUAGES_BY_EXTENSION.get(path.suffix.lower(), "unknown")


def build_file_metadata(
    path: Path,
    content: str,
    repository_id: str,
    revision: str,
    *,
    relative_path: str | None = None,
) -> FileMetadata:
    repo_path = (relative_path or path.as_posix()).replace("\\", "/")
    lowered = repo_path.lower()
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    file_id = f"{repository_id}:{revision}:{repo_path}"
    return FileMetadata(
        id=file_id,
        repository_id=repository_id,
        revision=revision,
        path=repo_path,
        extension=path.suffix.lower(),
        language=detect_language(path, content),
        size_bytes=len(content.encode("utf-8")),
        line_count=len(content.splitlines()),
        content_hash=digest,
        is_test="test" in path.stem.lower() or "/tests/" in f"/{lowered}/",
        is_config=path.name.lower() in CONFIG_NAMES
        or path.suffix.lower() in {".yml", ".yaml", ".toml"},
        is_docs=path.suffix.lower() in DOC_EXTENSIONS or "/docs/" in f"/{lowered}/",
    )


def load_repository_files(
    repo_path: Path,
    repository_id: str,
    revision: str,
) -> list[RepositoryFile]:
    files: list[RepositoryFile] = []
    for path in sorted(item for item in repo_path.rglob("*") if item.is_file()):
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
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
    selected = []
    for file in files:
        path = file.metadata.path
        included = any(_matches(path, pattern) for pattern in config.include)
        excluded = any(_matches(path, pattern) for pattern in config.exclude)
        if included and not excluded:
            selected.append(file)
    return selected


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])
    )
