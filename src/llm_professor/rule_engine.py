"""Compatibility shim — moved to src.bibops.evaluation.judges.rule_engine."""
from src.bibops.evaluation.judges.rule_engine import (
    EvaluationEngine,
    EvaluationProcessor,
    compare_models,
    filter_by_model,
)

__all__ = ["EvaluationEngine", "EvaluationProcessor", "compare_models", "filter_by_model"]
