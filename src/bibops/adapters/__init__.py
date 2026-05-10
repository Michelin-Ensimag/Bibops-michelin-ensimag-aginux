"""Adapter layer — uniform contract for any agent under test."""

from src.bibops.adapters.base import AbstractAgentAdapter, AgentResponse
from src.bibops.adapters.registry import AVAILABLE_ADAPTERS, load_adapter

__all__ = [
    "AVAILABLE_ADAPTERS",
    "AbstractAgentAdapter",
    "AgentResponse",
    "load_adapter",
]
