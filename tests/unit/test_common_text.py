"""Unit tests for src.common.text helpers and the A/B-pipeline helpers that live in ab_test_llm."""
from __future__ import annotations

from concurrent.futures import TimeoutError as FuturesTimeoutError

import pytest

from src.common import text as T
from src.bibops.benchmark import ab_test_llm as AB
from tests._fakes.fake_openai import FakeOpenAI, make_response

# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------

class TestApiKeyLoading:
    def test_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("COPILOT_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert T.charger_copilot_api_key() == "copilot"

    def test_prefers_copilot_over_openai(self, monkeypatch):
        monkeypatch.setenv("COPILOT_API_KEY", "copilot-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        assert T.charger_copilot_api_key() == "copilot-key"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("COPILOT_API_KEY", "  k  ")
        assert T.charger_copilot_api_key() == "k"


# ---------------------------------------------------------------------------
# Message text extraction
# ---------------------------------------------------------------------------

class TestExtraireTexte:
    def test_string_content(self):
        msg = type("M", (), {"content": "hello"})()
        assert T._extraire_texte(msg) == "hello"

    def test_list_content_concatenates_text_parts(self):
        msg = type("M", (), {"content": [{"text": "a"}, {"text": "b"}, {"other": "z"}]})()
        assert T._extraire_texte(msg) == "a\nb"

    def test_falls_back_to_reasoning(self):
        msg = type("M", (), {"content": "", "reasoning": "thinking..."})()
        assert T._extraire_texte(msg) == "thinking..."

    def test_returns_placeholder_when_empty(self):
        msg = type("M", (), {"content": None})()
        assert T._extraire_texte(msg) == "[Reponse vide]"


# ---------------------------------------------------------------------------
# JSON extraction from free-form text
# ---------------------------------------------------------------------------

class TestExtractJSON:
    def test_strict_json(self):
        assert AB._extraire_json_depuis_texte('{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self):
        out = AB._extraire_json_depuis_texte('```json\n{"k": "v"}\n```')
        assert out == {"k": "v"}

    def test_json_with_leading_prose(self):
        out = AB._extraire_json_depuis_texte('Verdict: {"choix": "A"} done.')
        assert out == {"choix": "A"}

    def test_returns_none_on_no_json(self):
        assert AB._extraire_json_depuis_texte("just text, nothing here") is None

    def test_returns_none_on_empty(self):
        assert AB._extraire_json_depuis_texte("") is None

    def test_picks_first_valid_object(self):
        # Two candidates; the parser must return one valid dict.
        out = AB._extraire_json_depuis_texte('{"a": 1} and also {"b": 2}')
        assert isinstance(out, dict)


# ---------------------------------------------------------------------------
# Choice normaliser + error classifiers
# ---------------------------------------------------------------------------

class TestChoiceNormaliser:
    def test_uppercases_a_and_b(self):
        assert AB._normaliser_choix("a") == "A"
        assert AB._normaliser_choix(" B ") == "B"

    def test_rejects_other_letters(self):
        assert AB._normaliser_choix("C") is None

    def test_rejects_non_string(self):
        assert AB._normaliser_choix(None) is None
        assert AB._normaliser_choix(42) is None


class TestErrorClassifiers:
    def test_est_reponse_erreur_true(self):
        assert AB._est_reponse_erreur("[ERREUR_MODELE foo] timed out")
        assert not AB._est_reponse_erreur("normal answer")

    def test_quota_free_epuise_detection(self):
        assert AB._est_quota_free_epuise("free-models-per-day quota exceeded")
        assert not AB._est_quota_free_epuise("any other error")

    def test_message_erreur_court_humanizes_known_signatures(self):
        assert "Quota OpenRouter" in AB._message_erreur_court("free-models-per-day reached")
        assert "rate-limited" in AB._message_erreur_court("temporarily rate-limited")
        assert "Aucun endpoint" in AB._message_erreur_court("no endpoints found")
        assert "Delai depasse" in AB._message_erreur_court("timeout")
        assert "JSON" in AB._message_erreur_court("json invalide")

    def test_message_erreur_court_passes_through_unknown(self):
        assert AB._message_erreur_court("weird error") == "weird error"

    def test_eligible_fallback_for_known_transients(self):
        assert AB._erreur_modele_eligible_fallback("rate limit reached")
        assert AB._erreur_modele_eligible_fallback("timeout")
        assert AB._erreur_modele_eligible_fallback("Developer instruction is not enabled")
        assert not AB._erreur_modele_eligible_fallback("syntax error in code")


# ---------------------------------------------------------------------------
# Timeout executor
# ---------------------------------------------------------------------------

class TestExecuterAvecTimeout:
    def test_returns_result_on_success(self):
        assert AB._executer_avec_timeout(lambda: 42, timeout_s=2) == 42

    def test_raises_timeout_on_slow_function(self):
        import time
        with pytest.raises(FuturesTimeoutError):
            AB._executer_avec_timeout(lambda: time.sleep(2), timeout_s=0)


# ---------------------------------------------------------------------------
# appeler_modele — exercises the OpenAI chat path
# ---------------------------------------------------------------------------

class TestAppelerModele:
    def test_success_returns_text(self):
        client = FakeOpenAI(make_response("Bonjour"))
        out = AB.appeler_modele(client, "fake-model", "context", "ticket", timeout_s=2)
        assert out == "Bonjour"

    def test_exception_returns_error_envelope(self):
        client = FakeOpenAI(RuntimeError("upstream failed"))
        out = AB.appeler_modele(client, "fake-model", "context", "ticket", timeout_s=2)
        assert out.startswith("[ERREUR_MODELE fake-model]")
        assert "upstream failed" in out

    def test_developer_instruction_fallback(self):
        # First call raises the "Developer instruction is not enabled" signature; the
        # fallback path retries without a system message.
        calls = {"n": 0}

        def behaviour(**_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Developer instruction is not enabled")
            return make_response("retry succeeded")

        client = FakeOpenAI(behaviour)
        out = AB.appeler_modele(client, "fake-model", "context", "ticket", timeout_s=2)
        assert out == "retry succeeded"
        assert calls["n"] == 2


# ---------------------------------------------------------------------------
# Ollama-side helpers
# ---------------------------------------------------------------------------

class TestOllamaResponseHelpers:
    def test_extraire_texte_reponse_dict(self):
        rep = {"message": {"content": "ok"}}
        assert T.extraire_texte_reponse(rep) == "ok"

    def test_extraire_texte_reponse_object(self):
        msg = type("M", (), {"content": "from-attr"})()
        rep = type("R", (), {"message": msg})()
        assert T.extraire_texte_reponse(rep) == "from-attr"

    def test_extraire_texte_reponse_missing(self):
        assert T.extraire_texte_reponse({}) == ""

    def test_token_count_from_native_ollama(self):
        rep = {"prompt_eval_count": 30, "eval_count": 50}
        total, source = T.extraire_compteurs_tokens(rep)
        assert total == 80 and source == "ollama_native"

    def test_token_count_from_usage_total(self):
        rep = {"usage": {"total_tokens": 123}}
        total, source = T.extraire_compteurs_tokens(rep)
        assert total == 123 and source == "usage_total_tokens"

    def test_token_count_from_usage_split(self):
        rep = {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}
        total, source = T.extraire_compteurs_tokens(rep)
        assert total == 30 and source == "usage_prompt_plus_completion"

    def test_token_count_absent(self):
        total, source = T.extraire_compteurs_tokens({})
        assert total is None and source == "native_tokens_absents"
