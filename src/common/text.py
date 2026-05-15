"""Shared text processing and response extraction helpers."""
from __future__ import annotations

import csv
import json
import os
import re
import sys
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


def is_non_interactive_mode() -> bool:
    return os.environ.get("BIBOPS_NON_INTERACTIVE", "0") == "1" or not sys.stdin.isatty()


def extract_first_json(text: str) -> dict | None:
    """Return the first valid JSON object found in *text*, or None.

    Tolerates leading prose and ```json ... ``` code fences.
    """
    if not isinstance(text, str) or not text:
        return None
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```$", "", cleaned)
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(cleaned[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def load_tickets_csv(path: str, max_tickets: int | None = None) -> list[dict]:
    """Load tickets from a CSV. Slices to *max_tickets* if it is a positive int."""
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if isinstance(max_tickets, int) and max_tickets > 0:
        rows = rows[:max_tickets]
    return rows


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
