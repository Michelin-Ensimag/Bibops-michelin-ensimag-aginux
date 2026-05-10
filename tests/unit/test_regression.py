"""Unit tests for the regression module (no pytest run, no agent)."""
from __future__ import annotations

import json

import pytest

from src.eval_bank.reporting.regression import (
    check_regression,
    extract_scores_from_report,
    write_baseline,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic JSON reports
# ---------------------------------------------------------------------------

def _fake_report(scores: dict[str, float]) -> dict:
    """Build a minimal pytest-json-report payload with the given scores."""
    tests = []
    for key, score in scores.items():
        metric, probe_id = key.rsplit("/", 1)
        tests.append({
            "nodeid": f"tests/integration/security/test_x.py::test_x[{probe_id}]",
            "outcome": "passed",
            "user_properties": [
                {"eval_score": {
                    "metric": metric,
                    "score": float(score),
                    "zone": "pass",
                    "min": 7.0,
                    "target": 9.0,
                    "tolerance": 0.5,
                    "severity": "major",
                    "findings": [],
                }}
            ],
        })
    return {
        "duration": 12.3,
        "summary": {"total": len(tests), "passed": len(tests)},
        "tests": tests,
    }


@pytest.fixture
def report_path(tmp_path):
    def _make(scores):
        path = tmp_path / "report.json"
        path.write_text(json.dumps(_fake_report(scores)))
        return path
    return _make


@pytest.fixture
def baseline_path(tmp_path, report_path):
    def _make(scores, tolerance=1.0):
        rep = report_path(scores)
        path = tmp_path / "baseline.json"
        write_baseline(
            json_report_path=rep,
            baseline_path=path,
            agent="test",
            agent_model="test_model",
            threshold_profile="default",
            tolerance=tolerance,
        )
        return path
    return _make


# ---------------------------------------------------------------------------
# extract_scores_from_report
# ---------------------------------------------------------------------------

class TestExtractScores:
    def test_extracts_metric_and_probe(self, report_path):
        path = report_path({"security.pii/pii_a": 9.0, "security.secrets/sec_b": 5.0})
        scores, summary = extract_scores_from_report(path)
        assert scores == {"security.pii/pii_a": 9.0, "security.secrets/sec_b": 5.0}
        assert summary["total"] == 2

    def test_skipped_tests_omitted(self, tmp_path):
        payload = {
            "duration": 1.0,
            "summary": {"total": 2},
            "tests": [
                {
                    "nodeid": "tests/x.py::t[a]",
                    "outcome": "passed",
                    "user_properties": [{"eval_score": {"metric": "m", "score": 8.0}}],
                },
                {"nodeid": "tests/x.py::t[b]", "outcome": "skipped", "user_properties": []},
            ],
        }
        p = tmp_path / "r.json"
        p.write_text(json.dumps(payload))
        scores, _ = extract_scores_from_report(p)
        assert scores == {"m/a": 8.0}


# ---------------------------------------------------------------------------
# write_baseline
# ---------------------------------------------------------------------------

class TestWriteBaseline:
    def test_baseline_has_required_fields(self, baseline_path):
        path = baseline_path({"security.pii/a": 10.0})
        data = json.loads(path.read_text())
        assert data["schema_version"] == 1
        assert data["agent"] == "test"
        assert data["agent_model"] == "test_model"
        assert data["tolerance"] == 1.0
        assert data["scores"] == {"security.pii/a": 10.0}
        assert "snapshot_date" in data

    def test_scores_sorted(self, baseline_path):
        path = baseline_path({"z/c": 1.0, "a/b": 2.0, "m/x": 3.0})
        data = json.loads(path.read_text())
        keys = list(data["scores"].keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# check_regression
# ---------------------------------------------------------------------------

class TestCheckRegression:
    def test_stable_no_regression(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 10.0, "m/b": 8.0})
        rp = report_path({"m/a": 10.0, "m/b": 8.0})
        report = check_regression(bp, rp)
        assert not report.has_regression
        assert len(report.regressions) == 0

    def test_within_tolerance_is_stable(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 8.0}, tolerance=1.0)
        rp = report_path({"m/a": 7.5})  # delta -0.5, within tol
        report = check_regression(bp, rp)
        assert not report.has_regression
        assert all(r.status == "stable" for r in report.rows)

    def test_regression_below_tolerance(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 10.0}, tolerance=1.0)
        rp = report_path({"m/a": 8.0})  # delta -2.0, exceeds tol
        report = check_regression(bp, rp)
        assert report.has_regression
        assert len(report.regressions) == 1
        assert report.regressions[0].delta == -2.0

    def test_improvement_flagged(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 5.0}, tolerance=1.0)
        rp = report_path({"m/a": 9.0})  # delta +4.0
        report = check_regression(bp, rp)
        assert not report.has_regression
        assert len(report.improvements) == 1
        assert report.improvements[0].delta == 4.0

    def test_missing_in_current(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 10.0, "m/b": 10.0})
        rp = report_path({"m/a": 10.0})  # m/b missing now
        report = check_regression(bp, rp)
        assert report.missing_in_current == ["m/b"]
        assert not report.has_regression

    def test_new_in_current(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 10.0})
        rp = report_path({"m/a": 10.0, "m/c": 8.0})
        report = check_regression(bp, rp)
        assert report.new_in_current == ["m/c"]

    def test_tolerance_override(self, baseline_path, report_path):
        bp = baseline_path({"m/a": 10.0}, tolerance=2.0)  # baseline says 2.0
        rp = report_path({"m/a": 8.5})  # delta -1.5
        # With baseline tolerance, this is stable
        assert not check_regression(bp, rp).has_regression
        # With override tolerance=1.0, this is a regression
        assert check_regression(bp, rp, tolerance=1.0).has_regression

    def test_unsupported_schema_raises(self, tmp_path, report_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"schema_version": 99, "scores": {}}))
        rp = report_path({"m/a": 10.0})
        with pytest.raises(ValueError, match="schema_version"):
            check_regression(bad, rp)
