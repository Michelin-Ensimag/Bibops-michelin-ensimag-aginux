"""Unit tests for the A2AAdapter (high-level wrapper around a2a_client)."""
from __future__ import annotations

from unittest.mock import patch

from src.bibops.adapters.a2a import A2AAdapter
from src.bibops.adapters.a2a_client import A2AAgentInfo, A2AAgentResult


def _info() -> A2AAgentInfo:
    return A2AAgentInfo(
        base_url="https://demo.test",
        card_url="https://demo.test/.well-known/agent-card.json",
        rpc_url="https://demo.test/a2a/jsonrpc",
        protocol_variant="openclaw",
        name="demo-agent",
        description="",
        model="claude",
        skills=[],
        capabilities={},
        revealed=True,
        raw_card={},
    )


def _result(answer: str = "the answer", error: str = "") -> A2AAgentResult:
    return A2AAgentResult(
        agent_url="https://demo.test",
        agent_name="demo-agent",
        prompt="ping",
        answer=answer,
        latency_s=0.1,
        raw_response={"result": {}},
        error=error,
    )


class TestConfiguration:
    def test_constructor_uses_env_vars(self, monkeypatch):
        monkeypatch.setenv("EVAL_BANK_A2A_URL", "https://from-env/")
        monkeypatch.setenv("A2A_USERNAME", "envuser")
        monkeypatch.setenv("A2A_PASSWORD", "envpass")
        adapter = A2AAdapter()
        assert adapter.a2a_url == "https://from-env"
        assert adapter.username == "envuser"
        assert adapter.password == "envpass"

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("EVAL_BANK_A2A_URL", "https://from-env/")
        adapter = A2AAdapter(a2a_url="https://explicit/")
        assert adapter.a2a_url == "https://explicit"

    def test_unknown_kwargs_are_ignored(self):
        # The constructor takes **_ignored to swallow legacy kwargs.
        A2AAdapter(a2a_url="https://x", legacy_unused="value")


class TestQuery:
    def test_query_returns_agent_response_on_success(self):
        adapter = A2AAdapter(a2a_url="https://demo.test")
        with patch("src.bibops.adapters.a2a_client.discover_agent", return_value=_info()), \
             patch("src.bibops.adapters.a2a_client.send_message", return_value=_result(answer="hi there")):
            response = adapter.query("hello")
        assert response.text == "hi there"
        assert not response.is_error
        assert response.metadata["agent_name"] == "demo-agent"

    def test_query_propagates_send_error_envelope(self):
        adapter = A2AAdapter(a2a_url="https://demo.test")
        with patch("src.bibops.adapters.a2a_client.discover_agent", return_value=_info()), \
             patch("src.bibops.adapters.a2a_client.send_message", return_value=_result(answer="", error="503 service")):
            response = adapter.query("hello")
        assert response.is_error
        assert "503 service" in response.text

    def test_query_returns_discovery_error_envelope(self):
        adapter = A2AAdapter(a2a_url="https://demo.test")
        with patch("src.bibops.adapters.a2a_client.discover_agent", side_effect=RuntimeError("DNS")):
            response = adapter.query("hello")
        assert response.is_error
        assert "Discovery failed" in response.text

    def test_query_requires_url(self):
        adapter = A2AAdapter(a2a_url="")
        response = adapter.query("hello")
        assert response.is_error
        assert "requires a target URL" in response.text


class TestRateLimitRetry:
    def test_retries_when_rate_limited(self):
        adapter = A2AAdapter(a2a_url="https://demo.test", max_retries=3, rate_limit_backoff_s=0)
        rate_limited = _result(answer="[!] API rate limit reached")
        ok = _result(answer="success after retry")
        with patch("src.bibops.adapters.a2a_client.discover_agent", return_value=_info()), \
             patch("src.bibops.adapters.a2a_client.send_message", side_effect=[rate_limited, ok]) as mock_send, \
             patch("src.bibops.adapters.a2a.time.sleep") as mock_sleep:
            response = adapter.query("hello")
        assert response.text == "success after retry"
        assert mock_send.call_count == 2
        # Backoff was attempted between retries.
        assert mock_sleep.called

    def test_returns_last_response_when_all_retries_rate_limited(self):
        adapter = A2AAdapter(a2a_url="https://demo.test", max_retries=2, rate_limit_backoff_s=0)
        rate_limited = _result(answer="API rate limit reached")
        with patch("src.bibops.adapters.a2a_client.discover_agent", return_value=_info()), \
             patch("src.bibops.adapters.a2a_client.send_message", return_value=rate_limited), \
             patch("src.bibops.adapters.a2a.time.sleep"):
            response = adapter.query("hello")
        assert "rate limit" in response.text.lower()
        assert response.metadata.get("rate_limited") is True


class TestLifecycle:
    def test_warmup_triggers_discovery(self):
        adapter = A2AAdapter(a2a_url="https://demo.test")
        with patch("src.bibops.adapters.a2a_client.discover_agent", return_value=_info()) as mock:
            adapter.warmup()
        assert mock.called

    def test_teardown_clears_cached_agent_info(self):
        adapter = A2AAdapter(a2a_url="https://demo.test")
        with patch("src.bibops.adapters.a2a_client.discover_agent", return_value=_info()):
            adapter.warmup()
        assert adapter._agent_info is not None
        adapter.teardown()
        assert adapter._agent_info is None
