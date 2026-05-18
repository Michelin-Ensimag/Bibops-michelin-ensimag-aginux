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


def _register_passthrough(name: str, module_attr: str, label: str, help_text: str) -> None:
    """Wire a `bibops bench <name>` command that defers to a benchmark module's main()."""

    @app.command(name, context_settings=PASSTHROUGH)
    def _cmd(ctx: typer.Context, _module_attr: str = module_attr, _label: str = label) -> None:
        from importlib import import_module
        module = import_module(f"src.bibops.benchmark.{_module_attr}")
        run_argparse_main(module.main, ctx.args, _label)

    _cmd.__doc__ = help_text


# (command-name, module attr, CLI label, help text)
_BENCHMARKS = [
    ("compare-archs", "compare_architectures", "bibops bench compare-archs",
     "LLM Unique vs Multi-Agents architecture comparison."),
    ("core", "core", "bibops bench core",
     "Historical local Ollama benchmark producing tickets_evalues.json."),
    ("kaggle", "local_kaggle_exam", "bibops bench kaggle",
     "Local Kaggle SAE exam (judge-scored)."),
    ("a2a", "compare_a2a_agents", "bibops bench a2a",
     "Evaluate external A2A agents through the BibOps evaluator stack."),
    ("validate", "validate_benchmark_output", "bibops bench validate",
     "Validate a benchmark output JSON against the BibOps schema."),
    ("adversarial", "adversarial_convergence", "bibops bench adversarial",
     "Adversarial RAGAS-inspired benchmark: ReAct+RAG vs Zero-shot convergence (10 tickets x N iter)."),
    ("adversarial-demo", "adversarial", "bibops bench adversarial-demo",
     "Single-ticket demo of the adversarial loop (default: VPN-China scenario)."),
]
for _name, _attr, _label, _help in _BENCHMARKS:
    _register_passthrough(_name, _attr, _label, _help)


@app.command("ab-test", context_settings=PASSTHROUGH)
def ab_test(
    ctx: typer.Context,
    mode: str = typer.Option("llm", "--mode",
                             help="A/B mode: 'llm' (judge), 'user' (human), or 'statements' (factchecker vs bibops)."),
) -> None:
    """A/B test between two models / agents."""
    modules = {"llm": "ab_test_llm", "user": "ab_test_user", "statements": "ab_test_llm_statements"}
    if mode not in modules:
        raise typer.BadParameter(f"Unknown --mode: {mode}. Use 'llm', 'user', or 'statements'.")
    from importlib import import_module
    module = import_module(f"src.bibops.benchmark.{modules[mode]}")
    label = "bibops bench ab-test --mode statements" if mode == "statements" else "bibops bench ab-test"
    run_argparse_main(module.main, ctx.args, label)


@app.command("position-bias", context_settings=PASSTHROUGH)
def position_bias(
    ctx: typer.Context,
    mode: str = typer.Option("tickets", "--mode",
                             help="'tickets' (CSV scenarios) or 'statements' (factchecker pairs)."),
) -> None:
    """Detect order-dependent bias in the LLM judge."""
    modules = {"tickets": "position_bias", "statements": "position_bias_statements"}
    if mode not in modules:
        raise typer.BadParameter(f"Unknown --mode: {mode}. Use 'tickets' or 'statements'.")
    from importlib import import_module
    module = import_module(f"src.bibops.benchmark.{modules[mode]}")
    label = "bibops bench position-bias --mode statements" if mode == "statements" else "bibops bench position-bias"
    run_argparse_main(module.main, ctx.args, label)


@app.command("mcp-tools", context_settings=PASSTHROUGH)
def mcp_tools(ctx: typer.Context) -> None:
    """MCP tools benchmark (requires MCP server running in another terminal)."""
    from src.bibops.benchmark import mcp_tools as mcp_tools_mod

    run_async_main(mcp_tools_mod.main)
