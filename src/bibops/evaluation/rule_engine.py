"""Rule-based evaluation wrappers."""

from src.llm_professor.evaluation import EvaluationEngine, EvaluationProcessor, compare_models, filter_by_model

__all__ = [
    "EvaluationEngine",
    "EvaluationProcessor",
    "compare_models",
    "filter_by_model",
]
