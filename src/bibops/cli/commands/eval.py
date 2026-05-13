"""`bibops eval` — run BibOps evaluation commands."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer

from src.bibops.cli._shell import PROJECT_ROOT
from src.common.config import (
    DEFAULT_AGENT_MODEL,
    DEFAULT_AGENT_PROVIDER,
    DEFAULT_JUDGE_MODEL,
    validate_chat_model,
    validate_judge_model,
)

PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "databases" / "bibops.db"
DEFAULT_SCORES_OUTPUT = PROJECT_ROOT / "data" / "outputs" / "benchmark" / "tickets_evalues_scores.json"

app = typer.Typer(
    name="eval",
    help="Run evaluation jobs (pending LLM judge rows, JSON scoring, or integration suites).",
    no_args_is_help=True,
)


@app.command("pending")
def pending(
    db: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database containing pending evaluations."),
    judge_model: str = typer.Option(DEFAULT_JUDGE_MODEL, "--judge-model", help="OpenAI-compatible judge model."),
) -> None:
    """Evaluate pending rows from the SQLite `evaluations` table."""
    from src.bibops.evaluation.judges.llm_professor import LLMProfessor

    try:
        validate_judge_model(judge_model)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    count = LLMProfessor(db_path=str(db), modele_juge=judge_model).evaluer_tickets_en_attente()
    typer.echo(f"[OK] {count} ticket(s) évalué(s).")


@app.command("process")
def process(
    input_file: Path = typer.Option(..., "--input", "-i", help="Input JSON containing ticket responses."),
    output_file: Path = typer.Option(DEFAULT_SCORES_OUTPUT, "--output", "-o", help="Output JSON for scored tickets."),
) -> None:
    """Score a JSON file of ticket responses with the rule-based engine."""
    from src.bibops.evaluation.judges.rule_engine import EvaluationProcessor, compare_models

    output_file.parent.mkdir(parents=True, exist_ok=True)
    results = EvaluationProcessor(str(input_file), str(output_file)).process()
    typer.echo("\nStatistiques par modèle:")
    for model, stats in compare_models(results).items():
        typer.echo(
            f"- {model}: {stats['nombre_tickets']} ticket(s), "
            f"score moyen {stats['score_moyen']}/10, médiane {stats['score_median']}/10"
        )


@app.command("suite", context_settings=PASSTHROUGH)
def suite(
    ctx: typer.Context,
    category: str = typer.Argument(
        "all",
        help="Integration suite: all, security, quality, robustness, tool_use, or regression.",
    ),
    adapter: str = typer.Option("it_support", "--adapter", help="Adapter name passed to integration tests."),
    model: str | None = typer.Option(None, "--model", help="Optional agent model override."),
    agent_provider: str | None = typer.Option(
        None,
        "--agent-provider",
        "--provider",
        help="Optional agent provider override for it_support: ollama or copilot.",
    ),
    judge_model: str = typer.Option(DEFAULT_JUDGE_MODEL, "--judge-model", help="OpenAI-compatible judge model."),
    threshold_profile: str = typer.Option("default", "--threshold-profile", help="Threshold profile."),
) -> None:
    """Run integration evaluation tests through pytest."""
    suite_paths = {
        "all": PROJECT_ROOT / "tests" / "integration",
        "security": PROJECT_ROOT / "tests" / "integration" / "security",
        "quality": PROJECT_ROOT / "tests" / "integration" / "quality",
        "robustness": PROJECT_ROOT / "tests" / "integration" / "robustness",
        "tool_use": PROJECT_ROOT / "tests" / "integration" / "tool_use",
        "regression": PROJECT_ROOT / "tests" / "regression",
    }
    if category not in suite_paths:
        raise typer.BadParameter(f"Unknown suite: {category}. Available: {', '.join(suite_paths)}")

    env = os.environ.copy()
    env["EVAL_BANK_ADAPTER"] = adapter
    env["EVAL_BANK_THRESHOLD_PROFILE"] = threshold_profile
    try:
        validate_judge_model(judge_model)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    env["BIBOPS_JUDGE_MODEL"] = judge_model
    if agent_provider:
        if adapter != "it_support":
            raise typer.BadParameter("--agent-provider is only supported with --adapter it_support")
        try:
            validate_chat_model(agent_provider, model or DEFAULT_AGENT_MODEL, role="agent model")
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        env["EVAL_BANK_AGENT_PROVIDER"] = agent_provider
    if model:
        if not agent_provider:
            try:
                validate_chat_model(DEFAULT_AGENT_PROVIDER, model, role="agent model")
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
        env["EVAL_BANK_AGENT_MODEL"] = model

    cmd = [sys.executable, "-m", "pytest", str(suite_paths[category]), *list(ctx.args)]
    rc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env).returncode
    raise typer.Exit(code=rc)
