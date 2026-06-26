"""AST-Grep based code chunking.

This module turns one source file into AST-aware ``CodeChunk`` objects
"""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Iterable

from gitflame_coderag.chunking.config import (
    CALL_EXCLUDED_KEYWORDS,
    CHUNK_NODE_KINDS,
    DEFINITION_KINDS,
    IMPORT_PATTERNS,
    LANGUAGE_ALIASES,
    SYMBOL_EXCLUDED_KEYWORDS,
)
from gitflame_coderag.chunking.datamodels import AstMatch
from gitflame_coderag.schemas import (
    AIConfig,
    ChunkingConfig,
    CodeChunk,
    RepositoryFile,
    StructuralMetadata,
)


def chunk_file_with_ast_grep(
    file: RepositoryFile,
    config: AIConfig | ChunkingConfig,
) -> list[CodeChunk]:
    """Create AST-aware chunks for one repository file.

    Returns an empty list when AST-Grep cannot parse the language or the
    dependency is missing. The caller can then use fallback chunking.
    """

    chunking_config = get_chunking_config(config)
    language = normalize_language(file.metadata.language)
    rules = build_ast_grep_rules(language)
    if not rules or not file.raw_content.strip():
        return []

    matches = run_ast_grep_scan(
        content=file.raw_content,
        language=language,
        rules=rules,
    )
    chunks = parse_ast_grep_matches(
        matches=matches,
        file=file,
    )
    chunks = deduplicate_ast_chunks(chunks)

    final_chunks: list[CodeChunk] = []
    for chunk in chunks:
        final_chunks.extend(split_large_ast_chunk(chunk, chunking_config))

    return final_chunks


def get_chunking_config(config: AIConfig | ChunkingConfig) -> ChunkingConfig:
    """Accept either the full AIConfig or the nested ChunkingConfig."""

    return config.chunking if isinstance(config, AIConfig) else config


def normalize_language(language: str) -> str:
    """Convert repo language names/extensions to AST-Grep parser names."""

    return LANGUAGE_ALIASES.get(language.strip().lower(), language.strip().lower())


def build_ast_grep_rules(language: str) -> list[str]:
    """Return AST node kinds that should become evidence chunks."""

    return CHUNK_NODE_KINDS.get(normalize_language(language), [])


def run_ast_grep_scan(
    content: str,
    language: str,
    rules: list[str],
) -> list[AstMatch]:
    """Parse code with AST-Grep and return normalized matches."""

    try:
        from ast_grep_py import SgRoot
    except ImportError:
        return []

    parser_language = normalize_language(language)
    try:
        root = SgRoot(content, parser_language).root()
    except Exception:
        return []

    matches: list[AstMatch] = []
    for node_type in rules:
        try:
            nodes = root.find_all(kind=node_type)
        except Exception:
            continue

        for node in nodes:
            match = build_ast_match(node=node, node_type=node_type)
            if match is not None:
                matches.append(match)

    return sorted(matches, key=lambda match: (match.start_line, match.end_line))


def build_ast_match(node: Any, node_type: str | None = None) -> AstMatch | None:
    """Normalize one AST-Grep node into AstMatch."""

    content = safe_node_text(node).strip("\n")
    if not content.strip():
        return None

    start_line, end_line = extract_node_line_range(node)
    if start_line is None or end_line is None:
        return None

    start_line, end_line = normalize_line_range(start_line, end_line)
    kind = node_type or safe_node_kind(node)

    return AstMatch(
        node=node,
        node_type=kind,
        symbol_name=extract_symbol_name(node),
        parent_symbol=extract_parent_symbol(node),
        start_line=start_line,
        end_line=end_line,
        content=content,
    )


def parse_ast_grep_matches(
    matches: list[AstMatch],
    file: RepositoryFile,
) -> list[CodeChunk]:
    """Convert AST-Grep matches into shared CodeChunk contracts."""

    chunks: list[CodeChunk] = []
    for match in matches:
        start_line, end_line = normalize_line_range(match.start_line, match.end_line)
        if not is_line_range_within_file(start_line, end_line, file.metadata.line_count):
            continue

        content = match.content.strip("\n")
        if not content.strip():
            continue

        chunks.append(
            CodeChunk(
                id=make_ast_chunk_id(
                    file_id=file.metadata.id,
                    start_line=start_line,
                    end_line=end_line,
                    node_type=match.node_type,
                    content=content,
                ),
                repository_id=file.metadata.repository_id,
                file_id=file.metadata.id,
                path=file.metadata.path,
                language=file.metadata.language,
                chunk_type="ast",
                node_type=match.node_type,
                symbol_name=match.symbol_name,
                parent_symbol=match.parent_symbol,
                start_line=start_line,
                end_line=end_line,
                content=content,
                content_hash=hash_chunk_content(content),
                token_count=estimate_token_count(content),
            )
        )

    return chunks


def extract_structural_metadata(
    chunk: CodeChunk,
    raw_content: str | None = None,
) -> StructuralMetadata:
    """Extract lightweight structural metadata from a chunk."""

    content = raw_content if raw_content is not None else chunk.content
    defined_symbols = [chunk.symbol_name] if chunk.symbol_name else []

    flags = {
        "is_class": bool(chunk.node_type and "class" in chunk.node_type),
        "is_function": bool(
            chunk.node_type
            and ("function" in chunk.node_type or "method" in chunk.node_type)
        ),
        "is_test": bool(re.search(r"(^|[_\W])(test|spec)([_\W]|$)", chunk.path.lower())),
        "has_async": bool(re.search(r"\basync\b", content)),
        "has_error_handling": bool(
            re.search(r"\b(try|except|catch|finally|raise|throw)\b", content)
        ),
    }

    return StructuralMetadata(
        chunk_id=chunk.id,
        imports=sorted(set(extract_imports(content, chunk.language))),
        calls=sorted(set(extract_calls(content))),
        defined_symbols=sorted(set(defined_symbols)),
        referenced_symbols=sorted(set(extract_referenced_symbols(content))),
        flags=flags,
    )


def extract_symbol_name(node: Any) -> str | None:
    """Best-effort symbol name extraction for common AST node shapes."""

    for field_name in ("name", "property", "field", "declarator"):
        field_node = safe_node_field(node, field_name)
        if field_node is not None:
            text = safe_node_text(field_node).strip()
            if field_name == "declarator":
                match = re.search(r"\b(?:[A-Za-z_][A-Za-z0-9_]*::)*([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
                if match:
                    return match.group(1)
            elif text:
                return text

    text = safe_node_text(node)
    for pattern in symbol_patterns_for_kind(safe_node_kind(node)):
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            return match.group(1)

    return None


def extract_parent_symbol(node: Any) -> str | None:
    """Return the nearest enclosing class/function-like symbol."""

    for ancestor in safe_node_ancestors(node):
        if safe_node_kind(ancestor) in DEFINITION_KINDS:
            symbol = extract_symbol_name(ancestor)
            if symbol:
                return symbol
    return None


def normalize_line_range(
    start_line: int,
    end_line: int,
) -> tuple[int, int]:
    """Clamp line range to one-based inclusive line numbers."""

    start_line = max(1, start_line)
    end_line = max(start_line, end_line)

    return start_line, end_line


def is_line_range_within_file(
    start_line: int,
    end_line: int,
    file_line_count: int,
) -> bool:
    """Return True when a chunk line range can point to real file lines."""

    if file_line_count <= 0:
        return True
    return 1 <= start_line <= end_line <= file_line_count


def deduplicate_ast_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    """Remove exact duplicate chunks while preserving order."""

    seen: set[tuple[str, int, int, str | None, str]] = set()
    unique_chunks: list[CodeChunk] = []

    for chunk in sorted(chunks, key=lambda item: (item.start_line, item.end_line)):
        key = (
            chunk.file_id,
            chunk.start_line,
            chunk.end_line,
            chunk.node_type,
            chunk.content_hash,
        )
        if key in seen:
            continue
        seen.add(key)
        unique_chunks.append(chunk)

    return unique_chunks


def split_large_ast_chunk(
    chunk: CodeChunk,
    config: ChunkingConfig,
) -> list[CodeChunk]:
    """Split oversized AST chunks into stable line-window subchunks."""

    max_lines = config.max_chunk_lines
    if max_lines <= 0:
        return [chunk]

    lines = chunk.content.splitlines()
    if len(lines) <= max_lines:
        return [chunk]

    overlap = min(config.overlap_lines, max_lines - 1)
    step = max_lines - overlap
    windows: list[tuple[int, list[str]]] = []

    for offset in range(0, len(lines), step):
        part_lines = lines[offset : offset + max_lines]
        if not part_lines:
            continue

        windows.append((offset, part_lines))
        if offset + max_lines >= len(lines):
            break

    split_count = len(windows)
    split_chunks: list[CodeChunk] = []

    for part_number, (offset, part_lines) in enumerate(windows, start=1):
        part_start = chunk.start_line + offset
        part_end = part_start + len(part_lines) - 1
        content = "\n".join(part_lines)

        data = model_to_dict(chunk)
        data.update(
            {
                "id": make_ast_chunk_id(
                    file_id=chunk.file_id,
                    start_line=part_start,
                    end_line=part_end,
                    node_type=chunk.node_type,
                    content=content,
                    suffix=f"part-{part_number}",
                ),
                "parent_chunk_id": chunk.id,
                "split_index": part_number,
                "split_count": split_count,
                "start_line": part_start,
                "end_line": part_end,
                "content": content,
                "content_hash": hash_chunk_content(content),
                "token_count": estimate_token_count(content),
            }
        )
        split_chunks.append(CodeChunk(**data))

    return split_chunks


def make_ast_chunk_id(
    file_id: str,
    start_line: int,
    end_line: int,
    node_type: str | None,
    content: str = "",
    suffix: str | None = None,
) -> str:
    """Build a stable chunk id from file id, location, AST type, and content."""

    raw = "|".join(
        [
            file_id,
            str(start_line),
            str(end_line),
            node_type or "unknown",
            hash_chunk_content(content)[:16],
            suffix or "",
        ]
    )
    digest = sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"chunk_ast_{digest}"


def hash_chunk_content(content: str) -> str:
    """Return a deterministic hash for chunk content."""

    return sha256(content.encode("utf-8")).hexdigest()


def estimate_token_count(content: str) -> int:
    """Estimate token count without binding the chunker to a tokenizer."""

    if not content:
        return 0
    return max(1, len(re.findall(r"\w+|[^\w\s]", content, flags=re.UNICODE)))


def extract_node_line_range(node: Any) -> tuple[int | None, int | None]:
    """Extract one-based inclusive line range from an AST-Grep node."""

    try:
        node_range = node.range()
    except Exception:
        return None, None

    start = getattr(node_range, "start", None)
    end = getattr(node_range, "end", None)
    if start is None or end is None:
        return None, None

    start_line = getattr(start, "line", None)
    end_line = getattr(end, "line", None)
    if start_line is None or end_line is None:
        return None, None

    return int(start_line) + 1, int(end_line) + 1


def extract_imports(content: str, language: str) -> list[str]:
    """Extract imported modules/packages from chunk text."""

    imports: list[str] = []
    for pattern in IMPORT_PATTERNS.get(normalize_language(language), []):
        imports.extend(re.findall(pattern, content, flags=re.MULTILINE))

    cleaned: list[str] = []
    for item in imports:
        cleaned.extend(part.strip() for part in item.split(",") if part.strip())
    return cleaned


def extract_calls(content: str) -> list[str]:
    """Extract function/method call-like identifiers from chunk text."""

    calls = re.findall(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        strip_comments_and_strings(content),
    )
    return [call for call in calls if call not in CALL_EXCLUDED_KEYWORDS]


def extract_referenced_symbols(content: str) -> list[str]:
    """Extract identifier-like symbols from code text."""

    identifiers = re.findall(
        r"\b[A-Za-z_][A-Za-z0-9_]*\b",
        strip_comments_and_strings(content),
    )
    return [
        identifier
        for identifier in identifiers
        if identifier.lower() not in SYMBOL_EXCLUDED_KEYWORDS
    ]


def strip_comments_and_strings(content: str) -> str:
    """Remove obvious comments and string literals before regex extraction."""

    without_block_comments = re.sub(r"/\*.*?\*/", " ", content, flags=re.DOTALL)
    without_line_comments = re.sub(
        r"//.*?$|#.*?$",
        " ",
        without_block_comments,
        flags=re.MULTILINE,
    )
    return re.sub(
        r"(['\"])(?:\\.|(?!\1).)*\1",
        " ",
        without_line_comments,
        flags=re.DOTALL,
    )


def symbol_patterns_for_kind(kind: str) -> list[str]:
    """Return regex fallbacks for symbol extraction by AST node kind."""

    if kind == "namespace_definition":
        return [r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_]*)"]
    if kind == "struct_specifier":
        return [r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)"]
    if "class" in kind or kind == "class_specifier":
        return [r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"]
    if "interface" in kind:
        return [r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)"]
    if "type_alias" in kind or kind == "type_declaration":
        return [r"\btype\s+([A-Za-z_][A-Za-z0-9_]*)"]
    if kind in {"function_definition", "function_declaration", "function_item"}:
        return [
            r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\b(?:[A-Za-z_][A-Za-z0-9_]*::)*([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:->\s*[A-Za-z_:<>*&\s]+)?\s*\{",
        ]
    if kind == "template_declaration":
        return [
            r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\b(?:[A-Za-z_][A-Za-z0-9_]*::)*([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:->\s*[A-Za-z_:<>*&\s]+)?\s*\{",
        ]
    if "method" in kind or "constructor" in kind:
        return [
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            r"\bfunc\s*\([^)]*\)\s*([A-Za-z_][A-Za-z0-9_]*)",
        ]
    if kind in {"lexical_declaration", "arrow_function"}:
        return [r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)"]
    return [r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\("]


def safe_node_text(node: Any) -> str:
    """Return node text without leaking AST-Grep exceptions."""

    try:
        return str(node.text())
    except Exception:
        return ""


def safe_node_kind(node: Any) -> str:
    """Return node kind without leaking AST-Grep exceptions."""

    try:
        return str(node.kind())
    except Exception:
        return "unknown"


def safe_node_field(node: Any, field_name: str) -> Any | None:
    """Return an AST-Grep named field when it exists."""

    try:
        return node.field(field_name)
    except Exception:
        return None


def safe_node_ancestors(node: Any) -> Iterable[Any]:
    """Return ancestors for parent-symbol extraction."""

    try:
        ancestors = node.ancestors()
    except Exception:
        return []

    try:
        return list(ancestors)
    except TypeError:
        return []


def model_to_dict(chunk: CodeChunk) -> dict[str, Any]:
    """Support both Pydantic v2 and v1 model serialization."""

    if hasattr(chunk, "model_dump"):
        return chunk.model_dump()
    return chunk.dict()
