"""Compatibility shim — moved to src.bibops.adapters.a2a_client."""
from src.bibops.adapters.a2a_client import (
    A2AAgentInfo,
    A2AClientError,
    discover_agent,
    send_message,
)

__all__ = ["A2AAgentInfo", "A2AClientError", "discover_agent", "send_message"]
