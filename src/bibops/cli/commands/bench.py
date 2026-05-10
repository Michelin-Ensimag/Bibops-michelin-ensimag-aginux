"""`bibops bench …` — benchmark runners."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_module, run_script

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="bench",
    help="Run benchmarks (architecture comparison, A/B tests, position bias, MCP, A2A, Kaggle).",
    no_args_is_help=True,
)


@app.command("compare-archs", context_settings=PASSTHROUGH)
def compare_archs(ctx: typer.Context) -> None:
    """LLM Unique vs Multi-Agents architecture comparison."""
    run_script("scripts/benchmark/compare_architectures.py", ctx.args)


@app.command("ab-test", context_settings=PASSTHROUGH)
def ab_test(
    ctx: typer.Context,
    mode: str = typer.Option(
        "llm",
        "--mode",
        help="A/B mode: 'llm' (judge), 'user' (human), or 'statements' (factchecker vs bibops).",
    ),
) -> None:
    """A/B test between two models / agents."""
    if mode == "llm":
        run_module("src.benchmark.ab_test_llm", ctx.args)
    elif mode == "user":
        run_module("src.benchmark.ab_test_user", ctx.args)
    elif mode == "statements":
        run_script("scripts/benchmark/ab_test_llm_statements.py", ctx.args)
    else:
        raise typer.BadParameter(f"Unknown --mode: {mode}. Use 'llm', 'user', or 'statements'.")


@app.command("position-bias", context_settings=PASSTHROUGH)
def position_bias(
    ctx: typer.Context,
    mode: str = typer.Option(
        "tickets",
        "--mode",
        help="'tickets' (CSV scenarios) or 'statements' (factchecker pairs).",
    ),
) -> None:
    """Detect order-dependent bias in the LLM judge."""
    if mode == "tickets":
        run_module("src.benchmark.test_biais_position", ctx.args)
    elif mode == "statements":
        run_script("scripts/benchmark/test_biais_position_statements.py", ctx.args)
    else:
        raise typer.BadParameter(f"Unknown --mode: {mode}. Use 'tickets' or 'statements'.")


@app.command("kaggle", context_settings=PASSTHROUGH)
def kaggle(ctx: typer.Context) -> None:
    """Local Kaggle SAE exam (judge-scored)."""
    run_script("scripts/benchmark/run_local_kaggle_exam.py", ctx.args)


@app.command("a2a", context_settings=PASSTHROUGH)
def a2a(ctx: typer.Context) -> None:
    """Evaluate external A2A agents through the BibOps evaluator stack."""
    run_script("scripts/benchmark/compare_a2a_agents.py", ctx.args)


@app.command("mcp-tools", context_settings=PASSTHROUGH)
def mcp_tools(ctx: typer.Context) -> None:
    """MCP tools benchmark (requires MCP server running in another terminal)."""
    run_module("src.benchmark.mcp_tools", ctx.args)


@app.command("validate", context_settings=PASSTHROUGH)
def validate(ctx: typer.Context) -> None:
    """Validate a benchmark output JSON against the BibOps schema."""
    run_script("scripts/benchmark/validate_benchmark_output.py", ctx.args)
