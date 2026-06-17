"""Unit tests for the Apple MLX chat provider.

MLX is served via an OpenAI-compatible HTTP server (mlx_lm.server), so the
`mlx` provider reuses the OpenAI client path. The official mlx_lm.server does
NOT enforce response_format/JSON mode, so the maestro must tolerate JSON that
arrives wrapped in prose or ```json fences.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# config — mlx provider is a first-class, validated provider
# ---------------------------------------------------------------------------

class TestMlxConfig:
    def test_normalize_provider_accepts_mlx(self):
        from src.common.config import normalize_provider

        assert normalize_provider("mlx") == "mlx"
        assert normalize_provider("MLX") == "mlx"

    def test_validate_chat_model_accepts_mlx_model(self):
        from src.common.config import SUPPORTED_MLX_MODELS, validate_chat_model

        model = SUPPORTED_MLX_MODELS[0]
        assert validate_chat_model("mlx", model) == ("mlx", model)

    def test_validate_chat_model_rejects_unknown_mlx_model(self):
        from src.common.config import validate_chat_model

        with pytest.raises(ValueError):
            validate_chat_model("mlx", "phi3:latest")

    def test_available_models_for_provider_returns_mlx_models(self):
        from src.common.config import SUPPORTED_MLX_MODELS, available_models_for_provider

        assert available_models_for_provider("mlx") == SUPPORTED_MLX_MODELS

    def test_mistral_7b_is_a_supported_mlx_model(self):
        from src.common.config import SUPPORTED_MLX_MODELS

        assert "mlx-community/Mistral-7B-Instruct-v0.3-4bit" in SUPPORTED_MLX_MODELS


# ---------------------------------------------------------------------------
# llm_clients — get_mlx_client builds an OpenAI client at the MLX server URL
# ---------------------------------------------------------------------------

class TestGetMlxClient:
    def test_constructs_openai_client_with_mlx_url(self, monkeypatch):
        import src.common.llm_clients as llm_clients

        monkeypatch.setattr(llm_clients, "_mlx_client_cache", None, raising=False)
        with patch("src.common.llm_clients.OpenAI") as MockOpenAI:
            llm_clients.get_mlx_client()
        kwargs = MockOpenAI.call_args.kwargs
        assert kwargs["base_url"] == llm_clients.MLX_BASE_URL
        assert kwargs["max_retries"] == 0

    def test_returns_singleton(self, monkeypatch):
        import src.common.llm_clients as llm_clients

        monkeypatch.setattr(llm_clients, "_mlx_client_cache", None, raising=False)
        with patch("src.common.llm_clients.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = MagicMock(name="client")
            c1 = llm_clients.get_mlx_client()
            c2 = llm_clients.get_mlx_client()
        assert c1 is c2
        assert MockOpenAI.call_count == 1


# ---------------------------------------------------------------------------
# chat_models — provider="mlx" dispatches through the MLX OpenAI client
# ---------------------------------------------------------------------------

class TestCallChatModelMlx:
    def _openai_response(self, text="ok", prompt=3, completion=7):
        message = SimpleNamespace(content=text)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)
        return SimpleNamespace(choices=[choice], usage=usage)

    def test_mlx_provider_calls_mlx_client(self):
        from src.common.chat_models import ChatModelResponse, call_chat_model

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._openai_response("mlx answer")

        with patch("src.common.chat_models.get_mlx_client", return_value=mock_client):
            result = call_chat_model(
                provider="mlx",
                model="mlx-community/Mistral-7B-Instruct-v0.3-4bit",
                messages=[{"role": "user", "content": "hi"}],
                validate=False,
            )
        assert isinstance(result, ChatModelResponse)
        assert result.text == "mlx answer"
        assert result.prompt_tokens == 3
        assert result.completion_tokens == 7

    def test_mlx_provider_does_not_touch_copilot_client(self):
        from src.common.chat_models import call_chat_model

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._openai_response()

        with patch("src.common.chat_models.get_mlx_client", return_value=mock_client), \
             patch("src.common.chat_models.get_copilot_client") as mock_copilot:
            call_chat_model(
                provider="mlx",
                model="mlx-community/Mistral-7B-Instruct-v0.3-4bit",
                messages=[{"role": "user", "content": "hi"}],
                validate=False,
            )
        mock_copilot.assert_not_called()


# ---------------------------------------------------------------------------
# maestro — mlx client wiring + JSON-mode-tolerant parsing
# ---------------------------------------------------------------------------

def _fake_llm_client(content: str):
    """OpenAI-shaped client whose completion returns *content*."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2)
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[choice], usage=usage)
    return client


class TestMaestroMlxClient:
    def test_make_client_mlx_returns_mlx_client(self):
        from src.agent import maestro

        sentinel = object()
        with patch("src.agent.maestro.get_mlx_client", return_value=sentinel):
            assert maestro._make_client("mlx") is sentinel


class TestCallLlmJsonTolerance:
    def test_parses_clean_json_object(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client('{"final_answer": "tout est ok"}')
        result = _call_llm(client, "m", [{"role": "user", "content": "x"}], AgentDecision)
        assert result.final_answer == "tout est ok"

    def test_recovers_from_markdown_fenced_json(self):
        # The official mlx_lm.server ignores response_format, so a model may wrap
        # its JSON in prose / ```json fences. The maestro must still parse it.
        from src.agent.maestro import AgentDecision, _call_llm

        content = 'Voici ma decision:\n```json\n{"tool": "verifier_statut_serveur", "argument": "VPN"}\n```'
        client = _fake_llm_client(content)
        result = _call_llm(client, "m", [{"role": "user", "content": "x"}], AgentDecision)
        assert result.tool == "verifier_statut_serveur"
        assert result.argument == "VPN"

    def test_raises_when_no_json_present(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client("désolé, je n'ai aucune sortie structurée ici")
        with pytest.raises(Exception):
            _call_llm(client, "m", [{"role": "user", "content": "x"}], AgentDecision)


# ---------------------------------------------------------------------------
# maestro — Mistral chat-template normalization (mlx path only)
#
# Mistral instruct templates (as served by mlx_lm.server) require a
# conversation that starts with `user` and strictly alternates user/assistant.
# A standalone `system` message or consecutive same-role messages raise
# "Conversation roles must alternate user/assistant/...".
# ---------------------------------------------------------------------------

class TestMistralMessageNormalization:
    def test_folds_leading_system_into_first_user(self):
        from src.agent.maestro import _normalize_messages_for_mistral

        out = _normalize_messages_for_mistral(
            [{"role": "system", "content": "SYS"}, {"role": "user", "content": "hi"}]
        )
        assert out[0]["role"] == "user"
        assert "SYS" in out[0]["content"] and "hi" in out[0]["content"]
        assert all(m["role"] != "system" for m in out)

    def test_collapses_consecutive_user_messages(self):
        from src.agent.maestro import _normalize_messages_for_mistral

        out = _normalize_messages_for_mistral([
            {"role": "system", "content": "S"},
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
            {"role": "user", "content": "d"},
        ])
        assert [m["role"] for m in out] == ["user", "assistant", "user"]
        assert "c" in out[-1]["content"] and "d" in out[-1]["content"]

    def test_promotes_orphan_system_to_user(self):
        from src.agent.maestro import _normalize_messages_for_mistral

        out = _normalize_messages_for_mistral([{"role": "system", "content": "only-sys"}])
        assert out == [{"role": "user", "content": "only-sys"}]

    def test_coerces_unknown_role_to_user(self):
        # Mistral only accepts user/assistant; any other role (e.g. "tool") must be coerced.
        from src.agent.maestro import _normalize_messages_for_mistral

        out = _normalize_messages_for_mistral([
            {"role": "user", "content": "x"},
            {"role": "tool", "content": "y"},
        ])
        assert all(m["role"] in {"user", "assistant"} for m in out)
        assert "y" in out[-1]["content"]

    def test_call_llm_mlx_normalizes_away_system_role(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client('{"final_answer": "ok"}')
        _call_llm(
            client,
            "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
            [{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}],
            AgentDecision,
            provider="mlx",
        )
        sent = client.chat.completions.create.call_args.kwargs["messages"]
        assert sent[0]["role"] == "user"
        assert all(m["role"] != "system" for m in sent)

    def test_call_llm_non_mlx_keeps_system_role(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client('{"final_answer": "ok"}')
        _call_llm(
            client,
            "gpt-4o",
            [{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}],
            AgentDecision,
            provider="copilot",
        )
        sent = client.chat.completions.create.call_args.kwargs["messages"]
        assert sent[0]["role"] == "system"


# ---------------------------------------------------------------------------
# maestro — prose-answer fallback (mlx path only)
#
# The official mlx_lm.server does not enforce the AgentDecision schema, so a
# weaker local model often just answers in prose (sometimes JSON-string-encoded)
# instead of emitting the {tool, argument, final_answer} object. Rather than
# fail the turn, the mlx path treats that prose as the final answer.
# ---------------------------------------------------------------------------

class TestMlxProseFallback:
    def test_bare_json_string_becomes_final_answer(self):
        from src.agent.maestro import AgentDecision, _call_llm

        # A JSON *string* (valid JSON, but not an AgentDecision object).
        client = _fake_llm_client('"Voici la procedure: etape 1, etape 2."')
        result = _call_llm(client, "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
                           [{"role": "user", "content": "x"}], AgentDecision, provider="mlx")
        assert result.tool is None
        assert result.final_answer == "Voici la procedure: etape 1, etape 2."

    def test_plain_prose_becomes_final_answer(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client("Redemarrez le poste puis escaladez au niveau 2.")
        result = _call_llm(client, "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
                           [{"role": "user", "content": "x"}], AgentDecision, provider="mlx")
        assert result.final_answer == "Redemarrez le poste puis escaladez au niveau 2."

    def test_valid_tool_object_still_parsed_not_treated_as_prose(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client('{"tool": "verifier_statut_serveur", "argument": "VPN"}')
        result = _call_llm(client, "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
                           [{"role": "user", "content": "x"}], AgentDecision, provider="mlx")
        assert result.tool == "verifier_statut_serveur"
        assert result.final_answer is None

    def test_non_mlx_provider_still_raises_on_unparseable_prose(self):
        from src.agent.maestro import AgentDecision, _call_llm

        client = _fake_llm_client("just prose, no json at all")
        with pytest.raises(Exception):
            _call_llm(client, "gpt-4o", [{"role": "user", "content": "x"}], AgentDecision, provider="copilot")
