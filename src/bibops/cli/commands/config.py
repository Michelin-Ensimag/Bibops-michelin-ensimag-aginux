"""`bibops config ...` - active model/provider configuration."""
from __future__ import annotations

import typer

from src.common.config import (
    DEFAULT_AGENT_MODEL,
    DEFAULT_AGENT_PROVIDER,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_ZERO_SHOT_MODEL,
    DEFAULT_ZERO_SHOT_PROVIDER,
    SUPPORTED_COPILOT_AGENT_MODELS,
    SUPPORTED_JUDGE_MODELS,
    SUPPORTED_LOCAL_LLM_MODELS,
    SUPPORTED_PROVIDERS,
    validate_chat_model,
    validate_judge_model,
)

app = typer.Typer(
    name="config",
    help="Show and validate BibOps model/provider configuration.",
    no_args_is_help=True,
)


def _echo_list(title: str, values: tuple[str, ...]) -> None:
    typer.echo(title)
    for value in values:
        typer.echo(f"  - {value}")


@app.command("models")
def models() -> None:
    """List supported providers and models."""
    _echo_list("Providers:", SUPPORTED_PROVIDERS)
    _echo_list("\nJudge models (Copilot/OpenAI-compatible):", SUPPORTED_JUDGE_MODELS)
    _echo_list("\nOllama chat models:", SUPPORTED_LOCAL_LLM_MODELS)
    _echo_list("\nCopilot agent models:", SUPPORTED_COPILOT_AGENT_MODELS)


@app.command("show")
def show() -> None:
    """Show active defaults after environment-variable overrides."""
    typer.echo(f"judge_model        : {DEFAULT_JUDGE_MODEL}")
    typer.echo(f"agent_provider     : {DEFAULT_AGENT_PROVIDER}")
    typer.echo(f"agent_model        : {DEFAULT_AGENT_MODEL}")
    typer.echo(f"zero_shot_provider : {DEFAULT_ZERO_SHOT_PROVIDER}")
    typer.echo(f"zero_shot_model    : {DEFAULT_ZERO_SHOT_MODEL}")


@app.command("check")
def check(
    judge_model: str = typer.Option(DEFAULT_JUDGE_MODEL, "--judge-model"),
    agent_provider: str = typer.Option(DEFAULT_AGENT_PROVIDER, "--agent-provider"),
    agent_model: str = typer.Option(DEFAULT_AGENT_MODEL, "--agent-model"),
    zero_shot_provider: str = typer.Option(DEFAULT_ZERO_SHOT_PROVIDER, "--zero-shot-provider"),
    zero_shot_model: str = typer.Option(DEFAULT_ZERO_SHOT_MODEL, "--zero-shot-model"),
) -> None:
    """Validate one model/provider configuration."""
    try:
        validate_judge_model(judge_model)
        validate_chat_model(agent_provider, agent_model, role="agent model")
        validate_chat_model(zero_shot_provider, zero_shot_model, role="zero-shot model")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo("[OK] Model/provider configuration is valid.")
