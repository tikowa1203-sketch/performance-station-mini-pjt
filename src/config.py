from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    region: str = os.getenv("AWS_REGION", "us-east-1")
    model_id: str = os.getenv(
        "MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    use_bedrock: bool = os.getenv("USE_BEDROCK", "false").lower() == "true"
    top_k: int = int(os.getenv("TOP_K", "4"))
    trace_path: Path = PROJECT_ROOT / os.getenv("TRACE_PATH", "data/traces.jsonl")
    data_dir: Path = PROJECT_ROOT / "data"


settings = Settings()

