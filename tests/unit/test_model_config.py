from __future__ import annotations

import importlib

import pytest
from typer.testing import CliRunner


def test_validate_judge_model_accepts_supported_model():
    from src.common.config import validate_judge_model

    assert validate_judge_model("gpt-5.2") == "gpt-5.2"


def test_validate_judge_model_rejects_unknown_model():
    from src.common.config import validate_judge_model

    with pytest.raises(ValueError):
        validate_judge_model("not-a-judge")


def test_validate_chat_model_accepts_provider_specific_models():
    from src.common.config import validate_chat_model

    assert validate_chat_model("ollama", "mistral:latest") == ("ollama", "mistral:latest")
    assert validate_chat_model("copilot", "claude-haiku-4.5") == ("copilot", "claude-haiku-4.5")


def test_validate_chat_model_rejects_embedding_model_as_local_llm():
    from src.common.config import validate_chat_model

    with pytest.raises(ValueError):
        validate_chat_model("ollama", "nomic-embed-text:latest")


def test_model_defaults_follow_environment(monkeypatch):
    import src.common.config as config

    monkeypatch.setenv("BIBOPS_JUDGE_MODEL", "gpt-5.2")
    monkeypatch.setenv("BIBOPS_AGENT_PROVIDER", "copilot")
    monkeypatch.setenv("BIBOPS_AGENT_MODEL", "gpt-5.2-codex")
    monkeypatch.setenv("BIBOPS_ZERO_SHOT_PROVIDER", "ollama")
    monkeypatch.setenv("BIBOPS_ZERO_SHOT_MODEL", "mistral:latest")

    try:
        reloaded = importlib.reload(config)
        assert reloaded.DEFAULT_JUDGE_MODEL == "gpt-5.2"
        assert reloaded.DEFAULT_AGENT_PROVIDER == "copilot"
        assert reloaded.DEFAULT_AGENT_MODEL == "gpt-5.2-codex"
        assert reloaded.DEFAULT_ZERO_SHOT_PROVIDER == "ollama"
        assert reloaded.DEFAULT_ZERO_SHOT_MODEL == "mistral:latest"
    finally:
        for name in (
            "BIBOPS_JUDGE_MODEL",
            "BIBOPS_AGENT_PROVIDER",
            "BIBOPS_AGENT_MODEL",
            "BIBOPS_ZERO_SHOT_PROVIDER",
            "BIBOPS_ZERO_SHOT_MODEL",
        ):
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config)


def test_zero_shot_defaults_do_not_follow_agent_provider(monkeypatch):
    import src.common.config as config

    monkeypatch.setenv("BIBOPS_AGENT_PROVIDER", "copilot")
    monkeypatch.setenv("BIBOPS_AGENT_MODEL", "gpt-5.2")

    try:
        reloaded = importlib.reload(config)
        assert reloaded.DEFAULT_AGENT_PROVIDER == "copilot"
        assert reloaded.DEFAULT_AGENT_MODEL == "gpt-5.2"
        assert reloaded.DEFAULT_ZERO_SHOT_PROVIDER == "ollama"
        assert reloaded.DEFAULT_ZERO_SHOT_MODEL == "phi3:latest"
    finally:
        monkeypatch.delenv("BIBOPS_AGENT_PROVIDER", raising=False)
        monkeypatch.delenv("BIBOPS_AGENT_MODEL", raising=False)
        importlib.reload(config)


def test_config_cli_models_lists_supported_models():
    from src.bibops.cli.main import app

    result = CliRunner().invoke(app, ["config", "models"])

    assert result.exit_code == 0
    assert "gpt-5.2" in result.output
    assert "mistral:latest" in result.output


def test_config_cli_check_rejects_invalid_combo():
    from src.bibops.cli.main import app

    result = CliRunner().invoke(app, ["config", "check", "--agent-provider", "ollama", "--agent-model", "gpt-5.2"])

    assert result.exit_code != 0
    assert "Invalid agent model" in result.output
