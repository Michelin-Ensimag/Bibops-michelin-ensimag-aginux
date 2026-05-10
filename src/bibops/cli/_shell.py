"""Helpers to delegate CLI subcommands to existing Python modules / scripts."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]


def run_module(module: str, extra_args: list[str]) -> None:
    """Run `python -m <module> <extra_args>` in the project root and exit with its code."""
    cmd = [sys.executable, "-m", module, *list(extra_args)]
    rc = subprocess.run(cmd, cwd=PROJECT_ROOT).returncode
    raise typer.Exit(code=rc)


def run_script(rel_path: str, extra_args: list[str]) -> None:
    """Run a script at `<project_root>/<rel_path> <extra_args>` and exit with its code."""
    target = PROJECT_ROOT / rel_path
    cmd = [sys.executable, str(target), *list(extra_args)]
    rc = subprocess.run(cmd, cwd=PROJECT_ROOT).returncode
    raise typer.Exit(code=rc)
