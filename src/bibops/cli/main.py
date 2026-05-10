"""BibOps unified CLI — `bibops <subcommand>`."""
from __future__ import annotations

import typer

from src.bibops.cli.commands import bench, dev, racing
from src.bibops.cli.commands import eval as eval_cmd

app = typer.Typer(
    name="bibops",
    help="BibOps — production CLI for evaluation, benchmarking, and racing arena.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(eval_cmd.app, name="eval")
app.add_typer(bench.app, name="bench")
app.add_typer(racing.app, name="racing")
app.add_typer(dev.app, name="dev")


if __name__ == "__main__":
    app()
