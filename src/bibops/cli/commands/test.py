"""`bibops test ...` - project test runners."""
from __future__ import annotations

from pathlib import Path

import typer

from src.bibops.cli._shell import run_pytest

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="test",
    help="Run BibOps tests through the unified CLI.",
    no_args_is_help=True,
)


def _pytest_args(default_path: str, extra_args: list[str]) -> list[str]:
    has_explicit_path = any(not arg.startswith("-") and Path(arg).exists() for arg in extra_args)
    if has_explicit_path:
        return list(extra_args)
    return [default_path, *extra_args]


@app.command("unit", context_settings=PASSTHROUGH)
def unit(ctx: typer.Context) -> None:
    """Run unit tests."""
    run_pytest(_pytest_args("tests/unit", ctx.args))


@app.command("integration", context_settings=PASSTHROUGH)
def integration(ctx: typer.Context) -> None:
    """Run integration tests."""
    run_pytest(_pytest_args("tests/integration", ctx.args))


@app.command("all", context_settings=PASSTHROUGH)
def all_tests(ctx: typer.Context) -> None:
    """Run the full test suite."""
    run_pytest(_pytest_args("tests", ctx.args))


@app.command("coverage", context_settings=PASSTHROUGH)
def coverage(ctx: typer.Context) -> None:
    """Run tests with coverage JSON output."""
    run_pytest(["--cov=src", "--cov-report=json", *_pytest_args("tests", ctx.args)])
