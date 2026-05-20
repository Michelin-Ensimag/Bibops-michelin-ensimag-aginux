"""
Adapter for external A2A agents (JSON-RPC over HTTPS, Basic Auth).

Wraps src.bibops.adapters.a2a_client so any agent reachable via the A2A
protocol can be evaluated through the unified eval bank pytest pipeline.

Configuration — all args fall back to env vars if not passed:
    a2a_url   → EVAL_BANK_A2A_URL   (required)
    username  → A2A_USERNAME        (may be empty for public agents)
    password  → A2A_PASSWORD

Rate-limit handling:
    Responses that contain rate-limit signals (HTTP 429 or the "[!] API rate
    limit reached" banner used by OpenClaw) are retried up to `max_retries`
    times with a configurable backoff so flaky infrastructure does not corrupt
    benchmark scores.
"""
from __future__ import annotations

import os
import time

from src.bibops.adapters.base import AbstractAgentAdapter, AgentResponse

_RATE_LIMIT_STRINGS = (
    "rate limit",
    "rate-limit",
    "too many requests",
    "api rate limit",
    "[!] api rate limit",
    "ratelimit",
)


def _is_rate_limited(text: str) -> bool:
    lower = (text or "").lower()
    return any(kw in lower for kw in _RATE_LIMIT_STRINGS)


class A2AAdapter(AbstractAgentAdapter):
    """Agent adapter for any A2A-compliant agent (OpenClaw family and others)."""

    name = "a2a"

    def __init__(
        self,
        a2a_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_s: int = 120,
        discovery_timeout_s: int = 30,
        max_retries: int = 3,
        rate_limit_backoff_s: int = 60,
        **_ignored,
    ):
        self.a2a_url = (a2a_url or os.environ.get("EVAL_BANK_A2A_URL", "")).rstrip("/")
        self.username = username or os.environ.get("A2A_USERNAME", "") or None
        self.password = password or os.environ.get("A2A_PASSWORD", "") or None
        self.timeout_s = timeout_s
        self.discovery_timeout_s = discovery_timeout_s
        self.max_retries = max_retries
        self.rate_limit_backoff_s = rate_limit_backoff_s
        self._agent_info = None

    def _ensure_discovered(self):
        if self._agent_info is not None:
            return
        if not self.a2a_url:
            raise RuntimeError(
                "A2AAdapter requires a target URL. "
                "Set EVAL_BANK_A2A_URL or pass a2a_url= to the constructor."
            )
        from src.bibops.adapters.a2a_client import discover_agent
        self._agent_info = discover_agent(self.a2a_url, timeout_s=self.discovery_timeout_s)

    def _send_once(self, prompt: str) -> AgentResponse:
        from src.bibops.adapters.a2a_client import send_message
        t0 = time.perf_counter()
        result = send_message(
            agent=self._agent_info,
            prompt=prompt,
            username=self.username,
            password=self.password,
            timeout_s=self.timeout_s,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        if result.error:
            return AgentResponse(
                text=f"[ADAPTER_ERROR] {result.error}",
                latency_ms=latency_ms,
                metadata={
                    "agent_name": self._agent_info.name,
                    "error": result.error,
                    "rate_limited": False,
                },
            )

        rate_limited = _is_rate_limited(result.answer)
        return AgentResponse(
            text=result.answer,
            latency_ms=latency_ms,
            raw=result.raw_response if result.raw_response else None,
            metadata={
                "agent_name": self._agent_info.name,
                "rate_limited": rate_limited,
                "latency_s": result.latency_s,
            },
        )

    def query(self, prompt: str, *, context: str = "") -> AgentResponse:
        try:
            self._ensure_discovered()
        except Exception as exc:
            return AgentResponse(
                text=f"[ADAPTER_ERROR] Discovery failed: {exc}",
                metadata={"error": str(exc)},
            )

        for attempt in range(1, self.max_retries + 1):
            response = self._send_once(prompt)
            if not response.metadata.get("rate_limited"):
                return response
            if attempt < self.max_retries:
                time.sleep(self.rate_limit_backoff_s)

        return response

    def warmup(self) -> None:
        self._ensure_discovered()

    def teardown(self) -> None:
        self._agent_info = None
