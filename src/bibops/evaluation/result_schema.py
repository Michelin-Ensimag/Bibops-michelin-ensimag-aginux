"""Shared schema helpers for benchmark output payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0.0"


def build_benchmark_payload(
    config: dict[str, Any],
    summary: dict[str, Any],
    quality: dict[str, Any],
    security: dict[str, Any],
    composite: dict[str, Any],
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a normalized benchmark payload with versioned schema."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "summary": summary,
        "quality": quality,
        "security": security,
        "composite": composite,
        "details": details,
    }
