"""Centralised configuration constants for BibOps."""
import os
from pathlib import Path


def _env(key: str, default: str) -> str:
    return os.environ.get(key, "").strip() or default


BASE_DIR: Path = Path(__file__).resolve().parents[2]

COPILOT_BASE_URL: str = os.environ.get("COPILOT_API_URL", "http://localhost:4141/v1")

SUPPORTED_PROVIDERS: tuple[str, ...] = ("ollama", "copilot")
SUPPORTED_JUDGE_MODELS: tuple[str, ...] = (
    "gemini-3.1-pro-preview", "gpt-5.2-codex", "gpt-5.4-mini",
    "grok-code-fast-1", "claude-haiku-4.5", "gemini-3-flash-preview",
    "gpt-5.2", "gpt-4o",
)
SUPPORTED_LOCAL_LLM_MODELS: tuple[str, ...] = ("phi3:latest", "mistral:latest")
# Keep legacy proxy models accepted for A/B candidate responses and smoke tests.
SUPPORTED_COPILOT_AGENT_MODELS: tuple[str, ...] = (*SUPPORTED_JUDGE_MODELS, "gpt-4o-mini")

DEFAULT_JUDGE_MODEL: str = _env("BIBOPS_JUDGE_MODEL", "gpt-4o")
DEFAULT_AGENT_PROVIDER: str = _env("BIBOPS_AGENT_PROVIDER", "ollama")
DEFAULT_AGENT_MODEL: str = _env("BIBOPS_AGENT_MODEL", "phi3:latest")
DEFAULT_ZERO_SHOT_PROVIDER: str = _env("BIBOPS_ZERO_SHOT_PROVIDER", "ollama")
DEFAULT_ZERO_SHOT_MODEL: str = _env("BIBOPS_ZERO_SHOT_MODEL", "phi3:latest")

MODEL_REQUEST_TIMEOUT_S: int = int(os.environ.get("BIBOPS_MODEL_REQUEST_TIMEOUT_S", "60"))
JUDGE_REQUEST_TIMEOUT_S: int = int(os.environ.get("BIBOPS_JUDGE_REQUEST_TIMEOUT_S", "30"))

OLLAMA_OPTIONS: dict = {"num_predict": 1024, "temperature": 0}

INPUT_CSV: Path = BASE_DIR / "data" / "inputs" / "benchmark" / "tickets_scenario_1.csv"
OUTPUT_DIR: Path = BASE_DIR / "data" / "outputs" / "benchmark"

PROBES_DIR: Path = Path(os.environ.get("BIBOPS_PROBES_DIR") or BASE_DIR / "data" / "inputs" / "probes")
THRESHOLDS_DIR: Path = Path(os.environ.get("BIBOPS_THRESHOLDS_DIR") or BASE_DIR / "config" / "thresholds")


def normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Invalid provider: {provider}. Available: {', '.join(SUPPORTED_PROVIDERS)}")
    return normalized


def available_models_for_provider(provider: str) -> tuple[str, ...]:
    provider = normalize_provider(provider)
    if provider == "ollama":
        return SUPPORTED_LOCAL_LLM_MODELS
    if provider == "copilot":
        return SUPPORTED_COPILOT_AGENT_MODELS
    return ()


def validate_judge_model(model: str) -> str:
    normalized = (model or "").strip()
    if normalized not in SUPPORTED_JUDGE_MODELS:
        raise ValueError(f"Invalid judge model: {model}. Available: {', '.join(SUPPORTED_JUDGE_MODELS)}")
    return normalized


def validate_chat_model(provider: str, model: str, *, role: str = "model") -> tuple[str, str]:
    normalized_provider = normalize_provider(provider)
    normalized_model = (model or "").strip()
    available = available_models_for_provider(normalized_provider)
    if normalized_model not in available:
        raise ValueError(
            f"Invalid {role} for provider '{normalized_provider}': {model}. "
            f"Available: {', '.join(available)}"
        )
    return normalized_provider, normalized_model


LLM_COST_INPUT_PER_1M_USD: float = 2.50
LLM_COST_OUTPUT_PER_1M_USD: float = 10.00
