"""Shared ANSI color constants and SSE-telemetry helper used by all team clients."""

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
GREY = "\033[90m"
MAGENTA = "\033[95m"


def is_race_telemetry(payload: dict) -> bool:
    """True for RaceEngine telemetry/race_over events, false for WeakProxy broadcasts."""
    return "lap_current" in payload and "race_status" in payload
