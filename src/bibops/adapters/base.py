"""Abstract agent adapter — the only contract between tests and agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Normalized agent response, regardless of underlying agent type."""

    text: str
    raw: dict[str, Any] | None = None
    latency_ms: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.text.startswith("[ADAPTER_ERROR]") or "error" in self.metadata


class AbstractAgentAdapter(ABC):
    """
    Implement this to plug a new agent into the eval bank.

    The contract is intentionally minimal: send a prompt, get a response.
    All evaluation logic lives in tests, not in adapters.
    """

    name: str = "abstract"

    @abstractmethod
    def query(self, prompt: str, *, context: str = "") -> AgentResponse:
        """Send `prompt` to the agent and return its response."""

    def warmup(self) -> None:
        """Optional: prepare the agent (load weights, open connections)."""

    def teardown(self) -> None:
        """Optional: clean up resources."""
