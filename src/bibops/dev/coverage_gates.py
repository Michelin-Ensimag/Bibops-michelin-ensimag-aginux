#!/usr/bin/env python3
"""
Per-module coverage-gate enforcer.

Reads `data/outputs/coverage.json` (produced by `pytest --cov-report=json`),
sums covered/total statements per logical module group, and asserts that each
group meets its threshold. Exits non-zero on the first failure with a
human-readable summary.

Gates (per BibOps refactor plan, validated by user):
  evaluation/, agent/, adapters/, common/, probes/   -->  >= 80 %
  racing/, runners/ (= benchmark/)                   -->  >= 50 %
  research/                                          -->  EXCLUDED
  bibops/cli/                                        -->  EXCLUDED (Typer scaffolding)

Usage:
    bibops dev coverage-gates
    bibops dev coverage-gates --report data/outputs/coverage.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT = PROJECT_ROOT / "data" / "outputs" / "coverage.json"

# Each entry: (group label, prefix list, minimum % covered statements).
# A file is attributed to the FIRST matching group (order matters).
GATES: list[tuple[str, tuple[str, ...], float]] = [
    ("evaluation",  ("src/bibops/evaluation/",), 80.0),
    ("adapters",    ("src/bibops/adapters/",),   80.0),
    ("probes",      ("src/bibops/probes/",),     80.0),
    ("agent",       ("src/agent/",),             80.0),
    ("common",      ("src/common/",),            80.0),
    ("racing",      ("src/racing/",),            50.0),
    ("runners",     ("src/bibops/benchmark/",),  50.0),
]


def _normalise(path: str) -> str:
    """coverage.json reports paths relative to repo root, with forward slashes."""
    return path.replace("\\", "/")


def aggregate(report: dict) -> list[dict]:
    """Bucket every covered file into a gate group."""
    files = report.get("files", {})
    buckets: dict[str, dict] = {label: {"label": label, "min": gate, "files": [], "covered": 0, "total": 0}
                                for label, _prefixes, gate in GATES}

    for raw_path, file_data in files.items():
        path = _normalise(raw_path)
        for label, prefixes, _gate in GATES:
            if any(path.startswith(p) for p in prefixes):
                summary = file_data.get("summary", {})
                buckets[label]["files"].append(path)
                buckets[label]["covered"] += int(summary.get("covered_lines", 0))
                buckets[label]["total"] += int(summary.get("num_statements", 0))
                break

    rows: list[dict] = []
    for label, _prefixes, gate in GATES:
        row = buckets[label]
        total = row["total"]
        covered = row["covered"]
        pct = (100.0 * covered / total) if total else 0.0
        rows.append({
            "label": label,
            "min": gate,
            "covered": covered,
            "total": total,
            "pct": round(pct, 2),
            "file_count": len(row["files"]),
            "passed": total == 0 or pct >= gate,
            "empty": total == 0,
        })
    return rows


def render(rows: list[dict]) -> str:
    header = f"  {'GROUP':<14} {'COVERED':>8}/{'TOTAL':>6}  {'%':>7}  {'GATE':>6}  STATUS"
    sep = "  " + "─" * (len(header) - 2)
    lines = [header, sep]
    for row in rows:
        if row["empty"]:
            status = "SKIP (no files)"
        elif row["passed"]:
            status = "PASS"
        else:
            status = f"FAIL (need >= {row['min']:.1f}%)"
        lines.append(
            f"  {row['label']:<14} "
            f"{row['covered']:>8}/{row['total']:<6}  "
            f"{row['pct']:>6.2f}%  "
            f"{row['min']:>5.1f}%  {status}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT,
                        help=f"Path to coverage.json (default: {DEFAULT_REPORT.relative_to(PROJECT_ROOT)})")
    parser.add_argument("--allow-empty", action="store_true",
                        help="Treat groups with zero files as PASS (default behavior).")
    args = parser.parse_args(argv)

    if not args.report.exists():
        print(f"[ERROR] Coverage report not found: {args.report}", file=sys.stderr)
        print("        Run pytest with `--cov-report=json:data/outputs/coverage.json` first.", file=sys.stderr)
        return 2

    with args.report.open(encoding="utf-8") as f:
        report = json.load(f)

    rows = aggregate(report)
    print("\nBibOps coverage gates:\n")
    print(render(rows))

    failures = [r for r in rows if not r["passed"]]
    if failures:
        print()
        for row in failures:
            print(f"[FAIL] {row['label']}: {row['pct']:.2f}% < gate {row['min']:.1f}% "
                  f"({row['covered']}/{row['total']} statements across {row['file_count']} files)")
        return 1

    print("\n[OK] All coverage gates met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
