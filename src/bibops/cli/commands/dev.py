"""`bibops dev …` — developer utilities (init databases, MCP server, etc.)."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_argv_main

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="dev",
    help="Developer utilities for first-time setup and local services.",
    no_args_is_help=True,
)


@app.command("init-db", context_settings=PASSTHROUGH)
def init_db(ctx: typer.Context) -> None:
    """Initialise the SQLite schema (servers + KB metadata)."""
    from src.agent.database import initialiser_base_de_donnees

    initialiser_base_de_donnees()


@app.command("build-vectordb", context_settings=PASSTHROUGH)
def build_vectordb(ctx: typer.Context) -> None:
    """Ingest the knowledge base into ChromaDB (requires Ollama)."""
    from src.agent.rag import initialiser_documentation

    initialiser_documentation()


@app.command("mcp-server", context_settings=PASSTHROUGH)
def mcp_server(ctx: typer.Context) -> None:
    """Run the MCP tool server (stdio transport)."""
    from src.agent.mcp_server import mcp

    mcp.run(transport="stdio")


@app.command("coverage-gates", context_settings=PASSTHROUGH)
def coverage_gates_cmd(ctx: typer.Context) -> None:
    """Check coverage.json against configured coverage gates."""
    from src.bibops.dev import coverage_gates

    run_argv_main(coverage_gates.main, ctx.args)
