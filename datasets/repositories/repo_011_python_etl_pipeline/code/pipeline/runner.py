from pathlib import Path

from pipeline.extract import read_many
from pipeline.load import write_jsonl
from pipeline.transform import deduplicate, normalize_row


def run(inputs: list[Path], output: Path) -> int:
    raw = read_many(inputs)
    transformed = [normalize_row(row) for row in raw]
    unique = deduplicate(transformed)
    return write_jsonl(unique, output)
