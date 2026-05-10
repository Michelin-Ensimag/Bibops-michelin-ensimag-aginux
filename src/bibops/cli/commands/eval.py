"""`bibops eval` — run evaluation suites (forwards to the legacy eval_bank pytest harness)."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_module

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="eval",
    help="Run evaluation suites (security, quality, robustness, tool_use, regression).",
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings=PASSTHROUGH,
)


@app.callback(invoke_without_command=True, context_settings=PASSTHROUGH)
def main(ctx: typer.Context) -> None:
    """Forward all arguments to `python -m src.eval_bank`."""
    run_module("src.eval_bank", ctx.args)
