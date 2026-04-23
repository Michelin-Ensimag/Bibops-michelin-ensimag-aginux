"""GreenOps utilities for token-based carbon estimation."""

from __future__ import annotations


# Heuristic industry baseline for LLM inference energy:
# ~0.0002 kWh per 1,000 tokens.
_KWH_PER_1K_TOKENS = 0.0002

# Carbon intensity factors (gCO2e / kWh)
_CARBON_INTENSITY = {
    "local": 50.0,   # French mix (approx)
    "cloud": 250.0,  # Global cloud mix (approx)
}


def calculate_carbon_footprint(total_tokens: int, hardware_type: str = "cloud") -> dict:
    """
    Estimate energy use and carbon footprint from token usage.

    Args:
        total_tokens: Total tokens consumed by inference.
        hardware_type: "local" or "cloud".

    Returns:
        Dict containing:
            - energy_kwh: estimated energy in kWh
            - gCO2e: estimated emissions in grams CO2e
    """
    tokens = max(0, int(total_tokens))
    hw = (hardware_type or "cloud").strip().lower()
    if hw not in _CARBON_INTENSITY:
        hw = "cloud"

    energy_kwh = (tokens / 1000.0) * _KWH_PER_1K_TOKENS
    gco2e = energy_kwh * _CARBON_INTENSITY[hw]

    return {
        "energy_kwh": round(energy_kwh, 8),
        "gCO2e": round(gco2e, 6),
    }

