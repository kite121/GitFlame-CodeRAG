from dataclasses import dataclass


@dataclass
class PipelineConfig:
    input_glob: str = "data/*.csv"
    output_path: str = "out/result.jsonl"
    fail_fast: bool = True
