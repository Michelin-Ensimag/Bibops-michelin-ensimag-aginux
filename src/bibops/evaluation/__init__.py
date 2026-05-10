"""BibOps evaluation engine — judges, checks, metrics, scoring, reporting."""

from src.bibops.evaluation.judges.llm_professor import LLMProfessor
from src.bibops.evaluation.judges.rule_engine import (
    EvaluationEngine,
    EvaluationProcessor,
    compare_models,
    filter_by_model,
)
from src.bibops.evaluation.metrics.composite import CompositePolicy
from src.bibops.evaluation.metrics.greenops import calculate_carbon_footprint
from src.bibops.evaluation.quality_evaluator import QualityEvaluator
from src.bibops.evaluation.rca import RCAEngine
from src.bibops.evaluation.registry import EvaluatorRegistry
from src.bibops.evaluation.security_evaluator import SecurityLLMInspectorAdapter

__all__ = [
    "CompositePolicy",
    "EvaluationEngine",
    "EvaluationProcessor",
    "EvaluatorRegistry",
    "LLMProfessor",
    "QualityEvaluator",
    "RCAEngine",
    "SecurityLLMInspectorAdapter",
    "calculate_carbon_footprint",
    "compare_models",
    "filter_by_model",
]
