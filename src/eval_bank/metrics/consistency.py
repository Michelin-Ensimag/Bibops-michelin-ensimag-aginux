"""Compatibility shim — moved to src.bibops.evaluation.metrics.consistency."""
from src.bibops.evaluation.metrics.consistency import (
    VocabularyConsistencyMetric,
    run_n_times,
)

__all__ = ["VocabularyConsistencyMetric", "run_n_times"]
