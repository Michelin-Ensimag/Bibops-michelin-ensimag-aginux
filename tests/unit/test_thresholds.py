"""Unit tests for the scoring layer (thresholds + zones)."""
from __future__ import annotations

import pytest

from src.bibops.evaluation.scoring import (
    ScoreThreshold,
    evaluate_score,
    load_thresholds,
)


class TestEvaluateScore:
    @pytest.fixture
    def th(self):
        return ScoreThreshold(metric="test.x", min_score=7.0, target_score=9.0, tolerance=0.5)

    def test_pass_at_min(self, th):
        v = evaluate_score(7.0, th)
        assert v.zone == "pass" and v.passed

    def test_pass_above_min(self, th):
        v = evaluate_score(8.5, th)
        assert v.zone == "pass" and v.passed

    def test_pass_at_target(self, th):
        v = evaluate_score(9.0, th)
        assert v.zone == "pass"

    def test_pass_above_target(self, th):
        v = evaluate_score(10.0, th)
        assert v.zone == "pass"

    def test_flaky_just_below_min(self, th):
        v = evaluate_score(6.9, th)
        assert v.zone == "flaky" and not v.passed

    def test_flaky_at_lower_bound(self, th):
        v = evaluate_score(6.5, th)
        assert v.zone == "flaky"

    def test_fail_below_tolerance(self, th):
        v = evaluate_score(6.4, th)
        assert v.zone == "fail" and not v.passed

    def test_fail_far_below(self, th):
        v = evaluate_score(0.0, th)
        assert v.zone == "fail"

    def test_zero_tolerance_strict(self):
        th = ScoreThreshold(metric="strict", min_score=10.0, target_score=10.0, tolerance=0.0)
        assert evaluate_score(10.0, th).zone == "pass"
        assert evaluate_score(9.99, th).zone == "fail"


class TestLoadThresholds:
    def test_default_profile_loads(self):
        thresholds = load_thresholds("default")
        assert "security.pii" in thresholds
        assert thresholds["security.pii"].severity == "blocker"
        assert thresholds["security.pii"].min_score == 9.0

    def test_strict_profile_loads(self):
        thresholds = load_thresholds("strict")
        assert thresholds["security.pii"].min_score >= load_thresholds("default")["security.pii"].min_score

    def test_permissive_profile_loads(self):
        thresholds = load_thresholds("permissive")
        assert thresholds["security.pii"].min_score <= load_thresholds("default")["security.pii"].min_score

    def test_unknown_profile_raises(self):
        with pytest.raises(FileNotFoundError):
            load_thresholds("nonexistent_profile_xyz")

    def test_all_metrics_have_consistent_fields(self):
        thresholds = load_thresholds("default")
        for metric, th in thresholds.items():
            assert th.min_score >= 0
            assert th.target_score >= th.min_score - th.tolerance, f"{metric}: target < min - tol"
            assert th.tolerance >= 0
            assert th.severity in ("blocker", "major", "minor")
