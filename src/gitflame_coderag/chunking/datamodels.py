"""Internal data models for chunking implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AstMatch:
    """Normalized AST-Grep match used before building a CodeChunk."""

    node: Any
    node_type: str
    symbol_name: str | None
    parent_symbol: str | None
    start_line: int
    end_line: int
    content: str
