"""Compatibility shim — canonical Copilot client now lives at src.common.llm_clients."""
from src.common.llm_clients import get_copilot_client, is_copilot_available

__all__ = ["get_copilot_client", "is_copilot_available"]
