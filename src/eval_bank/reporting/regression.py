"""Compatibility shim — moved to src.bibops.evaluation.reporting.regression."""
from src.bibops.evaluation.reporting.regression import (
    check_regression,
    extract_scores_from_report,
    write_baseline,
)

__all__ = ["check_regression", "extract_scores_from_report", "write_baseline"]
