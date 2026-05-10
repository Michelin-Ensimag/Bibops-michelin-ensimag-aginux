"""Centralised configuration constants for BibOps."""
import os
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parents[2]

COPILOT_BASE_URL: str = os.environ.get("COPILOT_API_URL", "http://localhost:4141/v1")

DEFAULT_JUDGE_MODEL: str = "gpt-4o"
DEFAULT_AGENT_MODEL: str = "phi3:latest"

MODEL_REQUEST_TIMEOUT_S: int = 30
JUDGE_REQUEST_TIMEOUT_S: int = 30

OLLAMA_OPTIONS: dict = {"num_predict": 1024, "temperature": 0}

INPUT_CSV: Path = BASE_DIR / "data" / "inputs" / "benchmark" / "tickets_scenario_1.csv"
OUTPUT_DIR: Path = BASE_DIR / "data" / "outputs" / "benchmark"

PROBES_DIR: Path = Path(os.environ.get("BIBOPS_PROBES_DIR") or BASE_DIR / "data" / "inputs" / "probes")
THRESHOLDS_DIR: Path = Path(os.environ.get("BIBOPS_THRESHOLDS_DIR") or BASE_DIR / "config" / "thresholds")
