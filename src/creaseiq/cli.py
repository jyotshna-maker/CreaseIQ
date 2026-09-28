"""CreaseIQ command-line interface (Typer).

The CLI is the single cross-platform entry point: ``creaseiq <command>`` or ``python -m creaseiq``.
Expected failures (:class:`~creaseiq.exceptions.CreaseIQError`) print a friendly message and
exit with code 1 instead of showing a traceback (NFR-02).
"""

from __future__ import annotations

from collections.abc import Callable

import typer
from rich.console import Console

from creaseiq import __version__
from creaseiq.config import Settings, get_settings
from creaseiq.exceptions import CreaseIQError
from creaseiq.logging_setup import configure_logging, new_run_id

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


@app.command()
def validate(
    strict: bool = typer.Option(False, "--strict", help="Fail on any invalid row."),
) -> None:
    """Ingest, validate and clean the raw CSV; write Parquet and the quality report (FR-01..03)."""
    from creaseiq.data.pipeline import run_data_pipeline

    settings = _bootstrap()
    result = _guard(lambda: run_data_pipeline(settings, mode="strict" if strict else "lenient"))
    res = result.summary["results"]
    console.print(
        f"[green]OK[/] {res['matches']} matches ({res['decided']} decided), "
        f"{result.validation.n_quarantined} quarantined, "
        f"{sum(result.clean.fixes.values())} fixes logged -> docs/data_quality_report.md"
    )


def _bootstrap() -> Settings:
    """Load settings, configure logging and start a run id."""
    settings = get_settings()
    configure_logging(
        settings.log_level,
        settings.root / str(settings.get("logging.file", "logs/creaseiq.log")),
        int(settings.get("logging.max_bytes", 1_000_000)),
        int(settings.get("logging.backup_count", 3)),
    )
    new_run_id()
    return settings


def _guard[T](fn: Callable[[], T]) -> T:
    """Run ``fn``; turn expected errors into a friendly message and exit code 1 (NFR-02)."""
    try:
        return fn()
    except CreaseIQError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":  # pragma: no cover
    app()
