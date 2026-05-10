"""Unit tests for the OpenAICompatAdapter (offline, with FakeOpenAI client)."""
from __future__ import annotations

from src.bibops.adapters.openai_compat import OpenAICompatAdapter
from tests._fakes.fake_openai import FakeOpenAI, make_response


def _adapter_with(behaviour) -> tuple[OpenAICompatAdapter, FakeOpenAI]:
    adapter = OpenAICompatAdapter.__new__(OpenAICompatAdapter)
    adapter.model = "fake-model"
    adapter.system_prompt = ""
    adapter.temperature = 0.0
    adapter.timeout = 30
    adapter.client = FakeOpenAI(behaviour)
    return adapter, adapter.client


class TestQuerySuccessPath:
    def test_returns_normalized_response(self):
        adapter, _ = _adapter_with(make_response("Hello!", prompt_tokens=12, completion_tokens=8))
        resp = adapter.query("Bonjour")
        assert resp.text == "Hello!"
        assert resp.tokens_in == 12
        assert resp.tokens_out == 8
        assert resp.latency_ms >= 0
        assert not resp.is_error
        assert resp.metadata.get("model") == "fake-model"

    def test_strips_whitespace_from_content(self):
        adapter, _ = _adapter_with(make_response("   trimmed   "))
        resp = adapter.query("x")
        assert resp.text == "trimmed"

    def test_request_includes_user_message(self):
        adapter, fake = _adapter_with(make_response("ok"))
        adapter.query("What is your name?")
        call = fake.calls[0]
        # No system_prompt + no context → only the user message
        assert [m["role"] for m in call["messages"]] == ["user"]
        assert call["messages"][0]["content"] == "What is your name?"
        assert call["model"] == "fake-model"

    def test_context_becomes_system_message_when_no_system_prompt(self):
        adapter, fake = _adapter_with(make_response("ok"))
        adapter.query("question?", context="business context")
        roles = [m["role"] for m in fake.calls[0]["messages"]]
        assert roles == ["system", "user"]
        assert fake.calls[0]["messages"][0]["content"] == "business context"

    def test_explicit_system_prompt_takes_precedence_over_context(self):
        adapter, fake = _adapter_with(make_response("ok"))
        adapter.system_prompt = "You are a pirate."
        adapter.query("anything", context="other context that should be ignored")
        sys_msg = fake.calls[0]["messages"][0]
        assert sys_msg["role"] == "system"
        assert sys_msg["content"] == "You are a pirate."


class TestQueryErrorPath:
    def test_exception_returns_adapter_error_envelope(self):
        adapter, _ = _adapter_with(RuntimeError("upstream timeout"))
        resp = adapter.query("ping")
        assert resp.is_error
        assert resp.text.startswith("[ADAPTER_ERROR]")
        assert "upstream timeout" in resp.text
        assert resp.metadata.get("error") == "upstream timeout"

    def test_error_response_keeps_latency_metric(self):
        adapter, _ = _adapter_with(RuntimeError("boom"))
        resp = adapter.query("ping")
        assert isinstance(resp.latency_ms, int)
        assert resp.latency_ms >= 0
