"""Minimal stand-in for the openai.OpenAI client used by judges & adapters.

Just enough surface to satisfy `client.chat.completions.create(...)`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class _Usage:
    prompt_tokens: int = 10
    completion_tokens: int = 20
    total_tokens: int = 30


@dataclass
class _Message:
    content: str
    role: str = "assistant"


@dataclass
class _Choice:
    message: _Message
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _Response:
    choices: list[_Choice]
    usage: _Usage | None = None
    model: str = "fake-model"


class _Completions:
    def __init__(self, behaviour: Callable[..., _Response] | _Response | Exception):
        self._behaviour = behaviour
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        if isinstance(self._behaviour, Exception):
            raise self._behaviour
        if callable(self._behaviour):
            return self._behaviour(**kwargs)
        return self._behaviour


class _Chat:
    def __init__(self, behaviour: Any):
        self.completions = _Completions(behaviour)


class FakeOpenAI:
    """Drop-in replacement for openai.OpenAI for unit tests.

    Pass `behaviour` as either:
      - a `_Response` (returned for every call),
      - a callable `(**kwargs) -> _Response` for prompt-aware responses,
      - an `Exception` instance (raised on every call).
    """

    def __init__(self, behaviour: Any = None, **_ignored: Any):
        if behaviour is None:
            behaviour = make_response('{"score": 8, "justification": "ok"}')
        self.chat = _Chat(behaviour)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.chat.completions.calls


def make_response(
    content: str,
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> _Response:
    """Build a canned chat-completion response with the given content."""
    return _Response(
        choices=[_Choice(message=_Message(content=content))],
        usage=_Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
