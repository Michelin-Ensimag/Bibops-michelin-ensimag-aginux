"""Tests for src.bibops.benchmark.core — pure helpers + mocked ollama benchmark loop."""
from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helpers (no LLM needed)
# ---------------------------------------------------------------------------

class TestIsNonInteractiveMode:
    def test_env_var_set(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")
        from src.bibops.benchmark.core import _is_non_interactive_mode
        assert _is_non_interactive_mode() is True

    def test_env_var_not_set(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_NON_INTERACTIVE", raising=False)
        from src.bibops.benchmark.core import _is_non_interactive_mode
        # stdin may or may not be tty, just check it returns a bool
        result = _is_non_interactive_mode()
        assert isinstance(result, bool)


class TestDefaultFeedbackChoice:
    def test_default_is_two(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_DEFAULT_FEEDBACK", raising=False)
        from src.bibops.benchmark.core import _default_feedback_choice
        assert _default_feedback_choice() == "2"

    def test_env_var_key(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_DEFAULT_FEEDBACK", "1")
        from src.bibops.benchmark.core import _default_feedback_choice
        assert _default_feedback_choice() == "1"

    def test_env_var_label_utile(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_DEFAULT_FEEDBACK", "Utile")
        from src.bibops.benchmark.core import _default_feedback_choice
        assert _default_feedback_choice() == "1"

    def test_invalid_env_falls_back_to_two(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_DEFAULT_FEEDBACK", "invalid")
        from src.bibops.benchmark.core import _default_feedback_choice
        assert _default_feedback_choice() == "2"


class TestLireChamp:
    def test_reads_from_dict(self):
        from src.bibops.benchmark.core import _lire_champ
        assert _lire_champ({"key": "value"}, "key") == "value"

    def test_missing_dict_key_returns_none(self):
        from src.bibops.benchmark.core import _lire_champ
        assert _lire_champ({}, "missing") is None

    def test_reads_from_object(self):
        from src.bibops.benchmark.core import _lire_champ
        obj = SimpleNamespace(name="test")
        assert _lire_champ(obj, "name") == "test"

    def test_missing_object_attr_returns_none(self):
        from src.bibops.benchmark.core import _lire_champ
        obj = SimpleNamespace()
        assert _lire_champ(obj, "missing") is None


class TestExtraireTexteReponse:
    def test_dict_format(self):
        from src.bibops.benchmark.core import extraire_texte_reponse
        resp = {"message": {"content": "Hello world"}}
        assert extraire_texte_reponse(resp) == "Hello world"

    def test_object_format(self):
        from src.bibops.benchmark.core import extraire_texte_reponse
        msg = SimpleNamespace(content="Test content")
        resp = SimpleNamespace(message=msg)
        assert extraire_texte_reponse(resp) == "Test content"

    def test_missing_message_returns_empty(self):
        from src.bibops.benchmark.core import extraire_texte_reponse
        assert extraire_texte_reponse({}) == ""

    def test_non_string_content_returns_empty(self):
        from src.bibops.benchmark.core import extraire_texte_reponse
        assert extraire_texte_reponse({"message": {"content": None}}) == ""


class TestExtraireCompteursTokens:
    def test_ollama_native_format(self):
        from src.bibops.benchmark.core import extraire_compteurs_tokens
        resp = {"prompt_eval_count": 10, "eval_count": 20}
        tokens, source = extraire_compteurs_tokens(resp)
        assert tokens == 30
        assert source == "ollama_native"

    def test_usage_total_tokens(self):
        from src.bibops.benchmark.core import extraire_compteurs_tokens
        resp = {"usage": {"total_tokens": 50}}
        tokens, source = extraire_compteurs_tokens(resp)
        assert tokens == 50
        assert source == "usage_total_tokens"

    def test_usage_prompt_plus_completion(self):
        from src.bibops.benchmark.core import extraire_compteurs_tokens
        resp = {"usage": {"prompt_tokens": 15, "completion_tokens": 25}}
        tokens, source = extraire_compteurs_tokens(resp)
        assert tokens == 40
        assert source == "usage_prompt_plus_completion"

    def test_no_token_info(self):
        from src.bibops.benchmark.core import extraire_compteurs_tokens
        tokens, source = extraire_compteurs_tokens({})
        assert tokens is None
        assert source == "native_tokens_absents"


class TestDemanderFeedbackUtilisateur:
    def test_non_interactive_returns_default(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")
        monkeypatch.setenv("BIBOPS_DEFAULT_FEEDBACK", "2")
        from src.bibops.benchmark.core import demander_feedback_utilisateur
        result = demander_feedback_utilisateur()
        assert result == "Partiellement utile"


class TestRunBenchmark:
    """Test run_benchmark with mocked ollama and a temp CSV."""

    def _make_csv(self, tmp_path: Path) -> Path:
        csv_file = tmp_path / "tickets.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "ticket", "contexte"])
            writer.writeheader()
            writer.writerow({
                "id": "T01",
                "ticket": "Mon VPN ne marche pas",
                "contexte": "Tu es un assistant IT.",
            })
        return csv_file

    def test_run_benchmark_writes_json(self, tmp_path, monkeypatch):
        csv_file = self._make_csv(tmp_path)
        output_json = tmp_path / "out.json"
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")
        monkeypatch.setenv("BIBOPS_DEFAULT_FEEDBACK", "2")

        fake_response = {
            "message": {"content": "Redémarrez le client VPN."},
            "prompt_eval_count": 10,
            "eval_count": 20,
        }

        with patch("src.bibops.benchmark.core.INPUT_CSV", str(csv_file)), \
             patch("src.bibops.benchmark.core.OUTPUT_JSON", str(output_json)), \
             patch("src.bibops.benchmark.core.ollama.chat", return_value=fake_response):
            from src.bibops.benchmark.core import run_benchmark
            run_benchmark(model_names=["phi3:latest"])

        import json as _json
        assert output_json.exists()
        data = _json.loads(output_json.read_text())
        assert len(data) == 1
        assert data[0]["modele"] == "phi3:latest"

    def test_run_benchmark_max_tickets_env_valid(self, tmp_path, monkeypatch):
        csv_file = self._make_csv(tmp_path)
        output_json = tmp_path / "out.json"
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")
        monkeypatch.setenv("BIBOPS_MAX_TICKETS", "1")

        fake_response = {"message": {"content": "ok"}, "prompt_eval_count": 5, "eval_count": 5}

        with patch("src.bibops.benchmark.core.INPUT_CSV", str(csv_file)), \
             patch("src.bibops.benchmark.core.OUTPUT_JSON", str(output_json)), \
             patch("src.bibops.benchmark.core.ollama.chat", return_value=fake_response):
            from src.bibops.benchmark.core import run_benchmark
            run_benchmark(model_names=["phi3:latest"])

        import json as _json
        data = _json.loads(output_json.read_text())
        assert len(data) == 1

    def test_run_benchmark_handles_ollama_error(self, tmp_path, monkeypatch):
        csv_file = self._make_csv(tmp_path)
        output_json = tmp_path / "out.json"
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")

        with patch("src.bibops.benchmark.core.INPUT_CSV", str(csv_file)), \
             patch("src.bibops.benchmark.core.OUTPUT_JSON", str(output_json)), \
             patch("src.bibops.benchmark.core.ollama.chat", side_effect=RuntimeError("Ollama unavailable")):
            from src.bibops.benchmark.core import run_benchmark
            run_benchmark(model_names=["phi3:latest"])

        import json as _json
        data = _json.loads(output_json.read_text())
        assert len(data) == 1
        assert data[0]["reponse"] == "ERREUR"
