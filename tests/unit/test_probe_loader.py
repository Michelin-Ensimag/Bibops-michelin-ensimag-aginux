"""
Unit tests for the probe loader.

The category-level tests are auto-discovered: any new probe file added under
data/inputs/probes/ is validated automatically.
"""
from __future__ import annotations

import pytest

from src.eval_bank.probes import Probe, list_categories, load_probes

ALL_CATEGORIES = list_categories()


class TestProbeLoaderBasics:
    def test_unknown_category_raises(self):
        with pytest.raises(FileNotFoundError):
            load_probes("nonexistent/category_xyz")

    def test_list_categories_non_empty(self):
        assert ALL_CATEGORIES, "No probe categories discovered"

    def test_security_pii_present(self):
        assert "security/pii" in ALL_CATEGORIES

    def test_security_injection_present(self):
        assert "security/injection" in ALL_CATEGORIES

    def test_security_secrets_present(self):
        assert "security/secrets" in ALL_CATEGORIES


@pytest.mark.parametrize("category", ALL_CATEGORIES)
class TestEachCategory:
    def test_loads(self, category):
        probes = load_probes(category)
        assert isinstance(probes, list)
        assert len(probes) > 0
        assert all(isinstance(p, Probe) for p in probes)

    def test_unique_ids(self, category):
        probes = load_probes(category)
        ids = [p.id for p in probes]
        assert len(ids) == len(set(ids)), f"Duplicate probe IDs in {category}: {ids}"

    def test_required_fields(self, category):
        probes = load_probes(category)
        for probe in probes:
            assert probe.id, f"Empty id in {category}"
            assert probe.input, f"Empty input in {category}/{probe.id}"
            assert probe.severity in ("blocker", "major", "minor"), (
                f"Invalid severity in {category}/{probe.id}: {probe.severity}"
            )


class TestInjectionProbes:
    def test_every_probe_has_a_canary(self):
        probes = load_probes("security/injection")
        for probe in probes:
            canary = probe.metadata.get("forbidden_canary")
            assert canary, f"{probe.id} missing forbidden_canary"
            assert len(canary) >= 4, f"{probe.id} canary too short: {canary!r}"

    def test_canary_appears_in_input(self):
        """Sanity check — the canary the test searches for must actually be in the prompt."""
        probes = load_probes("security/injection")
        for probe in probes:
            canary = probe.metadata["forbidden_canary"]
            # The system_prompt_reveal probe is special: canary is in the system prompt,
            # not in the user input. Skip that one.
            if probe.id == "injection_system_prompt_reveal":
                continue
            assert canary.lower() in probe.input.lower(), (
                f"{probe.id}: canary {canary!r} not found in input"
            )


class TestSecretsProbes:
    def test_echo_probes_contain_a_secret_pattern(self):
        """Echo-class probes should embed a secret in the input."""
        from src.eval_bank.checks import detect_secrets

        probes = load_probes("security/secrets")
        echo_probes = [p for p in probes if "echo" in p.tags]
        assert echo_probes, "No echo-class secrets probes found"
        for probe in echo_probes:
            findings = detect_secrets(probe.input)
            assert findings, (
                f"{probe.id}: echo-class probe should embed a detectable secret in input"
            )
