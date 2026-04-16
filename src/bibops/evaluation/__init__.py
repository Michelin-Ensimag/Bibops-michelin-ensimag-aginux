"""Evaluation wrappers."""

from src.bibops.evaluation.llm_judge import LLMProfessor
from src.bibops.evaluation.rule_engine import EvaluationEngine, EvaluationProcessor

__all__ = ["EvaluationEngine", "EvaluationProcessor", "LLMProfessor"]
