"""
Eval Bank fixtures.

These fixtures are only instantiated when a test requests them, so existing
unrelated tests (test_maestro.py, test_outils.py, ...) are unaffected.

Environment variables (set by `python -m src.eval_bank` CLI):
    EVAL_BANK_ADAPTER         — adapter name (default: it_support)
    EVAL_BANK_AGENT_MODEL     — optional model override
    EVAL_BANK_THRESHOLD_PROFILE — threshold profile (default | strict | permissive)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable when pytest is invoked without PYTHONPATH=.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Adapter selection
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def adapter_name() -> str:
    return os.environ.get("EVAL_BANK_ADAPTER", "it_support")


@pytest.fixture(scope="session")
def agent_model() -> str | None:
    return os.environ.get("EVAL_BANK_AGENT_MODEL") or None


@pytest.fixture(scope="session")
def agent_adapter(adapter_name, agent_model):
    """Instantiated agent adapter — the agent under test."""
    from src.eval_bank.adapters.registry import load_adapter

    kwargs = {}
    if agent_model:
        kwargs["model"] = agent_model
    return load_adapter(adapter_name, **kwargs)


# ---------------------------------------------------------------------------
# Copilot proxy + LLM judge
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def copilot_available() -> bool:
    from src.eval_bank.runtime.copilot import is_copilot_available
    return is_copilot_available()


@pytest.fixture(scope="session")
def copilot_client(copilot_available):
    if not copilot_available:
        pytest.skip("Copilot proxy not available on localhost:4141")
    from src.eval_bank.runtime.copilot import get_copilot_client
    return get_copilot_client()


@pytest.fixture(scope="session")
def llm_judge(copilot_client):
    from src.eval_bank.runtime.llm_judge import LLMJudge
    return LLMJudge(client=copilot_client, model="gpt-4o")


# ---------------------------------------------------------------------------
# Thresholds + assert_score helper
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def threshold_profile() -> str:
    return os.environ.get("EVAL_BANK_THRESHOLD_PROFILE", "default")


@pytest.fixture(scope="session")
def thresholds(threshold_profile):
    from src.eval_bank.scoring import load_thresholds
    return load_thresholds(threshold_profile)


@pytest.fixture
def assert_score(thresholds, request):
    """
    Helper used inside tests:

        assert_score(metric="security.pii", score=8.5, findings=[...], context="...")

    Behaviour:
        score >= min                    → PASS
        min - tolerance <= score < min  → xfail (FLAKY zone)
        score < min - tolerance         → fail (FAIL zone)
    """
    from src.eval_bank.scoring import evaluate_score

    def _assert(*, metric: str, score: float, findings: list | None = None, context: str = ""):
        if metric not in thresholds:
            pytest.fail(
                f"Unknown metric {metric!r}. "
                f"Add it to config/thresholds/{request.config.getoption('--threshold-profile', 'default') if False else ''}.yaml.\n"
                f"Available: {sorted(thresholds.keys())}"
            )
        verdict = evaluate_score(score, thresholds[metric], findings=list(findings or []), context=context)

        # Emit machine-readable record so reporters can pick it up.
        request.node.user_properties.append((
            "eval_score",
            {
                "metric": metric,
                "score": score,
                "zone": verdict.zone,
                "min": verdict.threshold.min_score,
                "target": verdict.threshold.target_score,
                "tolerance": verdict.threshold.tolerance,
                "severity": verdict.threshold.severity,
                "findings": list(findings or []),
            },
        ))

        if verdict.zone == "fail":
            pytest.fail(
                f"[FAIL] {metric}: score={score:.2f} < min={verdict.threshold.min_score:.2f} "
                f"- tolerance={verdict.threshold.tolerance:.2f} "
                f"(severity={verdict.threshold.severity}). "
                f"Findings: {findings or []}. "
                f"Context: {context[:300]}"
            )
        if verdict.zone == "flaky":
            pytest.xfail(
                f"[FLAKY] {metric}: score={score:.2f} below min={verdict.threshold.min_score:.2f} "
                f"but within tolerance={verdict.threshold.tolerance:.2f}. "
                f"Findings: {findings or []}"
            )
        return verdict

    return _assert
