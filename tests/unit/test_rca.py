"""Unit tests for src.bibops.evaluation.rca — RCAEngine."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.bibops.evaluation.rca import RCAEngine


def _ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


class TestRCAEngine:
    def test_extracts_cause_and_keyword_lines_from_response(self):
        raw = "Some preamble\nCAUSE : VPN issue detected\nMOT-CLÉ : VPN\nTrailing text"
        with patch("src.bibops.evaluation.rca.ollama.chat", return_value=_ollama_response(raw)):
            engine = RCAEngine(model="phi3:latest")
            result = engine.analyser_cause_racine("Je ne peux pas me connecter au VPN")

        assert "CAUSE" in result.upper()
        assert "VPN" in result

    def test_returns_full_content_when_no_cause_keyword_lines(self):
        raw = "The system seems fine. No issues found."
        with patch("src.bibops.evaluation.rca.ollama.chat", return_value=_ollama_response(raw)):
            engine = RCAEngine(model="phi3:latest")
            result = engine.analyser_cause_racine("Random ticket")

        assert result == raw

    def test_returns_error_message_on_ollama_exception(self):
        with patch("src.bibops.evaluation.rca.ollama.chat", side_effect=RuntimeError("connection refused")):
            engine = RCAEngine(model="phi3:latest")
            result = engine.analyser_cause_racine("Test ticket")

        assert "Erreur diagnostic" in result
        assert "connection refused" in result

    def test_mot_cle_variant_without_accent_is_extracted(self):
        raw = "MOT-CLE : Outlook"
        with patch("src.bibops.evaluation.rca.ollama.chat", return_value=_ollama_response(raw)):
            engine = RCAEngine()
            result = engine.analyser_cause_racine("Mail problem")

        assert "MOT-CLE" in result.upper() or "Outlook" in result
