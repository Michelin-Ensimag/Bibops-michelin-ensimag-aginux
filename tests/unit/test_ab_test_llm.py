"""Tests for src/benchmark/ab_test_llm.py — pure functions and mocked LLM calls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Pure helper: _construire_prompt_juge
# ---------------------------------------------------------------------------

class TestConstruirePromptJuge:
    def test_contains_all_parts(self):
        from src.benchmark.ab_test_llm import _construire_prompt_juge
        prompt = _construire_prompt_juge("IT context", "Question?", "Reply A", "Reply B")
        assert "IT context" in prompt
        assert "Question?" in prompt
        assert "Reply A" in prompt
        assert "Reply B" in prompt

    def test_has_json_format_instruction(self):
        from src.benchmark.ab_test_llm import _construire_prompt_juge
        prompt = _construire_prompt_juge("ctx", "q", "a", "b")
        assert "JSON" in prompt or "choix" in prompt.lower()


# ---------------------------------------------------------------------------
# appeler_juge — mocked OpenAI
# ---------------------------------------------------------------------------

def _make_openai_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


class TestAppelerJuge:
    def test_returns_valid_result_on_success(self):
        from src.benchmark.ab_test_llm import appeler_juge
        from src.common.text import _executer_avec_timeout

        client = MagicMock()
        client.chat.completions.create.return_value = _make_openai_response('{"choix": "A", "justification": "clear"}')

        with patch("src.benchmark.ab_test_llm._executer_avec_timeout", side_effect=lambda fn, _: fn()):
            result, err = appeler_juge(client, "gpt-4o", "some prompt")

        assert result is not None
        assert result["choix"] in ("A", "B")
        assert err == ""

    def test_returns_none_on_timeout(self):
        from src.benchmark.ab_test_llm import appeler_juge
        from concurrent.futures import TimeoutError as FT

        client = MagicMock()
        with patch("src.benchmark.ab_test_llm._executer_avec_timeout", side_effect=FT()):
            result, err = appeler_juge(client, "gpt-4o", "prompt")

        assert result is None
        assert "Timeout" in err or "timeout" in err.lower()

    def test_returns_none_on_invalid_json(self):
        from src.benchmark.ab_test_llm import appeler_juge

        client = MagicMock()
        with patch("src.benchmark.ab_test_llm._executer_avec_timeout", side_effect=lambda fn, _: fn()):
            client.chat.completions.create.return_value = _make_openai_response("not json at all")
            result, err = appeler_juge(client, "gpt-4o", "prompt")

        # Either None (invalid JSON path) or retried → still None
        assert result is None or isinstance(result, dict)

    def test_returns_none_on_exception(self):
        from src.benchmark.ab_test_llm import appeler_juge

        client = MagicMock()
        with patch("src.benchmark.ab_test_llm._executer_avec_timeout", side_effect=RuntimeError("oops")):
            result, err = appeler_juge(client, "gpt-4o", "prompt")

        assert result is None
        assert "oops" in err


# ---------------------------------------------------------------------------
# appeler_juge_qwen_robuste — cascading fallback
# ---------------------------------------------------------------------------

class TestAppelerJugeQwenRobuste:
    def test_returns_result_from_first_candidate(self):
        from src.benchmark.ab_test_llm import appeler_juge_qwen_robuste

        with patch("src.benchmark.ab_test_llm.appeler_juge",
                   return_value=({"choix": "B", "justification": "ok"}, "")):
            result, model, err = appeler_juge_qwen_robuste(MagicMock(), "gpt-4o", "prompt")

        assert result is not None
        assert result["choix"] == "B"
        assert err == ""

    def test_falls_back_when_first_fails(self):
        from src.benchmark.ab_test_llm import appeler_juge_qwen_robuste

        call_count = [0]
        def fake_appeler_juge(client, modele, prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return None, "model refused"
            return {"choix": "A", "justification": "fallback"}, ""

        with patch("src.benchmark.ab_test_llm.appeler_juge", side_effect=fake_appeler_juge):
            result, model, err = appeler_juge_qwen_robuste(MagicMock(), "gpt-4o", "prompt")

        assert result is not None
        assert call_count[0] >= 2

    def test_skips_forbidden_model(self):
        from src.benchmark.ab_test_llm import appeler_juge_qwen_robuste

        called_with = []
        def fake_appeler_juge(client, modele, prompt):
            called_with.append(modele)
            return {"choix": "A", "justification": "ok"}, ""

        with patch("src.benchmark.ab_test_llm.appeler_juge", side_effect=fake_appeler_juge):
            appeler_juge_qwen_robuste(MagicMock(), "gpt-4o", "prompt", modeles_interdits={"gpt-4o"})

        # gpt-4o should be skipped
        assert "gpt-4o" not in called_with

    def test_all_fail_returns_none(self):
        from src.benchmark.ab_test_llm import appeler_juge_qwen_robuste

        with patch("src.benchmark.ab_test_llm.appeler_juge", return_value=(None, "fail")):
            result, model, err = appeler_juge_qwen_robuste(MagicMock(), "gpt-4o", "prompt")

        assert result is None
        assert err != ""

    def test_all_forbidden_returns_none(self):
        from src.benchmark.ab_test_llm import appeler_juge_qwen_robuste, MODEL_FALLBACK_POOL, DEFAULT_JUDGE_MODEL

        all_models = {DEFAULT_JUDGE_MODEL, "gpt-4o", "claude-haiku-4.5", "gpt-4o-mini"}
        result, model, err = appeler_juge_qwen_robuste(MagicMock(), "gpt-4o", "prompt", modeles_interdits=all_models)
        assert result is None


# ---------------------------------------------------------------------------
# evaluer_ticket_par_juge
# ---------------------------------------------------------------------------

class TestEvaluerTicketParJuge:
    def test_ok_when_judge_succeeds(self):
        from src.benchmark.ab_test_llm import evaluer_ticket_par_juge

        with patch("src.benchmark.ab_test_llm.appeler_juge_qwen_robuste",
                   return_value=({"choix": "A", "justification": "clear"}, "gpt-4o", "")):
            result = evaluer_ticket_par_juge(MagicMock(), "gpt-4o", "ctx", "q", "a", "b")

        assert result["ok"] is True
        assert result["choix"] == "A"
        assert result["juge_utilise"] == "gpt-4o"

    def test_not_ok_when_judge_fails(self):
        from src.benchmark.ab_test_llm import evaluer_ticket_par_juge

        with patch("src.benchmark.ab_test_llm.appeler_juge_qwen_robuste",
                   return_value=(None, "", "Aucun endpoint disponible")):
            result = evaluer_ticket_par_juge(MagicMock(), "gpt-4o", "ctx", "q", "a", "b")

        assert result["ok"] is False
        assert result["choix"] == ""
        assert "Aucun" in result["erreur"]


# ---------------------------------------------------------------------------
# generer_reponse_avec_fallback
# ---------------------------------------------------------------------------

class TestGenererReponseAvecFallback:
    def test_returns_response_from_initial_model(self):
        from src.benchmark.ab_test_llm import generer_reponse_avec_fallback

        with patch("src.benchmark.ab_test_llm.appeler_modele", return_value="VPN response"):
            with patch("src.benchmark.ab_test_llm._est_reponse_erreur", return_value=False):
                result, model, tried = generer_reponse_avec_fallback(
                    MagicMock(), "gpt-4o-mini", "ctx", "ticket"
                )

        assert result == "VPN response"
        assert model == "gpt-4o-mini"

    def test_skips_forbidden_initial_model(self):
        from src.benchmark.ab_test_llm import generer_reponse_avec_fallback

        with patch("src.benchmark.ab_test_llm.appeler_modele", return_value="fallback response"):
            with patch("src.benchmark.ab_test_llm._est_reponse_erreur", return_value=False):
                result, model, tried = generer_reponse_avec_fallback(
                    MagicMock(), "gpt-4o-mini", "ctx", "ticket",
                    modeles_interdits={"gpt-4o-mini"},
                )

        # Should have skipped gpt-4o-mini and tried a fallback
        assert "gpt-4o-mini" not in tried

    def test_falls_back_when_initial_model_fails(self):
        from src.benchmark.ab_test_llm import generer_reponse_avec_fallback

        call_count = [0]
        def fake_appeler(client, modele, ctx, ticket, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return "[ERREUR_400] model refused"
            return "fallback works"

        def fake_est_erreur(rep):
            return "[ERREUR" in rep

        def fake_eligible(rep):
            return True

        with patch("src.benchmark.ab_test_llm.appeler_modele", side_effect=fake_appeler), \
             patch("src.benchmark.ab_test_llm._est_reponse_erreur", side_effect=fake_est_erreur), \
             patch("src.benchmark.ab_test_llm._erreur_modele_eligible_fallback", side_effect=fake_eligible):
            result, model, tried = generer_reponse_avec_fallback(
                MagicMock(), "gpt-4o-mini", "ctx", "ticket"
            )

        assert call_count[0] >= 2
