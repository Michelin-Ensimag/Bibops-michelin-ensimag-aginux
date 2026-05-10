"""Compatibility shim — eval_bank.metrics has been moved to src.bibops.evaluation.metrics."""
from src.bibops.evaluation.metrics.consistency import (
    VocabularyConsistencyMetric,
    run_n_times,
)

__all__ = ["VocabularyConsistencyMetric", "run_n_times"]
