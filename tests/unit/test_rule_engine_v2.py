"""Tests for EvaluationEngineV2 (fact-checking dimension) and EvaluationEngine edge cases."""
from __future__ import annotations

import pytest

from src.bibops.evaluation.judges.rule_engine import EvaluationEngine, EvaluationEngineV2


class TestEvaluationEngineEdgeCases:
    """Additional coverage for EvaluationEngine branches not hit by existing tests."""

    def setup_method(self):
        self.engine = EvaluationEngine()

    # score_erreur
    def test_score_erreur_erreur_string(self):
        assert self.engine.score_erreur("ERREUR") == 0.0

    def test_score_erreur_normal(self):
        assert self.engine.score_erreur("Some response") == 10.0

    # score_feedback branches
    def test_score_feedback_utile(self):
        assert self.engine.score_feedback("Utile") == 10.0

    def test_score_feedback_partiellement_utile(self):
        score = self.engine.score_feedback("Partiellement utile")
        assert 0.0 < score < 10.0

    def test_score_feedback_inutile(self):
        assert self.engine.score_feedback("Inutile") == 0.0

    def test_score_feedback_unknown(self):
        assert self.engine.score_feedback("PasUneFeedback") == 0.0

    # score_vitesse edge cases
    def test_score_vitesse_zero_is_excellent(self):
        assert self.engine.score_vitesse(0.0) == 10.0

    def test_score_vitesse_very_slow_is_zero(self):
        assert self.engine.score_vitesse(999.0) == 0.0

    def test_score_vitesse_mid_range(self):
        score = self.engine.score_vitesse(5.0)
        assert 0.0 <= score <= 10.0

    # score_efficacite_tokens edge cases
    def test_score_tokens_zero(self):
        assert self.engine.score_efficacite_tokens(0) == 10.0

    def test_score_tokens_excessive(self):
        assert self.engine.score_efficacite_tokens(10000) == 0.0

    def test_score_tokens_moderate(self):
        score = self.engine.score_efficacite_tokens(200)
        assert 0.0 <= score <= 10.0

    # score_pertinence — no KB match
    def test_score_pertinence_unknown_ticket(self):
        result = self.engine.score_pertinence("Good response here", "Unknown topic xyz123")
        assert result["score"] == 5.0  # default when no KB match

    def test_score_pertinence_erreur_response(self):
        result = self.engine.score_pertinence("ERREUR", "VPN issue")
        assert result["score"] == 0.0

    def test_score_pertinence_empty_response(self):
        result = self.engine.score_pertinence("   ", "VPN issue")
        assert result["score"] == 0.0

    # calculate_final_score with ERREUR
    def test_calculate_final_score_erreur_path(self):
        scores = self.engine.calculate_final_score(
            reponse="ERREUR",
            feedback="Inutile",
            temps_secondes=0.0,
            nombre_tokens=0,
            ticket="Test ticket",
        )
        assert scores["score_erreur"] == 0.0  # ERREUR penalty
        assert scores["score_final"] <= 5.0   # heavily penalised

    def test_calculate_final_score_no_ticket_uses_default_pertinence(self):
        scores = self.engine.calculate_final_score(
            reponse="Fine response",
            feedback="Utile",
            temps_secondes=1.0,
            nombre_tokens=100,
        )
        # No ticket → pertinence default = 5.0
        assert scores["score_pertinence"] == 5.0

    def test_calculate_final_score_all_perfect(self):
        scores = self.engine.calculate_final_score(
            reponse="Check VPN connection and restart AnyConnect.",
            feedback="Utile",
            temps_secondes=0.5,
            nombre_tokens=50,
            ticket="Mon VPN ne marche pas",
        )
        assert 0.0 <= scores["score_final"] <= 10.0

    # _tokeniser
    def test_tokeniser_removes_stopwords(self):
        tokens = self.engine._tokeniser("le chat est sur le toit")
        assert "le" not in tokens
        assert "chat" in tokens

    def test_tokeniser_lowercases(self):
        tokens = self.engine._tokeniser("VPN CISCO")
        assert "vpn" in tokens
        assert "cisco" in tokens

    def test_tokeniser_filters_short_words(self):
        tokens = self.engine._tokeniser("to an is a of")
        assert len(tokens) == 0


class TestEvaluationEngineV2:
    """Tests for V2 engine with fact-checking dimension."""

    def setup_method(self):
        self.engine = EvaluationEngineV2()

    def test_score_fact_checking_none_returns_neutral(self):
        assert self.engine.score_fact_checking(None) == 5.0

    def test_score_fact_checking_zero(self):
        assert self.engine.score_fact_checking(0.0) == 0.0

    def test_score_fact_checking_one(self):
        assert self.engine.score_fact_checking(1.0) == 10.0

    def test_score_fact_checking_midpoint(self):
        assert self.engine.score_fact_checking(0.7) == pytest.approx(7.0)

    def test_score_fact_checking_clamped_above_1(self):
        assert self.engine.score_fact_checking(2.0) == 10.0

    def test_score_fact_checking_clamped_below_0(self):
        assert self.engine.score_fact_checking(-0.5) == 0.0

    def test_calculate_final_score_v2_normal(self):
        scores = self.engine.calculate_final_score(
            reponse="Reconnect VPN client.",
            feedback="Utile",
            temps_secondes=1.0,
            nombre_tokens=100,
            accuracy_score=0.8,
        )
        assert 0.0 <= scores["score_final"] <= 10.0
        assert "score_fact_checking" in scores

    def test_calculate_final_score_v2_erreur(self):
        scores = self.engine.calculate_final_score(
            reponse="ERREUR",
            feedback="Inutile",
            temps_secondes=0.0,
            nombre_tokens=0,
            accuracy_score=None,
        )
        assert scores["score_erreur"] == 0.0

    def test_calculate_final_score_v2_no_accuracy(self):
        scores = self.engine.calculate_final_score(
            reponse="Good response",
            feedback="Utile",
            temps_secondes=1.0,
            nombre_tokens=50,
        )
        assert scores["score_fact_checking"] == 5.0  # None → neutral

    def test_v2_weights_sum_to_one(self):
        from src.bibops.evaluation.judges.rule_engine import _WEIGHTS_V2
        total = sum(_WEIGHTS_V2.values())
        assert abs(total - 1.0) < 1e-9

    def test_v2_has_no_pertinence_key(self):
        scores = self.engine.calculate_final_score(
            reponse="ok", feedback="Utile", temps_secondes=1.0, nombre_tokens=50
        )
        assert "score_pertinence" not in scores
        assert "score_fact_checking" in scores
