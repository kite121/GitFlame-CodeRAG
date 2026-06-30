"""Repository ``.yml`` configuration loading and parsing.

Owner: Kirill. ``load_ai_config`` reads raw YAML; ``parse_ai_config`` maps it onto
the shared :class:`AIConfig` schema used by every downstream module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gitflame_coderag.schemas import AIConfig


def load_ai_config(config_path: Path) -> dict[str, Any]:
    """Read a repository ``.yml`` file into a raw mapping."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("repository config must contain a YAML mapping")
    return raw


def _section(raw_config: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a sub-mapping, tolerating missing or empty (``None``) sections."""
    value = raw_config.get(key)
    return value if isinstance(value, dict) else {}


def parse_ai_config(raw_config: dict[str, Any]) -> AIConfig:
    """Map a raw repository config onto the :class:`AIConfig` contract.

    ``analysis.include`` / ``analysis.exclude`` drive file filtering. Unknown
    top-level sections (``ast_grep``, ``issues``, ``storage``, ``evaluation``,
    ``repository`` ...) are intentionally ignored here.
    """
    analysis = _section(raw_config, "analysis")
    return AIConfig.model_validate(
        {
            "version": raw_config.get("version", 1),
            "include": analysis.get("include") or ["**/*"],
            "exclude": analysis.get("exclude") or [],
            "chunking": _section(raw_config, "chunking"),
            "retrieval": _section(raw_config, "retrieval"),
            "embeddings": _section(raw_config, "embeddings"),
        }
    )
