"""Singleton Copilot proxy client + availability probe."""
from __future__ import annotations

import socket
from urllib.parse import urlparse

from openai import OpenAI

from src.common.config import COPILOT_BASE_URL
from src.common.text import charger_copilot_api_key

_client_cache: OpenAI | None = None


def get_copilot_client() -> OpenAI:
    """Return a process-wide OpenAI client targeting the Copilot proxy."""
    global _client_cache
    if _client_cache is None:
        _client_cache = OpenAI(
            api_key=charger_copilot_api_key(),
            base_url=COPILOT_BASE_URL,
            timeout=60,
            max_retries=0,
        )
    return _client_cache


def is_copilot_available(timeout_s: float = 1.0) -> bool:
    """Quick TCP probe — does NOT consume API quota."""
    try:
        parsed = urlparse(COPILOT_BASE_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 4141
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except Exception:
        return False
