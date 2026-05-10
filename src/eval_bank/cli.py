"""
Eval Bank CLI — single entry point.

Usage:
  python -m src.eval_bank --agent it_support
  python -m src.eval_bank --agent it_support --suite security
  python -m src.eval_bank --agent it_support --suite security --suite quality
  python -m src.eval_bank --agent it_support -k "pii"
  python -m src.eval_bank --agent it_support --threshold-profile strict
  python -m src.eval_bank --agent it_support --report json --output report.json
  python -m src.eval_bank --agent it_support --collect-only        # list tests

  # A2A agents (external, JSON-RPC over HTTPS)
  python -m src.eval_bank --agent a2a --a2a-url https://a2a-6.emottet.com
  python -m src.eval_bank --agent a2a --a2a-url https://a2a-6.emottet.com --suite security
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = PROJECT_ROOT / "tests"

KNOWN_SUITES = (
    "unit",
    "security",
    "quality",
    "reasoning",
    "tool_use",
    "robustness",
    "performance",
    "regression",
)


def _build_pytest_args(args: argparse.Namespace) -> list[str]:
    pytest_args: list[str] = []

    if args.suite:
        for suite in args.suite:
            if suite == "unit":
                pytest_args.append(str(TESTS_DIR / "unit"))
            elif suite == "regression":
                pytest_args.append(str(TESTS_DIR / "regression"))
            else:
                pytest_args.append(str(TESTS_DIR / "integration" / suite))
    else:
        pytest_args.append(str(TESTS_DIR / "integration"))

    if args.keyword:
        pytest_args.extend(["-k", args.keyword])

    if args.collect_only:
        pytest_args.append("--collect-only")

    if args.verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("-q")

    if args.report == "json":
        out = args.output or str(PROJECT_ROOT / "data" / "outputs" / "eval_bank_report.json")
        pytest_args.extend(["--json-report", f"--json-report-file={out}"])
    elif args.report == "junit":
        out = args.output or str(PROJECT_ROOT / "data" / "outputs" / "eval_bank_report.xml")
        pytest_args.extend([f"--junit-xml={out}"])

    if args.parallel:
        pytest_args.extend(["-n", str(args.parallel)])

    return pytest_args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_bank",
        description="Run evaluations on any agent through a unified test bank.",
    )
    parser.add_argument(
        "--agent", required=True,
        choices=["it_support", "openai_compat", "a2a"],
        help="Adapter for the agent under test.",
    )
    parser.add_argument(
        "--agent-model", default=None,
        help="Optional model identifier passed to the adapter (e.g. phi3:latest, gpt-4o-mini).",
    )
    parser.add_argument(
        "--suite", action="append", choices=list(KNOWN_SUITES),
        help="Test suite(s) to run. Repeatable (e.g. --suite security --suite quality).",
    )
    parser.add_argument(
        "-k", "--keyword", default=None,
        help="Pytest -k keyword filter (e.g. 'pii or injection').",
    )
    parser.add_argument(
        "--threshold-profile", default="default",
        choices=["default", "strict", "permissive"],
        help="Threshold profile for assert_score (default | strict | permissive).",
    )
    parser.add_argument(
        "--report", choices=["junit", "json", "none"], default="none",
        help="Report format.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Report output path (default under data/outputs/).",
    )
    parser.add_argument("--parallel", type=int, default=None, help="pytest-xdist worker count.")
    parser.add_argument("--collect-only", action="store_true", help="List tests without running.")
    parser.add_argument("-v", "--verbose", action="store_true")

    # A2A-specific options
    parser.add_argument(
        "--a2a-url", default=None,
        help="Base URL of the A2A agent to evaluate (required when --agent a2a).",
    )
    parser.add_argument(
        "--a2a-username", default=None,
        help="Basic Auth username for the A2A agent (overrides A2A_USERNAME env var).",
    )
    parser.add_argument(
        "--a2a-password", default=None,
        help="Basic Auth password for the A2A agent (overrides A2A_PASSWORD env var).",
    )

    # Regression flags (mutually compatible with --report json; both will read the JSON report).
    parser.add_argument(
        "--baseline", default=None,
        help="Path to a baseline JSON. After the run, compare scores and exit non-zero on regression.",
    )
    parser.add_argument(
        "--update-baseline", default=None,
        help="Path where to write a fresh baseline from the current run's JSON report.",
    )
    parser.add_argument(
        "--regression-tolerance", type=float, default=None,
        help="Per-probe tolerance for the regression check (overrides the baseline's value).",
    )

    args = parser.parse_args(argv)

    # Regression / baseline operations need a JSON report; force it on if not set.
    if (args.baseline or args.update_baseline) and args.report == "none":
        args.report = "json"

    os.environ["EVAL_BANK_ADAPTER"] = args.agent
    if args.agent_model:
        os.environ["EVAL_BANK_AGENT_MODEL"] = args.agent_model
    os.environ["EVAL_BANK_THRESHOLD_PROFILE"] = args.threshold_profile

    # Propagate A2A settings via env vars so the adapter fixture picks them up.
    if args.agent == "a2a":
        if not args.a2a_url and not os.environ.get("EVAL_BANK_A2A_URL"):
            print("[eval_bank] ERROR: --a2a-url is required when --agent a2a", file=sys.stderr)
            return 2
        if args.a2a_url:
            os.environ["EVAL_BANK_A2A_URL"] = args.a2a_url
        if args.a2a_username:
            os.environ["A2A_USERNAME"] = args.a2a_username
        if args.a2a_password:
            os.environ["A2A_PASSWORD"] = args.a2a_password

    pytest_args = _build_pytest_args(args)

    print(f"\n[eval_bank] adapter={args.agent}"
          f"{' model=' + args.agent_model if args.agent_model else ''}"
          f" profile={args.threshold_profile}")
    print(f"[eval_bank] pytest {' '.join(pytest_args)}\n")

    import pytest  # imported here so --help works without pytest installed
    pytest_exit = pytest.main(pytest_args)

    # Locate the JSON report we just produced (if any).
    json_report_path: str | None = None
    for i, a in enumerate(pytest_args):
        if a.startswith("--json-report-file="):
            json_report_path = a.split("=", 1)[1]
            break

    # --update-baseline takes precedence — write the snapshot, then return.
    if args.update_baseline:
        if not json_report_path or not Path(json_report_path).exists():
            print("[eval_bank] cannot update baseline: no JSON report was produced.", file=sys.stderr)
            return pytest_exit or 2
        from src.eval_bank.reporting.regression import write_baseline
        out = write_baseline(
            json_report_path=json_report_path,
            baseline_path=args.update_baseline,
            agent=args.agent,
            agent_model=args.agent_model,
            threshold_profile=args.threshold_profile,
            tolerance=args.regression_tolerance if args.regression_tolerance is not None else 1.0,
        )
        print(f"\n[eval_bank] baseline written: {out}")
        return pytest_exit

    # --baseline → compare and report; exit non-zero on regression.
    if args.baseline:
        if not json_report_path or not Path(json_report_path).exists():
            print("[eval_bank] cannot check regression: no JSON report was produced.", file=sys.stderr)
            return pytest_exit or 2
        from src.eval_bank.reporting.regression import check_regression, print_regression_report
        report = check_regression(
            baseline_path=args.baseline,
            json_report_path=json_report_path,
            tolerance=args.regression_tolerance,
        )
        print_regression_report(report)
        if report.has_regression:
            return 3  # distinct exit code for regression
        return pytest_exit

    return pytest_exit


if __name__ == "__main__":
    sys.exit(main())
