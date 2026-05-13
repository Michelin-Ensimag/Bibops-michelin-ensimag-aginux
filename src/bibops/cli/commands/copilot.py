"""`bibops copilot ...` - Copilot proxy smoke tests and MCP demos."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_argv_main, run_async_main

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="copilot",
    help="Copilot proxy utilities and MCP integration checks.",
    no_args_is_help=True,
)


@app.command("smoke-test", context_settings=PASSTHROUGH)
def smoke_test_cmd(ctx: typer.Context) -> None:
    """Send one support ticket to configured Copilot proxy models."""
    from src.bibops.copilot import smoke_test

    run_argv_main(smoke_test.main, ctx.args)


@app.command("agent-mcp", context_settings=PASSTHROUGH)
def agent_mcp(ctx: typer.Context) -> None:
    """Run the Copilot + MCP multi-model benchmark."""
    from src.bibops.copilot import agent_mcp as copilot_mcp

    run_async_main(copilot_mcp.main)
