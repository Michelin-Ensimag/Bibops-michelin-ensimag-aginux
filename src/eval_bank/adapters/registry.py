"""Compatibility shim — moved to src.bibops.adapters.registry."""
from src.bibops.adapters.registry import AVAILABLE_ADAPTERS, load_adapter

__all__ = ["AVAILABLE_ADAPTERS", "load_adapter"]
