"""`bibops racing …` — F1 racing arena commands."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_module, run_script

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="racing",
    help="Racing arena: standalone demo, hub-only, full arena, or adversarial mode.",
    no_args_is_help=True,
)


@app.command("demo", context_settings=PASSTHROUGH)
def demo(ctx: typer.Context) -> None:
    """Standalone single-team demo (no hub)."""
    run_script("scripts/racing/run_demo.py", ctx.args)


@app.command("hub", context_settings=PASSTHROUGH)
def hub(ctx: typer.Context) -> None:
    """Start the hub-only on localhost:8000."""
    run_script("scripts/racing/run_hub.py", ctx.args)


@app.command("arena", context_settings=PASSTHROUGH)
def arena(ctx: typer.Context) -> None:
    """Full arena: hub + 3 legacy teams in parallel processes."""
    run_script("scripts/racing/run_arena.py", ctx.args)


@app.command("adversarial", context_settings=PASSTHROUGH)
def adversarial(ctx: typer.Context) -> None:
    """Adversarial arena (4 teams: zero-shot, ReAct, validated, attacker)."""
    run_module("src.racing.start_arena", ctx.args)
