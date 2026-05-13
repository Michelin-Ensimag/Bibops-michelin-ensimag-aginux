"""Unit tests for the composite scoring + release-gate policy."""
from __future__ import annotations

import pytest

from src.bibops.evaluation.metrics.composite import CompositePolicy

_LOW_RISKS = {"pii": 0.0, "prompt_injection": 0.0, "no_refusal": 0.0, "toxicity": 0.0}


def _summary(quality: float, security: float, cost: float = 0.01, latency: float = 1.0, carbon: float = 0.5):
    return {
        "summary": {
            "llm_unique": {"cout_usd": cost, "latence_totale_s": latency, "empreinte_gco2e": carbon},
            "systeme_multi_agents": {"cout_usd": cost * 2, "latence_totale_s": latency * 2, "empreinte_gco2e": carbon * 2},
        },
        "quality": {
            "llm_unique": {"score_moyen": quality},
            "systeme_multi_agents": {"score_moyen": quality},
        },
        "security": {
            "llm_unique": {"security_score_moyen": security, "blocked_count": 0, "error_count": 0, "risks_moyens": dict(_LOW_RISKS)},
            "systeme_multi_agents": {"security_score_moyen": security, "blocked_count": 0, "error_count": 0, "risks_moyens": dict(_LOW_RISKS)},
        },
    }


class TestVerdictGates:
    def test_pass_when_quality_and_security_meet_thresholds(self):
        d = _summary(quality=8.0, security=7.0)
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        for arch in ("llm_unique", "systeme_multi_agents"):
            assert out["architectures"][arch]["release_verdict"] == "PASS"
            assert out["architectures"][arch]["reasons"] == []

    def test_fail_on_low_quality(self):
        d = _summary(quality=6.5, security=8.0)
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        verdict = out["architectures"]["llm_unique"]
        assert verdict["release_verdict"] == "FAIL"
        assert any("quality_score" in r for r in verdict["reasons"])

    def test_fail_on_low_security(self):
        d = _summary(quality=9.0, security=5.0)
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        verdict = out["architectures"]["llm_unique"]
        assert verdict["release_verdict"] == "FAIL"
        assert any("security_score" in r for r in verdict["reasons"])

    def test_fail_on_blocked_count(self):
        d = _summary(quality=9.0, security=8.0)
        d["security"]["llm_unique"]["blocked_count"] = 1
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        assert out["architectures"]["llm_unique"]["release_verdict"] == "FAIL"
        assert any("blocked_count" in r for r in out["architectures"]["llm_unique"]["reasons"])

    def test_fail_on_pii_risk_above_threshold(self):
        d = _summary(quality=9.0, security=8.0)
        d["security"]["llm_unique"]["risks_moyens"] = {"pii": 0.9}
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        assert any("pii_risk" in r for r in out["architectures"]["llm_unique"]["reasons"])

    def test_security_error_count_gates_when_strict(self):
        d = _summary(quality=9.0, security=8.0)
        d["security"]["llm_unique"]["error_count"] = 2
        out = CompositePolicy(fail_on_security_errors=True).evaluate(d["summary"], d["quality"], d["security"])
        assert any("security_error_count" in r for r in out["architectures"]["llm_unique"]["reasons"])

    def test_security_error_count_ignored_when_lenient(self):
        d = _summary(quality=9.0, security=8.0)
        d["security"]["llm_unique"]["error_count"] = 2
        out = CompositePolicy(fail_on_security_errors=False).evaluate(d["summary"], d["quality"], d["security"])
        assert all("security_error_count" not in r for r in out["architectures"]["llm_unique"]["reasons"])


class TestCompositeAggregation:
    def test_score_in_0_to_100_range(self):
        d = _summary(quality=8.0, security=7.0)
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        score = out["architectures"]["llm_unique"]["composite_score"]
        assert 0.0 <= score <= 100.0
        assert pytest.approx(out["architectures"]["llm_unique"]["composite_score_10"], 0.01) == score / 10.0

    def test_weights_sum_close_to_one(self):
        weights = CompositePolicy().weights
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_quality_dominates_when_weights_skewed_to_quality(self):
        d = _summary(quality=10.0, security=2.0)
        skewed = CompositePolicy(weights={"quality": 0.95, "security": 0.05, "finops": 0.0, "latency": 0.0, "greenops": 0.0})
        out = skewed.evaluate(d["summary"], d["quality"], d["security"])
        assert out["architectures"]["llm_unique"]["composite_score"] >= 90

    def test_winner_prefers_pass_over_higher_score_fail(self):
        # Build a case where llm_unique has higher composite but FAILs, multi_agents PASSes with lower score.
        d = _summary(quality=9.0, security=8.0)
        # llm_unique gets even higher quality but fails on security
        d["quality"]["llm_unique"]["score_moyen"] = 10.0
        d["security"]["llm_unique"]["security_score_moyen"] = 3.0   # FAIL gate
        d["quality"]["systeme_multi_agents"]["score_moyen"] = 7.5
        d["security"]["systeme_multi_agents"]["security_score_moyen"] = 7.0
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        assert out["winner"] == "systeme_multi_agents"
        assert out["architectures"]["llm_unique"]["release_verdict"] == "FAIL"
        assert out["architectures"]["systeme_multi_agents"]["release_verdict"] == "PASS"

    def test_no_winner_when_all_fail(self):
        d = _summary(quality=2.0, security=2.0)  # both fail
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        assert out["winner"] is None
        assert out["winner_rule"] == "no_winner_when_all_fail"


class TestPayloadShape:
    def test_payload_has_versioned_policy_metadata(self):
        d = _summary(quality=8.0, security=7.0)
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        assert "policy_version" in out
        assert "weights" in out and "thresholds" in out
        assert out["winner_rule"] == "highest_composite_among_pass"

    def test_each_arch_exposes_component_scores_and_gates(self):
        d = _summary(quality=8.0, security=7.0)
        out = CompositePolicy().evaluate(d["summary"], d["quality"], d["security"])
        verdict = out["architectures"]["llm_unique"]
        for key in ("composite_score", "composite_score_10", "release_verdict", "reasons", "component_scores", "raw_metrics", "gates"):
            assert key in verdict
        for sub in ("quality_norm", "security_norm", "finops_norm", "latency_norm", "greenops_norm"):
            assert 0.0 <= verdict["component_scores"][sub] <= 1.0



class TestInverseMinmax:
    def test_empty_values_returns_one(self):
        from src.bibops.evaluation.metrics.composite import _inverse_minmax
        assert _inverse_minmax(5.0, []) == 1.0

    def test_identical_values_returns_one(self):
        from src.bibops.evaluation.metrics.composite import _inverse_minmax
        assert _inverse_minmax(3.0, [3.0, 3.0, 3.0]) == 1.0


class TestUnknownArchKeys:
    def test_non_standard_arch_keys(self):
        summary = {"my_arch": {"cout_usd": 0.01, "latence_totale_s": 1.0, "empreinte_gco2e": 0.5}}
        quality = {"my_arch": {"score_moyen": 8.0}}
        security = {"my_arch": {"security_score_moyen": 7.0, "blocked_count": 0, "error_count": 0,
                                "risks_moyens": {"pii": 0.0, "prompt_injection": 0.0, "no_refusal": 0.0, "toxicity": 0.0}}}
        out = CompositePolicy().evaluate(summary, quality, security)
        assert "my_arch" in out["architectures"]
