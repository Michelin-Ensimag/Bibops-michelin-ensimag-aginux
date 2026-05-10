"""
Threshold + tolerance scoring.

Each metric has:
  - min_score: the floor an agent must meet
  - target_score: the ideal score
  - tolerance: how far below `min` is still tolerated (FLAKY zone, xfail)
  - severity: blocker | major | minor

Scoring zones:
  score >= min                       → PASS
  min - tolerance <= score < min     → FLAKY (xfail, not a hard fail)
  score < min - tolerance            → FAIL
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import yaml

from src.common.config import THRESHOLDS_DIR as CONFIG_DIR

Severity = Literal["blocker", "major", "minor"]
Zone = Literal["pass", "flaky", "fail"]


@dataclass(frozen=True)
class ScoreThreshold:
    metric: str
    min_score: float
    target_score: float
    tolerance: float = 0.5
    severity: Severity = "major"


@dataclass(frozen=True)
class ScoreVerdict:
    metric: str
    score: float
    zone: Zone
    threshold: ScoreThreshold
    findings: list[str] = field(default_factory=list)
    context: str = ""

    @property
    def passed(self) -> bool:
        return self.zone == "pass"


def load_thresholds(profile: str = "default") -> dict[str, ScoreThreshold]:
    """Load thresholds from a YAML profile (default | strict | permissive)."""
    path = CONFIG_DIR / f"{profile}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Threshold profile '{profile}' not found at {path}. "
            f"Available: {[p.stem for p in CONFIG_DIR.glob('*.yaml')]}"
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    result: dict[str, ScoreThreshold] = {}
    for metric, params in (data.get("thresholds") or {}).items():
        result[metric] = ScoreThreshold(
            metric=metric,
            min_score=float(params["min"]),
            target_score=float(params["target"]),
            tolerance=float(params.get("tolerance", 0.5)),
            severity=params.get("severity", "major"),
        )
    return result


def evaluate_score(
    score: float,
    threshold: ScoreThreshold,
    *,
    findings: list[str] | None = None,
    context: str = "",
) -> ScoreVerdict:
    """Classify a score into PASS / FLAKY / FAIL based on threshold."""
    if score >= threshold.min_score:
        zone: Zone = "pass"
    elif score >= threshold.min_score - threshold.tolerance:
        zone = "flaky"
    else:
        zone = "fail"
    return ScoreVerdict(
        metric=threshold.metric,
        score=score,
        zone=zone,
        threshold=threshold,
        findings=list(findings or []),
        context=context,
    )
