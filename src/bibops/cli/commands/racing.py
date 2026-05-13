"""`bibops racing …` — F1 racing arena commands."""
from __future__ import annotations

import typer

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="racing",
    help="Racing arena: standalone demo, hub-only, full arena, or adversarial mode.",
    no_args_is_help=True,
)


@app.command("demo", context_settings=PASSTHROUGH)
def demo(ctx: typer.Context) -> None:
    """Standalone single-team demo (no hub)."""
    from src.racing.demo import run_demo

    run_demo()


@app.command("hub", context_settings=PASSTHROUGH)
def hub(ctx: typer.Context) -> None:
    """Start the hub-only on localhost:8000."""
    import uvicorn

    uvicorn.run(
        "src.racing.hub.server:app",
        host="localhost",
        port=8000,
        reload=False,
        log_level="info",
    )


@app.command("arena", context_settings=PASSTHROUGH)
def arena(ctx: typer.Context) -> None:
    """Full arena launcher."""
    from src.racing import start_arena

    start_arena.main()


@app.command("adversarial", context_settings=PASSTHROUGH)
def adversarial(ctx: typer.Context) -> None:
    """Adversarial arena (4 teams: zero-shot, ReAct, validated, attacker)."""
    from src.racing import start_arena

    start_arena.main()
