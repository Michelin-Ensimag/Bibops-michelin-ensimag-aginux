"""`bibops dev …` — developer utilities (init databases, MCP server, etc.)."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_script

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="dev",
    help="Developer utilities for first-time setup and local services.",
    no_args_is_help=True,
)


@app.command("init-db", context_settings=PASSTHROUGH)
def init_db(ctx: typer.Context) -> None:
    """Initialise the SQLite schema (servers + KB metadata)."""
    run_script("scripts/dev/init_sqlite.py", ctx.args)


@app.command("build-vectordb", context_settings=PASSTHROUGH)
def build_vectordb(ctx: typer.Context) -> None:
    """Ingest the knowledge base into ChromaDB (requires Ollama)."""
    run_script("scripts/dev/build_it_vector_db.py", ctx.args)


@app.command("mcp-server", context_settings=PASSTHROUGH)
def mcp_server(ctx: typer.Context) -> None:
    """Run the MCP tool server (stdio transport)."""
    run_script("scripts/dev/run_mcp_server.py", ctx.args)
