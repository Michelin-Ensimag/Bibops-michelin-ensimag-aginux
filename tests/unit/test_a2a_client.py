"""Unit tests for the A2A client (request shape, auth, response parsing)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.bibops.adapters.a2a_client import (
    A2AAgentInfo,
    A2AClientError,
    discover_agent,
    extract_text_from_response,
    send_message,
    send_stream_message,
)


def _agent_info(rpc_url: str = "https://demo.test/a2a/jsonrpc", variant: str = "openclaw") -> A2AAgentInfo:
    return A2AAgentInfo(
        base_url="https://demo.test",
        card_url="https://demo.test/.well-known/agent-card.json",
        rpc_url=rpc_url,
        protocol_variant=variant,
        name="demo",
        description="",
        model="claude-3",
        skills=[],
        capabilities={},
        revealed=True,
        raw_card={},
    )


def _mock_post_response(json_payload: dict, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_payload
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestExtractText:
    def test_parts_in_result(self):
        payload = {"result": {"parts": [{"text": "hello"}, {"text": "world"}]}}
        assert extract_text_from_response(payload) == "hello\n\nworld"

    def test_message_parts_under_status(self):
        payload = {
            "result": {
                "status": {"message": {"parts": [{"text": "diagnostic"}]}}
            }
        }
        assert "diagnostic" in extract_text_from_response(payload)

    def test_artifacts_with_parts(self):
        payload = {"result": {"artifacts": [{"parts": [{"text": "a"}, {"text": "b"}]}]}}
        assert extract_text_from_response(payload) == "a\n\nb"

    def test_falls_back_to_json_dump_when_no_parts(self):
        payload = {"result": {"unexpected": "shape"}}
        out = extract_text_from_response(payload)
        assert "unexpected" in out

    def test_returns_empty_when_result_is_not_dict(self):
        assert extract_text_from_response({"result": "string-not-dict"}) == ""


class TestSendMessage:
    def test_request_carries_jsonrpc_envelope(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = _mock_post_response({"result": {"parts": [{"text": "ok"}]}})
            send_message(agent, "Bonjour")
        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs["json"]
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "message/send"
        assert body["params"]["message"]["role"] == "user"
        assert body["params"]["message"]["parts"][0]["text"] == "Bonjour"
        # openclaw variant uses {kind: "text", text: ...}
        assert body["params"]["message"]["parts"][0].get("kind") == "text"

    def test_factchecker_variant_omits_kind_field(self):
        agent = _agent_info(variant="fact_checker")
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = _mock_post_response({"result": {"parts": [{"text": "ok"}]}})
            send_message(agent, "ping")
        body = mock_post.call_args.kwargs["json"]
        assert "kind" not in body["params"]["message"]["parts"][0]

    def test_basic_auth_passed_when_credentials_provided(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = _mock_post_response({"result": {"parts": [{"text": "ok"}]}})
            send_message(agent, "ping", username="alice", password="secret")
        auth = mock_post.call_args.kwargs["auth"]
        # HTTPBasicAuth instance carries credentials.
        assert auth is not None
        assert getattr(auth, "username", None) == "alice"
        assert getattr(auth, "password", None) == "secret"

    def test_no_auth_when_credentials_absent(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = _mock_post_response({"result": {"parts": [{"text": "ok"}]}})
            send_message(agent, "ping")
        assert mock_post.call_args.kwargs["auth"] is None

    def test_network_error_returns_error_envelope(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post", side_effect=RuntimeError("DNS fail")):
            result = send_message(agent, "ping")
        assert result.error == "DNS fail"
        assert result.answer == ""
        assert result.latency_s >= 0

    def test_successful_call_returns_normalized_answer(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = _mock_post_response({"result": {"parts": [{"text": "the answer"}]}})
            result = send_message(agent, "ping")
        assert result.error == ""
        assert result.answer == "the answer"
        assert result.agent_url == agent.base_url

    def test_non_dict_response_yields_error_envelope(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = _mock_post_response(["unexpected", "list"])  # not a dict
            result = send_message(agent, "ping")
        assert "JSON-RPC response is not an object" in result.error


class TestSendStreamMessage:
    def test_stream_request_parses_sse_data_lines(self):
        agent = _agent_info()
        stream_resp = MagicMock()
        stream_resp.raise_for_status = MagicMock()
        stream_resp.iter_lines.return_value = [
            'data: {"result": {"parts": [{"text": "partial"}]}}',
            'data: {"result": {"parts": [{"text": "final"}]}}',
            "data: [DONE]",
        ]
        stream_resp.__enter__.return_value = stream_resp
        stream_resp.__exit__.return_value = False

        with patch("src.bibops.adapters.a2a_client.requests.post", return_value=stream_resp) as mock_post:
            result = send_stream_message(agent, "ping", username="alice", password="secret")

        body = mock_post.call_args.kwargs["json"]
        assert body["method"] == "message/stream"
        assert mock_post.call_args.kwargs["stream"] is True
        assert mock_post.call_args.kwargs["headers"]["Accept"] == "text/event-stream"
        assert result.error == ""
        assert "partial" in result.answer
        assert "final" in result.answer


class TestDiscovery:
    def test_discovery_succeeds_on_first_card_url(self):
        card = {
            "name": "AgentX",
            "description": "demo",
            "model": "gpt-4o",
            "skills": ["summarize"],
            "capabilities": {"streaming": True},
        }
        with patch("src.bibops.adapters.a2a_client.requests.get") as mock_get:
            mock_get.return_value = _mock_post_response(card)
            info = discover_agent("https://demo.test", timeout_s=5)
        assert info.name == "AgentX"
        assert info.model == "gpt-4o"
        assert info.skills == ["summarize"]
        assert info.protocol_variant == "openclaw"
        assert info.rpc_url.endswith("/a2a/jsonrpc")

    def test_discovery_falls_back_to_factchecker_variant(self):
        card_openclaw_404 = MagicMock()
        card_openclaw_404.raise_for_status.side_effect = RuntimeError("404")
        fc_card = _mock_post_response({"name": "fc-agent", "description": ""})

        with patch("src.bibops.adapters.a2a_client.requests.get", side_effect=[card_openclaw_404, fc_card]):
            info = discover_agent("https://demo.test", timeout_s=5)
        assert info.protocol_variant == "fact_checker"

    def test_discovery_raises_when_all_candidates_fail(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = RuntimeError("bad")
        with patch("src.bibops.adapters.a2a_client.requests.get", return_value=bad):
            with pytest.raises(A2AClientError, match="A2A discovery failed"):
                discover_agent("https://demo.test", timeout_s=1)
