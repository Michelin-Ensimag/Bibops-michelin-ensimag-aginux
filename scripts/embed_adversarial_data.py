"""Embed the trimmed adversarial-convergence JSON into docs/index.html.

Reads data/outputs/benchmark/adversarial_convergence.json, drops fields the page
does not consume (wallclock, reports[].iterations_necessaires is kept, etc.),
and replaces the content between
    <!-- ADVERSARIAL_DATA_BEGIN -->
    <!-- ADVERSARIAL_DATA_END -->
in docs/index.html with the trimmed JSON wrapped in a
<script id="adversarial-data" type="application/json"> block.

Idempotent. Run manually after each `bibops bench adversarial`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "outputs" / "benchmark" / "adversarial_convergence.json"
TARGET = ROOT / "docs" / "index.html"

BEGIN_MARKER = "<!-- ADVERSARIAL_DATA_BEGIN -->"
END_MARKER = "<!-- ADVERSARIAL_DATA_END -->"


def _trim(raw: dict) -> dict:
    """Strip fields the page does not consume to keep the inline JSON small."""
    config = raw.get("config", {})
    modes = {}
    for mode_name, mode_data in raw.get("modes", {}).items():
        modes[mode_name] = {
            "per_iteration": mode_data.get("per_iteration", {}),
            "success_rate": mode_data.get("success_rate", 0.0),
            "reports": mode_data.get("reports", []),
        }
    return {"config": config, "modes": modes}


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        return 1
    if not TARGET.exists():
        print(f"ERROR: target not found: {TARGET}", file=sys.stderr)
        return 1

    with SOURCE.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    trimmed = _trim(raw)
    payload = json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"))

    html = TARGET.read_text(encoding="utf-8")
    if BEGIN_MARKER not in html or END_MARKER not in html:
        print(
            f"ERROR: markers {BEGIN_MARKER} / {END_MARKER} not found in {TARGET}",
            file=sys.stderr,
        )
        return 2

    block = (
        f'{BEGIN_MARKER}\n'
        f'<script id="adversarial-data" type="application/json">\n'
        f'{payload}\n'
        f'</script>\n'
        f'{END_MARKER}'
    )
    before, _, rest = html.partition(BEGIN_MARKER)
    _, _, after = rest.partition(END_MARKER)
    new_html = before + block + after

    TARGET.write_text(new_html, encoding="utf-8")
    n_tickets = len(trimmed["modes"].get("react", {}).get("reports", []))
    print(f"[embed] wrote {len(payload):,} bytes ({n_tickets} tickets) → {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
