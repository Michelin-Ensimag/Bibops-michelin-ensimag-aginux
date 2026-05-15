"""Shared numeric helpers."""
from __future__ import annotations


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp *value* to [low, high]."""
    return max(low, min(high, float(value)))
