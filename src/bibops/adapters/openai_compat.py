"""Adapter for any OpenAI-compatible endpoint (Copilot proxy, Ollama, vLLM, etc.)."""
from __future__ import annotations

import time

from openai import OpenAI

from src.bibops.adapters.base import AbstractAgentAdapter, AgentResponse


class OpenAICompatAdapter(AbstractAgentAdapter):
    name = "openai_compat"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "http://localhost:4141/v1",
        api_key: str = "copilot",
        system_prompt: str = "",
        temperature: float = 0.2,
        timeout: int = 60,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.timeout = timeout
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

    def query(self, prompt: str, *, context: str = "") -> AgentResponse:
        messages = []
        sys = self.system_prompt or context
        if sys:
            messages.append({"role": "system", "content": sys})
        messages.append({"role": "user", "content": prompt})

        t0 = time.perf_counter()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                timeout=self.timeout,
            )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            text = (resp.choices[0].message.content or "").strip()
            usage = getattr(resp, "usage", None)
            return AgentResponse(
                text=text,
                latency_ms=latency_ms,
                tokens_in=getattr(usage, "prompt_tokens", None) if usage else None,
                tokens_out=getattr(usage, "completion_tokens", None) if usage else None,
                metadata={"model": self.model},
            )
        except Exception as exc:
            return AgentResponse(
                text=f"[ADAPTER_ERROR] {exc}",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                metadata={"error": str(exc), "model": self.model},
            )
