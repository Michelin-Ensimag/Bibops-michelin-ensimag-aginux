"""Adapter wrapping the existing BibOps IT-support agent (`lancer_agent`)."""
from __future__ import annotations

import time

from src.bibops.adapters.base import AbstractAgentAdapter, AgentResponse
from src.common.config import DEFAULT_AGENT_MODEL, DEFAULT_AGENT_PROVIDER


class ITSupportAdapter(AbstractAgentAdapter):
    """Adapter for src.agent.maestro.lancer_agent."""

    name = "it_support"

    def __init__(
        self,
        model: str = DEFAULT_AGENT_MODEL,
        provider: str = DEFAULT_AGENT_PROVIDER,
        max_iterations: int = 5,
        default_context: str = "Support IT Michelin",
    ):
        self.model = model
        self.provider = provider
        self.max_iterations = max_iterations
        self.default_context = default_context
        # Imported lazily so the test bank can be inspected without Ollama.
        self._tools = None
        self._lancer = None

    def _ensure_loaded(self):
        if self._tools is None:
            from src.agent.tools import (
                chercher_dans_kb,
                chercher_documentation_technique,
                verifier_statut_serveur,
            )

            self._tools = [
                verifier_statut_serveur,
                chercher_documentation_technique,
                chercher_dans_kb,
            ]
        if self._lancer is None:
            from src.agent.maestro import lancer_agent

            self._lancer = lancer_agent

    def query(self, prompt: str, *, context: str = "") -> AgentResponse:
        self._ensure_loaded()
        ctx = context or self.default_context

        t0 = time.perf_counter()
        try:
            result = self._lancer(
                contexte=ctx,
                ticket_utilisateur=prompt,
                outils_disponibles=self._tools,
                modele=self.model,
                modele_provider=self.provider,
                return_trace=True,
                max_iterations=self.max_iterations,
            )
        except Exception as exc:
            return AgentResponse(
                text=f"[ADAPTER_ERROR] {exc}",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                metadata={"error": str(exc), "model": self.model, "provider": self.provider},
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        if isinstance(result, dict):
            text = str(result.get("reponse_finale", "") or "")
            trace = result.get("trace") or {}
            return AgentResponse(
                text=text,
                latency_ms=latency_ms,
                metadata={
                    "model": self.model,
                    "provider": self.provider,
                    "run_id": result.get("run_id"),
                    "tool_calls": len(trace.get("tool_calls", [])) if isinstance(trace, dict) else 0,
                    "outcome": trace.get("outcome") if isinstance(trace, dict) else None,
                },
                raw=trace if isinstance(trace, dict) else None,
            )

        return AgentResponse(
            text=str(result or ""),
            latency_ms=latency_ms,
            metadata={"model": self.model, "provider": self.provider},
        )
