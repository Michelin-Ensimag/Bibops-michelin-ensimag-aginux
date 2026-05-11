"""Extra coverage for benchmark/runners: pure helpers not covered by other tests."""
from __future__ import annotations

import math
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# test_biais_position: pure math helpers
# ---------------------------------------------------------------------------

class TestBinomPmf:
    def test_zero_k(self):
        from src.benchmark.test_biais_position import _binom_pmf
        result = _binom_pmf(10, 0, 0.5)
        assert abs(result - (0.5 ** 10)) < 1e-12

    def test_all_successes(self):
        from src.benchmark.test_biais_position import _binom_pmf
        result = _binom_pmf(5, 5, 0.5)
        assert abs(result - (0.5 ** 5)) < 1e-12

    def test_mid_point(self):
        from src.benchmark.test_biais_position import _binom_pmf
        result = _binom_pmf(4, 2, 0.5)
        assert result > 0

    def test_certain_event_at_k_n(self):
        from src.benchmark.test_biais_position import _binom_pmf
        # p=1.0, k=n → result = 1.0
        result = _binom_pmf(3, 3, 1.0)
        assert abs(result - 1.0) < 1e-12


class TestBinomTestTwoSided:
    def test_zero_n_returns_one(self):
        from src.benchmark.test_biais_position import binom_test_two_sided
        assert binom_test_two_sided(0, 0) == 1.0

    def test_negative_n_returns_one(self):
        from src.benchmark.test_biais_position import binom_test_two_sided
        assert binom_test_two_sided(0, -1) == 1.0

    def test_unbiased_center(self):
        from src.benchmark.test_biais_position import binom_test_two_sided
        # k=n/2 → high p-value (no bias evidence)
        p = binom_test_two_sided(5, 10)
        assert 0.0 < p <= 1.0

    def test_extreme_result_low_pvalue(self):
        from src.benchmark.test_biais_position import binom_test_two_sided
        # k=0, n=20 → very unlikely under fair coin
        p = binom_test_two_sided(0, 20)
        assert p < 0.01

    def test_result_clamped_to_one(self):
        from src.benchmark.test_biais_position import binom_test_two_sided
        # p=0.5, k=n/2 → sum of all probs ≈ 1.0
        p = binom_test_two_sided(1, 2)
        assert p <= 1.0

    def test_all_trials_same_outcome(self):
        from src.benchmark.test_biais_position import binom_test_two_sided
        p = binom_test_two_sided(10, 10)
        assert p < 0.01  # very significant


# ---------------------------------------------------------------------------
# ab_test_user: env helpers and appeler_modele
# ---------------------------------------------------------------------------

class TestEnvInt:
    def test_missing_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("SOME_VAR", raising=False)
        from src.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 42) == 42

    def test_valid_positive_int(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "7")
        from src.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 42) == 7

    def test_zero_or_negative_returns_default(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "0")
        from src.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 5) == 5

    def test_non_int_returns_default(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "abc")
        from src.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 3) == 3

    def test_empty_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "  ")
        from src.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 99) == 99


class TestAutoChoiceDefault:
    def test_default_is_a(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_AB_USER_CHOICE", raising=False)
        from src.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "A"

    def test_b_from_env(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_AB_USER_CHOICE", "B")
        from src.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "B"

    def test_invalid_falls_back_to_a(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_AB_USER_CHOICE", "X")
        from src.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "A"

    def test_lowercase_normalized(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_AB_USER_CHOICE", "b")
        from src.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "B"


class TestIsNonInteractiveMode:
    def test_env_flag_set(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")
        from src.benchmark.ab_test_user import _is_non_interactive_mode
        assert _is_non_interactive_mode() is True

    def test_env_flag_not_set_returns_bool(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_NON_INTERACTIVE", raising=False)
        from src.benchmark.ab_test_user import _is_non_interactive_mode
        assert isinstance(_is_non_interactive_mode(), bool)


class TestAppelerModeleUser:
    def _make_response(self, content: str):
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    def test_returns_content_on_success(self):
        from src.benchmark.ab_test_user import appeler_modele
        client = MagicMock()
        client.chat.completions.create.return_value = self._make_response("VPN OK")
        result = appeler_modele(client, "gpt-4o-mini", "ctx", "ticket", retries=1)
        assert result == "VPN OK"

    def test_retries_on_exception(self):
        from src.benchmark.ab_test_user import appeler_modele
        client = MagicMock()
        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("transient error")
            return self._make_response("recovered")
        client.chat.completions.create.side_effect = side_effect
        with patch("src.benchmark.ab_test_user.time.sleep"):
            result = appeler_modele(client, "gpt-4o-mini", "ctx", "ticket", retries=2)
        assert result == "recovered"
        assert call_count[0] == 2

    def test_all_retries_fail_returns_error_string(self):
        from src.benchmark.ab_test_user import appeler_modele
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("always fails")
        with patch("src.benchmark.ab_test_user.time.sleep"):
            result = appeler_modele(client, "gpt-4o-mini", "ctx", "ticket", retries=2)
        assert "ERREUR_MODELE" in result
        assert "always fails" in result


# ---------------------------------------------------------------------------
# core.py: EOFError path in demander_feedback_utilisateur
# ---------------------------------------------------------------------------

class TestDemanderFeedbackEOF:
    def test_eof_returns_default(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_NON_INTERACTIVE", raising=False)
        monkeypatch.delenv("BIBOPS_DEFAULT_FEEDBACK", raising=False)
        # Make stdin look like a tty so non-interactive check passes,
        # then raise EOFError on input()
        with patch("src.benchmark.core.sys.stdin") as fake_stdin, \
             patch("builtins.input", side_effect=EOFError()):
            fake_stdin.isatty.return_value = True
            from src.benchmark.core import demander_feedback_utilisateur
            result = demander_feedback_utilisateur()
        # Should return a valid feedback string (default "2" = Partiellement utile)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# ab_test_llm.py: missed branches
# ---------------------------------------------------------------------------

def _make_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestAppelerJugeMissedBranches:
    def test_retry_strict_prompt_also_fails(self):
        """Both JSON attempts fail → None, 'JSON invalide'."""
        from src.benchmark.ab_test_llm import appeler_juge

        call_count = [0]
        def fake_timeout(fn, _):
            call_count[0] += 1
            return _make_response("not json")

        client = MagicMock()
        with patch("src.benchmark.ab_test_llm._executer_avec_timeout", side_effect=fake_timeout):
            result, err = appeler_juge(client, "gpt-4o", "prompt")

        assert result is None
        assert call_count[0] == 2  # both strict and normal attempted

    def test_invalid_choix_field_returns_none(self):
        """Valid JSON but choix field not A/B → None, 'Champ choix invalide'."""
        from src.benchmark.ab_test_llm import appeler_juge

        client = MagicMock()
        with patch("src.benchmark.ab_test_llm._executer_avec_timeout",
                   side_effect=lambda fn, _: fn()):
            client.chat.completions.create.return_value = _make_response(
                '{"choix": "C", "justification": "neither"}'
            )
            result, err = appeler_juge(client, "gpt-4o", "prompt")

        assert result is None
        assert "choix" in err.lower() or err == "Champ choix invalide"


class TestGenererReponseNonEligibleFallback:
    def test_error_not_eligible_does_not_fallback(self):
        """When initial model returns a non-fallback-eligible error, return immediately."""
        from src.benchmark.ab_test_llm import generer_reponse_avec_fallback

        def fake_appeler(client, modele, ctx, ticket, timeout):
            return "[ERREUR_NON_ELIGIBLE] hard refusal"

        def fake_est_erreur(rep):
            return "[ERREUR" in rep

        def fake_eligible(rep):
            return False  # NOT eligible for fallback

        with patch("src.benchmark.ab_test_llm.appeler_modele", side_effect=fake_appeler), \
             patch("src.benchmark.ab_test_llm._est_reponse_erreur", side_effect=fake_est_erreur), \
             patch("src.benchmark.ab_test_llm._erreur_modele_eligible_fallback", side_effect=fake_eligible):
            result, model, tried = generer_reponse_avec_fallback(
                MagicMock(), "gpt-4o-mini", "ctx", "ticket"
            )

        assert "ERREUR" in result
        assert model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# mcp_tools.py: import (covers module-level constants and TICKETS_TEST)
# ---------------------------------------------------------------------------

class TestMcpToolsImport:
    def test_module_imports(self):
        import src.benchmark.mcp_tools as m
        assert hasattr(m, "TICKETS_TEST")
        assert isinstance(m.TICKETS_TEST, list)
        assert len(m.TICKETS_TEST) > 0

    def test_tickets_have_required_keys(self):
        import src.benchmark.mcp_tools as m
        for t in m.TICKETS_TEST:
            assert "id_ticket" in t
            assert "ticket" in t
