"""`bibops bench …` — benchmark runners."""
from __future__ import annotations

import typer

from src.bibops.cli._shell import run_argparse_main, run_async_main

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="bench",
    help="Run benchmarks (architecture comparison, A/B tests, position bias, MCP, A2A, Kaggle).",
    no_args_is_help=True,
)


@app.command("compare-archs", context_settings=PASSTHROUGH)
def compare_archs(ctx: typer.Context) -> None:
    """LLM Unique vs Multi-Agents architecture comparison."""
    from src.bibops.benchmark import compare_architectures

    run_argparse_main(compare_architectures.main, ctx.args, "bibops bench compare-archs")


@app.command("core", context_settings=PASSTHROUGH)
def core(ctx: typer.Context) -> None:
    """Historical local Ollama benchmark producing tickets_evalues.json."""
    from src.bibops.benchmark import core as core_benchmark

    run_argparse_main(core_benchmark.main, ctx.args, "bibops bench core")


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
        from src.bibops.benchmark import ab_test_llm

        run_argparse_main(ab_test_llm.main, ctx.args, "bibops bench ab-test")
    elif mode == "user":
        from src.bibops.benchmark import ab_test_user

        run_argparse_main(ab_test_user.main, ctx.args, "bibops bench ab-test")
    elif mode == "statements":
        from src.bibops.benchmark import ab_test_llm_statements

        run_argparse_main(ab_test_llm_statements.main, ctx.args, "bibops bench ab-test --mode statements")
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
        from src.bibops.benchmark import position_bias

        run_argparse_main(position_bias.main, ctx.args, "bibops bench position-bias")
    elif mode == "statements":
        from src.bibops.benchmark import position_bias_statements

        run_argparse_main(position_bias_statements.main, ctx.args, "bibops bench position-bias --mode statements")
    else:
        raise typer.BadParameter(f"Unknown --mode: {mode}. Use 'tickets' or 'statements'.")


@app.command("kaggle", context_settings=PASSTHROUGH)
def kaggle(ctx: typer.Context) -> None:
    """Local Kaggle SAE exam (judge-scored)."""
    from src.bibops.benchmark import local_kaggle_exam

    run_argparse_main(local_kaggle_exam.main, ctx.args, "bibops bench kaggle")


@app.command("a2a", context_settings=PASSTHROUGH)
def a2a(ctx: typer.Context) -> None:
    """Evaluate external A2A agents through the BibOps evaluator stack."""
    from src.bibops.benchmark import compare_a2a_agents

    run_argparse_main(compare_a2a_agents.main, ctx.args, "bibops bench a2a")


@app.command("mcp-tools", context_settings=PASSTHROUGH)
def mcp_tools(ctx: typer.Context) -> None:
    """MCP tools benchmark (requires MCP server running in another terminal)."""
    from src.bibops.benchmark import mcp_tools

    run_async_main(mcp_tools.main)


@app.command("validate", context_settings=PASSTHROUGH)
def validate(ctx: typer.Context) -> None:
    """Validate a benchmark output JSON against the BibOps schema."""
    from src.bibops.benchmark import validate_benchmark_output

    run_argparse_main(validate_benchmark_output.main, ctx.args, "bibops bench validate")


@app.command("adversarial", context_settings=PASSTHROUGH)
def adversarial(ctx: typer.Context) -> None:
    """Adversarial RAGAS-inspired benchmark: ReAct+RAG vs Zero-shot convergence (10 tickets x N iter)."""
    from src.bibops.benchmark import adversarial_convergence

    run_argparse_main(adversarial_convergence.main, ctx.args, "bibops bench adversarial")


@app.command("adversarial-demo", context_settings=PASSTHROUGH)
def adversarial_demo(ctx: typer.Context) -> None:
    """Single-ticket demo of the adversarial loop (default: VPN-China scenario)."""
    from src.bibops.benchmark import adversarial as adversarial_demo_runner

    run_argparse_main(adversarial_demo_runner.main, ctx.args, "bibops bench adversarial-demo")
