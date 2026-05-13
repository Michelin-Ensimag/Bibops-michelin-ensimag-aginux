"""Helpers for CLI commands that delegate to importable Python entrypoints."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]


def _exit_from_result(result: Any) -> None:
    code = result if isinstance(result, int) else 0
    raise typer.Exit(code=code)


def run_argparse_main(main: Callable[[], Any], extra_args: list[str], prog: str) -> None:
    """Run an argparse-style no-arg main after temporarily setting sys.argv."""
    old_argv = sys.argv[:]
    sys.argv = [prog, *list(extra_args)]
    try:
        result = main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise typer.Exit(code=code) from exc
    finally:
        sys.argv = old_argv
    _exit_from_result(result)


def run_argv_main(main: Callable[[list[str] | None], Any], extra_args: list[str]) -> None:
    """Run a main(argv) function and convert its return value into a Typer exit."""
    try:
        result = main(list(extra_args))
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise typer.Exit(code=code) from exc
    _exit_from_result(result)


def run_async_main(main: Callable[[], Awaitable[Any]]) -> None:
    """Run an async no-arg main and convert its return value into a Typer exit."""
    result = asyncio.run(main())
    _exit_from_result(result)


def run_pytest(extra_args: list[str]) -> None:
    """Run pytest from the project root through the active Python interpreter."""
    cmd = [sys.executable, "-m", "pytest", *list(extra_args)]
    rc = subprocess.run(cmd, cwd=PROJECT_ROOT).returncode
    raise typer.Exit(code=rc)
