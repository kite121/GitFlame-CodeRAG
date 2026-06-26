"""Loading synthetic GitHub-like issues from ``issues.jsonl``.

Owner: Kirill. Each line of an ``issues.jsonl`` file is one issue with
``id``, ``title``, ``body``, ``labels`` and ``expected_files``.
``expected_chunks`` is intentionally not part of Sprint 1.
"""

from __future__ import annotations

import json
from pathlib import Path

from gitflame_coderag.schemas import Issue


def load_issues(issues_path: Path, repository_id: str) -> list[Issue]:
    """Parse an ``issues.jsonl`` file into a list of :class:`Issue`.

    Blank lines are ignored. The ``repository_id`` is injected (and overrides any
    value present in the file) so issues always reference the owning repository.
    """
    issues_path = Path(issues_path)
    issues: list[Issue] = []
    for line_number, raw_line in enumerate(
        issues_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{issues_path}:{line_number}: invalid JSON ({error.msg})"
            ) from error
        payload.pop("expected_chunks", None)  # Deferred beyond Sprint 1.
        payload["repository_id"] = repository_id
        issues.append(Issue.model_validate(payload))
    return issues
