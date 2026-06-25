import json
from pathlib import Path


def write_jsonl(rows: list[dict], path: Path) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return len(rows)
