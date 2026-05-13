"""Provider-aware chat calls for Ollama and Copilot/OpenAI-compatible models."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any

import ollama

from src.common.config import MODEL_REQUEST_TIMEOUT_S, OLLAMA_OPTIONS, normalize_provider, validate_chat_model
from src.common.llm_clients import get_copilot_client


@dataclass
class ChatModelResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Any = None


def _extract_ollama_text(response: Any) -> str:
    message = response.get("message") if isinstance(response, dict) else getattr(response, "message", None)
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    return content if isinstance(content, str) else ""


def _extract_ollama_token_usage(response: Any) -> tuple[int, int]:
    if isinstance(response, dict):
        prompt = response.get("prompt_eval_count")
        completion = response.get("eval_count")
    else:
        prompt = getattr(response, "prompt_eval_count", None)
        completion = getattr(response, "eval_count", None)
    return (
        prompt if isinstance(prompt, int) else 0,
        completion if isinstance(completion, int) else 0,
    )


def _extract_openai_text(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except Exception:
        return ""
    return content if isinstance(content, str) else ""


def _extract_openai_token_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    return (
        prompt if isinstance(prompt, int) else 0,
        completion if isinstance(completion, int) else 0,
    )


def call_chat_model(
    *,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0,
    max_tokens: int = 1024,
    timeout: int | None = MODEL_REQUEST_TIMEOUT_S,
    validate: bool = True,
) -> ChatModelResponse:
    """Call a chat model through either Ollama or the Copilot proxy."""
    provider = normalize_provider(provider)
    if validate:
        validate_chat_model(provider, model, role="chat model")

    if provider == "ollama":
        options = dict(OLLAMA_OPTIONS)
        options["temperature"] = temperature
        options["num_predict"] = max_tokens
        if timeout is None:
            response = ollama.chat(model=model, messages=messages, options=options)
        else:
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(ollama.chat, model=model, messages=messages, options=options)
            try:
                response = future.result(timeout=timeout)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise TimeoutError(f"Ollama chat timeout after {timeout}s for model {model}") from exc
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
        prompt_tokens, completion_tokens = _extract_ollama_token_usage(response)
        return ChatModelResponse(
            text=_extract_ollama_text(response),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw=response,
        )

    client = get_copilot_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    response = client.chat.completions.create(**kwargs)
    prompt_tokens, completion_tokens = _extract_openai_token_usage(response)
    return ChatModelResponse(
        text=_extract_openai_text(response),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        raw=response,
    )
