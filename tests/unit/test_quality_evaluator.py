"""Unit tests for the QualityEvaluator wrapper around LLMProfessor."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.bibops.evaluation.quality_evaluator import QualityEvaluator


class _FakeJudge:
    """Stand-in for LLMProfessor with the chain interface QualityEvaluator uses."""

    def __init__(self, result):
        self.parser = MagicMock()
        self.parser.get_format_instructions.return_value = "INSTR"
        self.chain = MagicMock()
        if isinstance(result, Exception):
            self.chain.invoke.side_effect = result
        else:
            self.chain.invoke.return_value = result


class TestEvaluate:
    def test_returns_score_and_justification_on_success(self):
        judge = _FakeJudge({"note": 8.5, "justification": "fine"})
        evaluator = QualityEvaluator(judge=judge)
        out = evaluator.evaluate({"ticket_text": "T", "answer_text": "A", "diagnostic_rca": "RCA"})
        assert out["status"] == "ok"
        assert out["score"] == 8.5
        assert out["justification"] == "fine"
        assert out["error"] == ""

    def test_score_is_clamped_to_0_10_range(self):
        judge = _FakeJudge({"note": 99, "justification": "huge"})
        out = QualityEvaluator(judge=judge).evaluate({"ticket_text": "t", "answer_text": "a"})
        assert out["score"] == 10.0

        judge = _FakeJudge({"note": -5, "justification": ""})
        out = QualityEvaluator(judge=judge).evaluate({"ticket_text": "t", "answer_text": "a"})
        assert out["score"] == 0.0

    def test_missing_note_defaults_to_zero(self):
        judge = _FakeJudge({"justification": "no note"})
        out = QualityEvaluator(judge=judge).evaluate({"ticket_text": "t", "answer_text": "a"})
        assert out["score"] == 0.0

    def test_chain_exception_returns_error_envelope(self):
        judge = _FakeJudge(RuntimeError("upstream"))
        out = QualityEvaluator(judge=judge).evaluate({"ticket_text": "t", "answer_text": "a"})
        assert out["status"] == "error"
        assert out["score"] == 0.0
        assert "upstream" in out["error"]

    def test_evaluator_has_quality_name(self):
        assert QualityEvaluator(judge=_FakeJudge({"note": 0})).name == "quality"

    def test_missing_diagnostic_rca_uses_placeholder(self):
        judge = _FakeJudge({"note": 7, "justification": "ok"})
        evaluator = QualityEvaluator(judge=judge)
        evaluator.evaluate({"ticket_text": "t", "answer_text": "a"})
        invoke_kwargs = judge.chain.invoke.call_args[0][0]
        assert invoke_kwargs["diagnostic_rca"] == "Non disponible"
