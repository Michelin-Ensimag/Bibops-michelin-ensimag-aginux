"""
Regression check against frozen baselines.

A baseline is a JSON file that snapshots per-probe scores from a known-good run.
After a fresh run, scores are compared:

    delta = current_score - baseline_score
    delta < -tolerance  → REGRESSION (test got worse)
    delta >  tolerance  → IMPROVEMENT (test got better — consider re-baselining)
    otherwise           → STABLE

Baseline format (schema_version 1):
{
  "schema_version": 1,
  "agent": "it_support",
  "agent_model": "phi3:latest",
  "threshold_profile": "default",
  "snapshot_date": "2026-05-09T15:30:00",
  "tolerance": 1.0,
  "summary": {"total": 23, "passed": 21, "failed": 1, "skipped": 1, "duration_s": 136.6},
  "scores": {
    "security.injection/injection_direct_override_en": 10.0,
    "security.secrets/secrets_echo_github_pat": 5.0,
    ...
  }
}

The probe key is `<metric>/<probe_id>`. Probes that were skipped (no eval_score
recorded) are absent from the baseline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class RegressionRow:
    probe_key: str
    baseline: float
    current: float
    delta: float
    status: str  # "regression" | "improvement" | "stable" | "missing"


@dataclass
class RegressionReport:
    baseline_path: str
    report_path: str
    tolerance: float
    rows: list[RegressionRow] = field(default_factory=list)
    missing_in_current: list[str] = field(default_factory=list)
    new_in_current: list[str] = field(default_factory=list)

    @property
    def regressions(self) -> list[RegressionRow]:
        return [r for r in self.rows if r.status == "regression"]

    @property
    def improvements(self) -> list[RegressionRow]:
        return [r for r in self.rows if r.status == "improvement"]

    @property
    def has_regression(self) -> bool:
        return bool(self.regressions)


def extract_scores_from_report(json_report_path: str | Path) -> tuple[dict[str, float], dict[str, Any]]:
    """
    Parse a pytest-json-report file and return:
      - scores: {"<metric>/<probe_id>": score, ...}
      - summary: {"total": int, "passed": int, ...}

    Skipped tests (no eval_score user-property) are absent from `scores`.
    """
    with open(json_report_path, encoding="utf-8") as f:
        data = json.load(f)

    scores: dict[str, float] = {}
    for test in data.get("tests", []):
        eval_score = None
        for prop in test.get("user_properties") or []:
            if isinstance(prop, dict) and "eval_score" in prop:
                eval_score = prop["eval_score"]
                break
        if not eval_score:
            continue
        nodeid = test["nodeid"]
        probe_id = nodeid.split("[")[-1].rstrip("]") if "[" in nodeid else nodeid.split("::")[-1]
        key = f"{eval_score['metric']}/{probe_id}"
        scores[key] = float(eval_score["score"])

    summary = dict(data.get("summary") or {})
    summary["duration_s"] = round(data.get("duration", 0.0), 2)
    return scores, summary


def write_baseline(
    json_report_path: str | Path,
    baseline_path: str | Path,
    *,
    agent: str,
    agent_model: str | None,
    threshold_profile: str,
    tolerance: float = 1.0,
) -> Path:
    """Generate a baseline file from a fresh JSON report."""
    scores, summary = extract_scores_from_report(json_report_path)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "agent": agent,
        "agent_model": agent_model or "default",
        "threshold_profile": threshold_profile,
        "snapshot_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tolerance": float(tolerance),
        "summary": summary,
        "scores": dict(sorted(scores.items())),
    }

    out = Path(baseline_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return out


def check_regression(
    baseline_path: str | Path,
    json_report_path: str | Path,
    *,
    tolerance: float | None = None,
) -> RegressionReport:
    """
    Compare a fresh JSON report against a baseline. Returns a structured report.

    `tolerance` overrides the baseline's tolerance if given.
    """
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    if int(baseline.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"Unsupported baseline schema_version: {baseline.get('schema_version')}")

    tol = float(tolerance if tolerance is not None else baseline.get("tolerance", 1.0))
    baseline_scores: dict[str, float] = {k: float(v) for k, v in baseline.get("scores", {}).items()}

    current_scores, _ = extract_scores_from_report(json_report_path)

    report = RegressionReport(
        baseline_path=str(baseline_path),
        report_path=str(json_report_path),
        tolerance=tol,
    )

    for key, baseline_score in baseline_scores.items():
        if key not in current_scores:
            report.missing_in_current.append(key)
            continue
        cur = current_scores[key]
        delta = cur - baseline_score
        if delta < -tol:
            status = "regression"
        elif delta > tol:
            status = "improvement"
        else:
            status = "stable"
        report.rows.append(RegressionRow(
            probe_key=key, baseline=baseline_score, current=cur,
            delta=delta, status=status,
        ))

    for key in current_scores:
        if key not in baseline_scores:
            report.new_in_current.append(key)

    return report


def print_regression_report(report: RegressionReport) -> None:
    """Pretty-print a regression report to stdout."""
    print()
    print("=" * 78)
    print(f"  Regression check vs {Path(report.baseline_path).name}  (tolerance ±{report.tolerance})")
    print("=" * 78)
    print(f"  Compared probes: {len(report.rows)}")
    print(f"  Regressions    : {len(report.regressions)}")
    print(f"  Improvements   : {len(report.improvements)}")
    print(f"  Stable         : {sum(1 for r in report.rows if r.status == 'stable')}")
    if report.missing_in_current:
        print(f"  Missing now    : {len(report.missing_in_current)} (in baseline but not in current run)")
    if report.new_in_current:
        print(f"  New probes     : {len(report.new_in_current)} (in current run, not in baseline)")
    print()

    if report.regressions:
        print("REGRESSIONS:")
        for r in sorted(report.regressions, key=lambda x: x.delta):
            print(f"   [REGRESS] {r.probe_key:<60} {r.baseline:>5.2f} -> {r.current:>5.2f}  (delta {r.delta:+.2f})")
        print()

    if report.improvements:
        print("IMPROVEMENTS (consider re-baselining):")
        for r in sorted(report.improvements, key=lambda x: -x.delta):
            print(f"   [IMPROVE] {r.probe_key:<60} {r.baseline:>5.2f} -> {r.current:>5.2f}  (delta {r.delta:+.2f})")
        print()

    if report.missing_in_current:
        print(f"Missing from current run ({len(report.missing_in_current)}):")
        for key in report.missing_in_current[:10]:
            print(f"   [MISSING] {key}")
        if len(report.missing_in_current) > 10:
            print(f"   ... and {len(report.missing_in_current) - 10} more")
        print()
