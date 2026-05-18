"""Unit tests for the A2A client (request shape, auth, response parsing)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.bibops.adapters.a2a_client import (
    A2AAgentInfo,
    A2AClientError,
    A2AFactChecker,
    _clean_base_url,
    _decode_sse_data_lines,
    _extract_capabilities,
    _extract_skills,
    _extract_text_from_stream_events,
    _find_first_key,
    _is_revealed,
    _resolve_rpc_url,
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


class TestCleanBaseUrl:
    def test_strips_trailing_slash(self):
        assert _clean_base_url("https://example.com/") == "https://example.com"

    def test_strips_whitespace(self):
        assert _clean_base_url("  https://example.com  ") == "https://example.com"

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            _clean_base_url("")

    def test_raises_on_whitespace_only(self):
        with pytest.raises(ValueError):
            _clean_base_url("   ")


class TestFindFirstKey:
    def test_finds_key_in_flat_dict(self):
        assert _find_first_key({"model": "gpt-4o"}, {"model"}) == "gpt-4o"

    def test_finds_key_case_insensitively(self):
        assert _find_first_key({"Model": "gpt-4o"}, {"model"}) == "gpt-4o"

    def test_finds_key_nested_in_dict(self):
        payload = {"capabilities": {"model": "ollama-phi3"}}
        assert _find_first_key(payload, {"model"}) == "ollama-phi3"

    def test_finds_key_inside_list(self):
        payload = [{"model": "phi3:latest"}]
        assert _find_first_key(payload, {"model"}) == "phi3:latest"

    def test_returns_none_when_key_not_found(self):
        assert _find_first_key({"name": "agent"}, {"model"}) is None

    def test_skips_empty_string_values(self):
        payload = {"model": "", "llm": "fallback"}
        assert _find_first_key(payload, {"model", "llm"}) == "fallback"


class TestExtractSkills:
    def test_extracts_id_from_skill_dicts(self):
        card = {"skills": [{"id": "summarize"}, {"id": "translate"}]}
        assert _extract_skills(card) == ["summarize", "translate"]

    def test_extracts_name_when_id_missing(self):
        card = {"skills": [{"name": "chat"}]}
        assert _extract_skills(card) == ["chat"]

    def test_extracts_plain_string_skills(self):
        card = {"skills": ["rag", "search"]}
        assert _extract_skills(card) == ["rag", "search"]

    def test_uses_description_when_no_id_or_name(self):
        card = {"skills": [{"description": "A very long description of skill X"}]}
        result = _extract_skills(card)
        assert len(result) == 1
        assert "description of skill" in result[0]

    def test_returns_empty_list_when_no_skills(self):
        assert _extract_skills({}) == []

    def test_falls_back_to_capabilities_skills(self):
        card = {"capabilities": {"skills": [{"id": "nested-skill"}]}}
        assert _extract_skills(card) == ["nested-skill"]


class TestExtractCapabilities:
    def test_returns_capabilities_dict(self):
        card = {"capabilities": {"streaming": True}}
        assert _extract_capabilities(card) == {"streaming": True}

    def test_returns_empty_dict_when_missing(self):
        assert _extract_capabilities({}) == {}

    def test_returns_empty_dict_when_not_a_dict(self):
        assert _extract_capabilities({"capabilities": ["list"]}) == {}


class TestIsRevealed:
    def test_revealed_when_model_present(self):
        assert _is_revealed("gpt-4o", [], {}) is True

    def test_revealed_when_specific_skills_present(self):
        assert _is_revealed(None, ["rag", "summarize"], {}) is True

    def test_not_revealed_for_generic_skills_only(self):
        assert _is_revealed(None, ["chat"], {}) is False

    def test_revealed_when_card_contains_claude_marker(self):
        card = {"info": "uses claude-3-sonnet internally"}
        assert _is_revealed(None, [], card) is True

    def test_revealed_when_card_contains_gpt_marker(self):
        card = {"backend": "gpt-4o"}
        assert _is_revealed(None, [], card) is True

    def test_not_revealed_for_empty_card_no_model_no_skills(self):
        assert _is_revealed(None, [], {}) is False


class TestResolveRpcUrl:
    def test_uses_advertised_absolute_url(self):
        card = {"url": "https://custom.test/rpc"}
        result = _resolve_rpc_url("https://demo.test", "https://demo.test/.well-known/agent-card.json", card, "openclaw")
        assert result == "https://custom.test/rpc"

    def test_resolves_relative_advertised_url(self):
        card = {"url": "/api/rpc"}
        result = _resolve_rpc_url("https://demo.test", "https://demo.test/.well-known/agent-card.json", card, "openclaw")
        assert result == "https://demo.test/api/rpc"

    def test_defaults_to_a2a_jsonrpc_for_openclaw(self):
        result = _resolve_rpc_url("https://demo.test", "https://demo.test/.well-known/agent-card.json", {}, "openclaw")
        assert result == "https://demo.test/a2a/jsonrpc"

    def test_defaults_to_base_slash_for_factchecker(self):
        result = _resolve_rpc_url("https://demo.test", "https://demo.test/.well-known/agent.json", {}, "fact_checker")
        assert result == "https://demo.test/"


class TestDecodeSseDataLines:
    def test_parses_json_data_lines(self):
        lines = ['data: {"result": {"parts": [{"text": "hello"}]}}']
        events = _decode_sse_data_lines(lines)
        assert len(events) == 1
        assert events[0]["result"]["parts"][0]["text"] == "hello"

    def test_skips_done_sentinel(self):
        lines = ["data: [DONE]"]
        assert _decode_sse_data_lines(lines) == []

    def test_skips_non_data_lines(self):
        lines = ["event: update", "id: 1", 'data: {"ok": true}']
        events = _decode_sse_data_lines(lines)
        assert len(events) == 1

    def test_wraps_non_dict_json_in_data_key(self):
        lines = ['data: ["item1", "item2"]']
        events = _decode_sse_data_lines(lines)
        assert events[0] == {"data": ["item1", "item2"]}

    def test_wraps_invalid_json_as_text(self):
        lines = ["data: not-json"]
        events = _decode_sse_data_lines(lines)
        assert events[0] == {"text": "not-json"}

    def test_skips_empty_data_lines(self):
        lines = ["data: "]
        assert _decode_sse_data_lines(lines) == []


class TestExtractTextFromStreamEvents:
    def test_collects_text_from_result_parts(self):
        events = [{"result": {"parts": [{"text": "hello"}]}}]
        result = _extract_text_from_stream_events(events)
        assert "hello" in result

    def test_falls_back_to_text_key(self):
        events = [{"text": "plain text fallback"}]
        result = _extract_text_from_stream_events(events)
        assert "plain text fallback" in result

    def test_falls_back_to_delta_key(self):
        events = [{"delta": "streamed delta"}]
        result = _extract_text_from_stream_events(events)
        assert "streamed delta" in result

    def test_deduplicates_repeated_text(self):
        events = [{"text": "repeated"}, {"text": "repeated"}]
        result = _extract_text_from_stream_events(events)
        assert result.count("repeated") == 1

    def test_returns_empty_for_events_with_no_text(self):
        events = [{"unknown_key": "ignored"}]
        assert _extract_text_from_stream_events(events) == ""


class TestA2AFactChecker:
    def _make_checker(self, **kwargs) -> A2AFactChecker:
        return A2AFactChecker(a2a_url="https://fact.test/", **kwargs)

    def _mock_response(self, json_payload: dict, status_code: int = 200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_payload
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_build_payload_has_correct_structure(self):
        checker = self._make_checker()
        payload = checker._build_payload("The VPN needs a restart.", "msg-1")
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["parts"][0]["text"] == "The VPN needs a restart."

    def test_parse_accuracy_from_accurate_keyword(self):
        checker = self._make_checker()
        assert checker._parse_accuracy("The answer is accurate.") == 1.0

    def test_parse_accuracy_from_incorrect_keyword(self):
        checker = self._make_checker()
        assert checker._parse_accuracy("This is incorrect.") == 0.0

    def test_parse_accuracy_from_percentage(self):
        checker = self._make_checker()
        assert checker._parse_accuracy("Accuracy: 80%") == pytest.approx(0.8)

    def test_parse_accuracy_from_score_over_ten(self):
        checker = self._make_checker()
        assert checker._parse_accuracy("Score: 7/10") == pytest.approx(0.7)

    def test_parse_accuracy_returns_none_for_unrecognized(self):
        checker = self._make_checker()
        assert checker._parse_accuracy("No verdict here.") is None

    def test_parse_accuracy_returns_none_for_empty_string(self):
        checker = self._make_checker()
        assert checker._parse_accuracy("") is None

    def test_check_answer_returns_normalized_result(self):
        checker = self._make_checker(username="user", password="pass")
        response_payload = {
            "result": {
                "parts": [{"text": "The answer is accurate."}]
            }
        }
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = self._mock_response(response_payload)
            result = checker.check_answer("Restart the VPN client.")

        assert result["accuracy_score"] == 1.0
        assert result["accuracy_score_10"] == 10.0
        assert "parsed_text" in result
        assert "raw_response" in result

    def test_check_answer_without_credentials_sends_no_auth(self):
        checker = self._make_checker()
        response_payload = {"result": {"parts": [{"text": "not applicable"}]}}
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = self._mock_response(response_payload)
            checker.check_answer("Some answer.")
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs.get("auth") is None

    def test_extract_text_from_nested_parts(self):
        checker = self._make_checker()
        payload = {"parts": [{"text": "nested answer"}]}
        assert "nested answer" in checker._extract_text(payload)

    def test_extract_text_from_artifacts(self):
        checker = self._make_checker()
        payload = {"artifacts": [{"text": "artifact text"}]}
        assert "artifact text" in checker._extract_text(payload)

    def test_extract_text_descends_into_result_key(self):
        checker = self._make_checker()
        payload = {"result": {"parts": [{"text": "deep text"}]}}
        assert "deep text" in checker._extract_text(payload)

    def test_check_answer_none_when_accuracy_unparseable(self):
        checker = self._make_checker()
        response_payload = {"result": {"parts": [{"text": "No verdict here at all."}]}}
        with patch("src.bibops.adapters.a2a_client.requests.post") as mock_post:
            mock_post.return_value = self._mock_response(response_payload)
            result = checker.check_answer("Some answer.")
        assert result["accuracy_score"] is None
        assert result["accuracy_score_10"] is None


class TestSendStreamMessageErrorHandling:
    def test_stream_error_returns_error_envelope(self):
        agent = _agent_info()
        with patch("src.bibops.adapters.a2a_client.requests.post", side_effect=RuntimeError("stream fail")):
            result = send_stream_message(agent, "ping")
        assert result.error == "stream fail"
        assert result.answer == ""
        assert result.events == []
