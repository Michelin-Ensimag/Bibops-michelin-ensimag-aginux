"""Unit tests for GreenOps carbon-footprint estimator."""
from __future__ import annotations

import pytest

from src.bibops.evaluation.metrics.greenops import calculate_carbon_footprint


class TestEnergyAndCarbonMath:
    def test_zero_tokens_yields_zero_emissions(self):
        out = calculate_carbon_footprint(0)
        assert out["energy_kwh"] == 0.0
        assert out["gCO2e"] == 0.0

    def test_negative_tokens_clamp_to_zero(self):
        assert calculate_carbon_footprint(-10) == calculate_carbon_footprint(0)

    def test_payload_has_expected_keys(self):
        out = calculate_carbon_footprint(1000)
        assert set(out.keys()) == {"energy_kwh", "gCO2e"}

    def test_cloud_emits_more_than_local(self):
        cloud = calculate_carbon_footprint(10_000, hardware_type="cloud")
        local = calculate_carbon_footprint(10_000, hardware_type="local")
        assert cloud["gCO2e"] > local["gCO2e"]
        # energy depends only on tokens, not hardware
        assert cloud["energy_kwh"] == local["energy_kwh"]

    def test_unknown_hardware_falls_back_to_cloud(self):
        unknown = calculate_carbon_footprint(5_000, hardware_type="quantum-flux-capacitor")
        cloud = calculate_carbon_footprint(5_000, hardware_type="cloud")
        assert unknown["gCO2e"] == cloud["gCO2e"]

    def test_emissions_scale_linearly_with_tokens(self):
        small = calculate_carbon_footprint(1_000)["gCO2e"]
        large = calculate_carbon_footprint(10_000)["gCO2e"]
        assert pytest.approx(large, rel=1e-4) == small * 10
