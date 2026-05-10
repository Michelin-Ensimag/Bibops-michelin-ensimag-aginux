"""Unit tests for src.common.llm_clients (Copilot factory + availability probe)."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

import src.common.llm_clients as llm_clients


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch):
    """Each test gets a fresh client cache."""
    monkeypatch.setattr(llm_clients, "_client_cache", None)


class TestGetCopilotClient:
    def test_constructs_openai_client_with_proxy_url(self):
        with patch("src.common.llm_clients.OpenAI") as MockOpenAI:
            llm_clients.get_copilot_client()
        kwargs = MockOpenAI.call_args.kwargs
        assert kwargs["base_url"] == llm_clients.COPILOT_BASE_URL
        assert kwargs["max_retries"] == 0

    def test_returns_singleton(self):
        with patch("src.common.llm_clients.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = MagicMock(name="client")
            c1 = llm_clients.get_copilot_client()
            c2 = llm_clients.get_copilot_client()
        assert c1 is c2
        assert MockOpenAI.call_count == 1


class TestIsCopilotAvailable:
    def test_returns_true_when_socket_connects(self):
        with patch("src.common.llm_clients.socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            assert llm_clients.is_copilot_available(timeout_s=0.1) is True

    def test_returns_false_on_connection_refused(self):
        with patch(
            "src.common.llm_clients.socket.create_connection",
            side_effect=ConnectionRefusedError(),
        ):
            assert llm_clients.is_copilot_available(timeout_s=0.1) is False

    def test_returns_false_on_timeout(self):
        with patch("src.common.llm_clients.socket.create_connection", side_effect=socket.timeout):
            assert llm_clients.is_copilot_available(timeout_s=0.1) is False

    def test_returns_false_on_unexpected_error(self):
        with patch("src.common.llm_clients.socket.create_connection", side_effect=RuntimeError("boom")):
            assert llm_clients.is_copilot_available(timeout_s=0.1) is False
