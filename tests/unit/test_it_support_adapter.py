"""Unit tests for the ITSupportAdapter (wraps maestro.lancer_agent)."""
from __future__ import annotations

from unittest.mock import patch

from src.bibops.adapters.it_support import ITSupportAdapter


def _adapter() -> ITSupportAdapter:
    return ITSupportAdapter(model="phi3:test", max_iterations=2, default_context="ctx")


class TestSuccessPath:
    def test_returns_normalized_response(self):
        adapter = _adapter()
        adapter._tools = []  # bypass _ensure_loaded
        adapter._lancer = lambda **kwargs: {
            "reponse_finale": "voici la réponse",
            "trace": {"tool_calls": [{"name": "kb"}], "outcome": "ok"},
            "run_id": "r1",
        }
        out = adapter.query("ticket text")
        assert out.text == "voici la réponse"
        assert out.metadata["model"] == "phi3:test"
        assert out.metadata["run_id"] == "r1"
        assert out.metadata["tool_calls"] == 1
        assert out.metadata["outcome"] == "ok"
        assert out.latency_ms >= 0
        assert not out.is_error

    def test_uses_default_context_when_none_provided(self):
        adapter = _adapter()
        adapter._tools = []
        observed = {}

        def stub(**kwargs):
            observed.update(kwargs)
            return {"reponse_finale": "ok", "trace": {}}

        adapter._lancer = stub
        adapter.query("hello")
        assert observed["contexte"] == "ctx"

    def test_explicit_context_takes_precedence(self):
        adapter = _adapter()
        adapter._tools = []
        observed = {}

        def stub(**kwargs):
            observed.update(kwargs)
            return {"reponse_finale": "ok", "trace": {}}

        adapter._lancer = stub
        adapter.query("hello", context="explicit")
        assert observed["contexte"] == "explicit"

    def test_handles_string_result_fallback(self):
        adapter = _adapter()
        adapter._tools = []
        adapter._lancer = lambda **kwargs: "plain string response"
        out = adapter.query("hi")
        assert out.text == "plain string response"
        assert out.metadata["model"] == "phi3:test"


class TestErrorPath:
    def test_lancer_exception_returns_adapter_error(self):
        adapter = _adapter()
        adapter._tools = []

        def boom(**kwargs):
            raise RuntimeError("ollama down")

        adapter._lancer = boom
        out = adapter.query("hi")
        assert out.is_error
        assert "ollama down" in out.text
        assert out.metadata["model"] == "phi3:test"


class TestLazyLoading:
    def test_constructor_does_not_import_maestro(self):
        # If imports were eager, constructing the adapter would crash any
        # environment without Ollama installed.
        adapter = ITSupportAdapter()
        assert adapter._tools is None
        assert adapter._lancer is None

    def test_ensure_loaded_imports_on_demand(self):
        adapter = _adapter()
        with patch("src.agent.tools.chercher_dans_kb"), \
             patch("src.agent.tools.chercher_documentation_technique"), \
             patch("src.agent.tools.verifier_statut_serveur"), \
             patch("src.agent.maestro.lancer_agent") as mock_lancer:
            mock_lancer.return_value = {"reponse_finale": "ok", "trace": {}}
            adapter._ensure_loaded()
            assert adapter._tools is not None
            assert adapter._lancer is not None
