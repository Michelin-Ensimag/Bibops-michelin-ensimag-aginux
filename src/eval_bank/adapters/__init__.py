"""Compatibility shim — eval_bank.adapters has been moved to src.bibops.adapters."""

from src.bibops.adapters import (
    AVAILABLE_ADAPTERS,
    AbstractAgentAdapter,
    AgentResponse,
    load_adapter,
)

__all__ = [
    "AVAILABLE_ADAPTERS",
    "AbstractAgentAdapter",
    "AgentResponse",
    "load_adapter",
]
