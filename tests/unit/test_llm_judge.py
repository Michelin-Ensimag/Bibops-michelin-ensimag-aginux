"""Unit tests for the lightweight LLMJudge (offline, with FakeOpenAI)."""
from __future__ import annotations

from src.bibops.evaluation.judges.llm_judge import JudgeVerdict, LLMJudge
from tests._fakes.fake_openai import FakeOpenAI, make_response


def _judge_with(content: str) -> tuple[LLMJudge, FakeOpenAI]:
    fake = FakeOpenAI(make_response(content))
    return LLMJudge(client=fake, model="fake-model"), fake


class TestParsing:
    def test_strict_json_response_yields_score(self):
        judge, _ = _judge_with('{"score": 7.5, "justification": "fine"}')
        v = judge.score(criterion="rel", question="q?", answer="a")
        assert isinstance(v, JudgeVerdict)
        assert v.score == 7.5
        assert v.justification == "fine"
        assert v.ok

    def test_json_in_code_fence_is_extracted(self):
        judge, _ = _judge_with('```json\n{"score": 6, "justification": "ok"}\n```')
        v = judge.score(criterion="rel", question="q?", answer="a")
        assert v.score == 6.0
        assert v.ok

    def test_json_with_leading_prose_is_extracted(self):
        judge, _ = _judge_with('Here is my evaluation: {"score": 9, "justification": "great"} done.')
        v = judge.score(criterion="rel", question="q?", answer="a")
        assert v.score == 9.0

    def test_invalid_json_returns_zero_with_invalid_marker(self):
        judge, _ = _judge_with("totally not json")
        v = judge.score(criterion="rel", question="q?", answer="a")
        assert v.score == 0.0
        assert v.justification.startswith("judge_invalid_json:")
        assert not v.ok


class TestClamping:
    def test_score_above_scale_is_clamped(self):
        judge, _ = _judge_with('{"score": 11.5, "justification": "x"}')
        v = judge.score(criterion="r", question="q", answer="a", scale=10)
        assert v.score == 10.0

    def test_negative_score_is_clamped_to_zero(self):
        judge, _ = _judge_with('{"score": -3, "justification": "x"}')
        v = judge.score(criterion="r", question="q", answer="a", scale=10)
        assert v.score == 0.0

    def test_non_numeric_score_defaults_to_zero(self):
        judge, _ = _judge_with('{"score": "high", "justification": "x"}')
        v = judge.score(criterion="r", question="q", answer="a", scale=10)
        assert v.score == 0.0


class TestErrorHandling:
    def test_client_exception_returns_judge_error_verdict(self):
        client = FakeOpenAI(RuntimeError("upstream 503"))
        judge = LLMJudge(client=client, model="fake-model")
        v = judge.score(criterion="r", question="q", answer="a")
        assert v.score == 0.0
        assert v.justification.startswith("judge_error:")
        assert "upstream 503" in v.justification
        assert not v.ok


class TestRequestShape:
    def test_request_carries_system_and_user_messages(self):
        judge, fake = _judge_with('{"score": 5, "justification": "ok"}')
        judge.score(criterion="REL", question="What time is it?", answer="3pm")
        call = fake.calls[0]
        roles = [m["role"] for m in call["messages"]]
        assert roles == ["system", "user"]
        assert "REL" in call["messages"][1]["content"]
        assert "What time is it?" in call["messages"][1]["content"]
        assert "3pm" in call["messages"][1]["content"]
        assert call["temperature"] == 0
