"""Judges: LLM-based and rule-based scoring."""

from src.bibops.evaluation.judges.llm_judge import JudgeVerdict, LLMJudge
from src.bibops.evaluation.judges.llm_professor import EvaluationResult, LLMProfessor
from src.bibops.evaluation.judges.rule_engine import (
    EvaluationEngine,
    EvaluationProcessor,
    compare_models,
    filter_by_model,
)

__all__ = [
    "EvaluationEngine",
    "EvaluationProcessor",
    "EvaluationResult",
    "JudgeVerdict",
    "LLMJudge",
    "LLMProfessor",
    "compare_models",
    "filter_by_model",
]
