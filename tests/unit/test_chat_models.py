"""Unit tests for src.common.chat_models — provider-aware chat dispatch."""
from __future__ import annotations

from concurrent.futures import TimeoutError as FuturesTimeoutError
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.common.chat_models import (
    ChatModelResponse,
    _extract_ollama_text,
    _extract_ollama_token_usage,
    _extract_openai_text,
    _extract_openai_token_usage,
    call_chat_model,
)


class TestExtractOllamaText:
    def test_extracts_text_from_dict_response(self):
        response = {"message": {"content": "hello world"}}
        assert _extract_ollama_text(response) == "hello world"

    def test_extracts_text_from_object_with_dict_message(self):
        response = SimpleNamespace(message={"content": "obj+dict"})
        assert _extract_ollama_text(response) == "obj+dict"

    def test_extracts_text_from_object_with_object_message(self):
        message = SimpleNamespace(content="nested object")
        response = SimpleNamespace(message=message)
        assert _extract_ollama_text(response) == "nested object"

    def test_returns_empty_when_content_is_none(self):
        assert _extract_ollama_text({"message": {"content": None}}) == ""

    def test_returns_empty_when_message_is_missing(self):
        assert _extract_ollama_text({}) == ""

    def test_returns_empty_when_content_is_not_string(self):
        assert _extract_ollama_text({"message": {"content": 123}}) == ""


class TestExtractOllamaTokenUsage:
    def test_extracts_counts_from_dict(self):
        response = {"prompt_eval_count": 10, "eval_count": 20}
        assert _extract_ollama_token_usage(response) == (10, 20)

    def test_extracts_counts_from_object(self):
        response = SimpleNamespace(prompt_eval_count=5, eval_count=15)
        assert _extract_ollama_token_usage(response) == (5, 15)

    def test_returns_zeros_when_fields_missing_from_dict(self):
        assert _extract_ollama_token_usage({}) == (0, 0)

    def test_returns_zeros_when_values_are_not_int(self):
        response = {"prompt_eval_count": "ten", "eval_count": None}
        assert _extract_ollama_token_usage(response) == (0, 0)


class TestExtractOpenAIText:
    def test_extracts_text_from_valid_response(self):
        message = SimpleNamespace(content="copilot answer")
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        assert _extract_openai_text(response) == "copilot answer"

    def test_returns_empty_on_access_exception(self):
        assert _extract_openai_text(object()) == ""

    def test_returns_empty_when_content_is_not_string(self):
        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        assert _extract_openai_text(response) == ""


class TestExtractOpenAITokenUsage:
    def test_extracts_counts_from_usage_object(self):
        usage = SimpleNamespace(prompt_tokens=8, completion_tokens=16)
        response = SimpleNamespace(usage=usage)
        assert _extract_openai_token_usage(response) == (8, 16)

    def test_returns_zeros_when_usage_is_none(self):
        assert _extract_openai_token_usage(SimpleNamespace(usage=None)) == (0, 0)

    def test_returns_zeros_when_token_fields_are_not_int(self):
        usage = SimpleNamespace(prompt_tokens="many", completion_tokens=None)
        assert _extract_openai_token_usage(SimpleNamespace(usage=usage)) == (0, 0)


class TestCallChatModel:
    def _ollama_response(self, text="ok", prompt=5, completion=10):
        return {"message": {"content": text}, "prompt_eval_count": prompt, "eval_count": completion}

    def _copilot_response(self, text="ok", prompt=4, completion=8):
        message = SimpleNamespace(content=text)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)
        return SimpleNamespace(choices=[choice], usage=usage)

    def test_ollama_returns_chat_model_response(self):
        with patch("src.common.chat_models.ollama.chat", return_value=self._ollama_response("answer")):
            result = call_chat_model(
                provider="ollama",
                model="phi3:latest",
                messages=[{"role": "user", "content": "hi"}],
                validate=False,
            )
        assert isinstance(result, ChatModelResponse)
        assert result.text == "answer"
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 10

    def test_ollama_no_timeout_calls_ollama_directly(self):
        with patch("src.common.chat_models.ollama.chat", return_value=self._ollama_response("direct")) as mock_chat:
            result = call_chat_model(
                provider="ollama",
                model="phi3:latest",
                messages=[{"role": "user", "content": "hi"}],
                timeout=None,
                validate=False,
            )
        mock_chat.assert_called_once()
        assert result.text == "direct"

    def test_ollama_timeout_uses_executor(self):
        with patch("src.common.chat_models.ThreadPoolExecutor") as MockExecutor:
            instance = MagicMock()
            MockExecutor.return_value = instance
            future = MagicMock()
            instance.submit.return_value = future
            future.result.return_value = self._ollama_response("via-executor")

            result = call_chat_model(
                provider="ollama",
                model="phi3:latest",
                messages=[{"role": "user", "content": "hi"}],
                timeout=10,
                validate=False,
            )
        future.result.assert_called_once_with(timeout=10)
        assert result.text == "via-executor"

    def test_ollama_timeout_raises_timeout_error_on_futures_timeout(self):
        with patch("src.common.chat_models.ThreadPoolExecutor") as MockExecutor:
            instance = MagicMock()
            MockExecutor.return_value = instance
            future = MagicMock()
            instance.submit.return_value = future
            future.result.side_effect = FuturesTimeoutError()

            with pytest.raises(TimeoutError, match="Ollama chat timeout after 1s"):
                call_chat_model(
                    provider="ollama",
                    model="phi3:latest",
                    messages=[{"role": "user", "content": "hi"}],
                    timeout=1,
                    validate=False,
                )

    def test_copilot_provider_calls_openai_client(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._copilot_response("gpt answer")

        with patch("src.common.chat_models.get_copilot_client", return_value=mock_client):
            result = call_chat_model(
                provider="copilot",
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
                validate=False,
            )
        assert result.text == "gpt answer"
        assert result.prompt_tokens == 4
        assert result.completion_tokens == 8

    def test_copilot_timeout_forwarded_to_client(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._copilot_response()

        with patch("src.common.chat_models.get_copilot_client", return_value=mock_client):
            call_chat_model(
                provider="copilot",
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
                timeout=30,
                validate=False,
            )
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["timeout"] == 30

    def test_copilot_no_timeout_omits_timeout_kwarg(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._copilot_response()

        with patch("src.common.chat_models.get_copilot_client", return_value=mock_client):
            call_chat_model(
                provider="copilot",
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
                timeout=None,
                validate=False,
            )
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "timeout" not in kwargs
