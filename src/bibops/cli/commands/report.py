"""`bibops report ...` - report asset generation."""
from __future__ import annotations

from pathlib import Path

import typer

from src.bibops.reporting.charts import (
    DEFAULT_BENCHMARK_DIR,
    DEFAULT_CHARTS_DIR,
    DEFAULT_COVERAGE_JSON,
    DEFAULT_EVAL_BANK_DIR,
    generate_all_charts,
)

app = typer.Typer(
    name="report",
    help="Generate report-ready artefacts from benchmark outputs.",
    no_args_is_help=True,
)


@app.command("charts")
def charts(
    benchmark_dir: Path = typer.Option(DEFAULT_BENCHMARK_DIR, "--benchmark-dir"),
    charts_dir: Path = typer.Option(DEFAULT_CHARTS_DIR, "--charts-dir"),
    coverage_json: Path = typer.Option(DEFAULT_COVERAGE_JSON, "--coverage-json"),
    eval_bank_dir: Path = typer.Option(DEFAULT_EVAL_BANK_DIR, "--eval-bank-dir"),
    strict: bool = typer.Option(False, "--strict", help="Fail if an expected source JSON is missing."),
) -> None:
    """Regenerate PNG charts under data/outputs/benchmark/charts."""
    try:
        result = generate_all_charts(
            benchmark_dir=benchmark_dir,
            charts_dir=charts_dir,
            coverage_json=coverage_json,
            eval_bank_dir=eval_bank_dir,
            strict=strict,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"[OK] Generated {len(result['generated'])} chart(s) in {result['charts_dir']}")
    for chart in result["generated"]:
        typer.echo(f"  - {chart}")
    for warning in result["warnings"]:
        typer.echo(f"[WARN] {warning}")

