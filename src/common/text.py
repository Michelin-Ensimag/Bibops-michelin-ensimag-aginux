"""Shared text processing and response extraction helpers."""
from __future__ import annotations

import os
from typing import Any


def _get_attr(obj: Any, key: str) -> Any:
    """Read a field from a dict or from an object attribute."""
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def charger_copilot_api_key() -> str:
    for env in ("COPILOT_API_KEY", "OPENAI_API_KEY"):
        key = os.environ.get(env, "").strip()
        if key:
            return key
    return "copilot"


def _extraire_texte(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [item.get("text", "").strip() for item in content if isinstance(item, dict) and item.get("text")]
        if parts:
            return "\n".join(parts)
    reasoning = getattr(message, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return "[Reponse vide]"


def extraire_texte_reponse(reponse_ollama) -> str:
    """Extract response text from Ollama response without assuming a unique format."""
    message = _get_attr(reponse_ollama, "message")
    contenu = _get_attr(message, "content") if message is not None else None
    return contenu if isinstance(contenu, str) else ""


def extraire_compteurs_tokens(reponse_ollama) -> tuple[int | None, str]:
    """Count tokens via native Ollama metadata, without approximation."""
    prompt_eval_count = _get_attr(reponse_ollama, "prompt_eval_count")
    eval_count = _get_attr(reponse_ollama, "eval_count")
    if isinstance(prompt_eval_count, int) and isinstance(eval_count, int):
        return prompt_eval_count + eval_count, "ollama_native"

    usage = _get_attr(reponse_ollama, "usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if isinstance(total_tokens, int):
            return total_tokens, "usage_total_tokens"
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            return prompt_tokens + completion_tokens, "usage_prompt_plus_completion"

    return None, "native_tokens_absents"


def contains_timeout(text: str) -> bool:
    """Return True if *text* looks like a timeout error message."""
    lowered = (text or "").lower()
    return "timeout" in lowered or "timed out" in lowered or "read timeout" in lowered
