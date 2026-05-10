"""Compatibility shim — moved to src.bibops.evaluation.scoring.thresholds."""
from src.bibops.evaluation.scoring.thresholds import (
    CONFIG_DIR,
    ScoreThreshold,
    ScoreVerdict,
    Severity,
    Zone,
    evaluate_score,
    load_thresholds,
)

__all__ = [
    "CONFIG_DIR",
    "ScoreThreshold",
    "ScoreVerdict",
    "Severity",
    "Zone",
    "evaluate_score",
    "load_thresholds",
]
