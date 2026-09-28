"""CreaseIQ command-line interface (Typer).

The CLI is the single cross-platform entry point: ``creaseiq <command>`` or ``python -m creaseiq``.
Expected failures (:class:`~creaseiq.exceptions.CreaseIQError`) print a friendly message and
exit with code 1 instead of showing a traceback (NFR-02).
"""

from __future__ import annotations

import typer
from rich.console import Console

from creaseiq import __version__
from creaseiq.config import get_settings

app = typer.Typer(
    name="creaseiq",
    help="CreaseIQ - IPL match intelligence: data pipeline, analytics and win probability.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Print the CreaseIQ version."""
    console.print(f"CreaseIQ {__version__}")


@app.command()
def info() -> None:
    """Show resolved configuration: project root, raw data path and database URL."""
    settings = get_settings()
    console.print(f"root     : {settings.root}")
    console.print(f"raw csv  : {settings.path('raw_csv')}")
    console.print(f"database : {settings.db_url}")
    console.print(f"seed     : {settings.seed}")


if __name__ == "__main__":  # pragma: no cover
    app()
