"""Unit tests for the QualityEvaluator wrapper around LLMProfessor."""
from __future__ import annotations

from src.bibops.evaluation.quality_evaluator import QualityEvaluator


class _FakeJudge:
    """Stand-in for LLMProfessor using evaluer_reponse interface."""

    def __init__(self, result):
        self._result = result
        self._last_call: dict = {}

    def evaluer_reponse(self, *, ticket_id, ticket_texte, reponse_agent, modele_agent, temps_reponse, diagnostic_rca):
        self._last_call = {
            "ticket_texte": ticket_texte,
            "reponse_agent": reponse_agent,
            "diagnostic_rca": diagnostic_rca,
        }
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class TestEvaluate:
    def test_returns_score_and_justification_on_success(self):
        judge = _FakeJudge({"note": 8, "justification": "fine"})
        evaluator = QualityEvaluator(judge=judge)
        out = evaluator.evaluate({"ticket_text": "T", "answer_text": "A", "diagnostic_rca": "RCA"})
        assert out["status"] == "ok"
        assert out["score"] == 8.0
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

    def test_judge_returns_none_gives_error_envelope(self):
        judge = _FakeJudge(None)
        out = QualityEvaluator(judge=judge).evaluate({"ticket_text": "t", "answer_text": "a"})
        assert out["status"] == "error"
        assert out["score"] == 0.0

    def test_evaluator_has_quality_name(self):
        assert QualityEvaluator(judge=_FakeJudge({"note": 0})).name == "quality"

    def test_missing_diagnostic_rca_uses_placeholder(self):
        judge = _FakeJudge({"note": 7, "justification": "ok"})
        evaluator = QualityEvaluator(judge=judge)
        evaluator.evaluate({"ticket_text": "t", "answer_text": "a"})
        assert judge._last_call["diagnostic_rca"] == "Non disponible"
