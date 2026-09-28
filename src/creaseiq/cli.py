"""CreaseIQ command-line interface (Typer).

The CLI is the single cross-platform entry point: ``creaseiq <command>`` or ``python -m creaseiq``.
Expected failures (:class:`~creaseiq.exceptions.CreaseIQError`) print a friendly message and
exit with code 1 instead of showing a traceback (NFR-02).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

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


@app.command("build-db")
def build_db() -> None:
    """Load the canonical tables into the database idempotently (FR-04)."""
    from creaseiq.data.pipeline import run_data_pipeline
    from creaseiq.db.loader import load_database
    from creaseiq.db.session import make_engine

    settings = _bootstrap()
    result = _guard(lambda: run_data_pipeline(settings))
    counts = _guard(
        lambda: load_database(
            make_engine(settings.db_url), result.clean.matches, result.clean.players, result.maps
        )
    )
    console.print(f"[green]OK[/] database {settings.db_url}")
    for table, n in counts.items():
        console.print(f"  {table:<16} {n:>6}")


@app.command()
def analyze() -> None:
    """Compute headline analytics and write reports/analytics.json (FR-06..FR-10)."""
    from creaseiq.analytics.summary import build_analytics_summary, render_findings_markdown
    from creaseiq.data.pipeline import load_processed
    from creaseiq.utils import write_json

    settings = _bootstrap()
    matches, players = _guard(lambda: load_processed(settings))
    summary = build_analytics_summary(matches, players, settings.seed)
    out = settings.path("reports_dir") / "analytics.json"
    write_json(out, summary)
    findings = settings.path("docs_dir") / "analytics_findings.md"
    findings.write_text(render_findings_markdown(summary), encoding="utf-8")
    toss, chase = summary["toss"]["overall"], summary["chasing"]["overall"]
    console.print(
        f"[green]OK[/] toss winner won {toss['rate']:.1%} (95% CI {toss['ci_low']:.1%}-{toss['ci_high']:.1%}, "
        f"p={toss['p_value']:.2f}); chasing side won {chase['rate']:.1%} (p={chase['p_value']:.3f}) -> {out.name}"
    )


@app.command()
def features() -> None:
    """Build leakage-safe as-of features and the Elo history (FR-12, FR-13)."""
    from creaseiq.data.pipeline import load_processed
    from creaseiq.features.builder import FeatureBuilder
    from creaseiq.models.params import feature_params_from_settings

    settings = _bootstrap()
    matches, players = _guard(lambda: load_processed(settings))
    fs = FeatureBuilder(feature_params_from_settings(settings)).build(matches, players)
    out = settings.path("processed_dir")
    fs.frame.to_parquet(out / "features.parquet", index=False)
    fs.elo_history.to_parquet(out / "elo_history.parquet", index=False)
    top = sorted(fs.state.elo.ratings.items(), key=lambda kv: -kv[1])[:3]
    console.print(
        f"[green]OK[/] {len(fs.frame)} feature rows; current Elo leaders: "
        + ", ".join(f"{t} {r:.0f}" for t, r in top)
    )


@app.command()
def train(
    no_register: bool = typer.Option(
        False, "--no-register", help="Evaluate only; do not register serving models."
    ),
) -> None:
    """Tune, select, calibrate, evaluate once on the holdout, and register models (FR-14..18, FR-22)."""
    from creaseiq.analytics.summary import build_analytics_summary
    from creaseiq.data.pipeline import load_processed
    from creaseiq.models.experiment import run_experiment
    from creaseiq.reporting.assets import write_training_outputs

    settings = _bootstrap()
    matches, players = _guard(lambda: load_processed(settings))
    metrics, _outcomes, fs = _guard(
        lambda: run_experiment(
            settings,
            matches,
            players,
            str(settings.get("paths.raw_sha256")),
            register=not no_register,
        )
    )
    write_training_outputs(
        settings, metrics, fs.elo_history, build_analytics_summary(matches, players, settings.seed)
    )
    processed = settings.path("processed_dir")
    fs.frame.to_parquet(processed / "features.parquet", index=False)
    fs.elo_history.to_parquet(processed / "elo_history.parquet", index=False)
    _print_metrics(metrics)


@app.command()
def evaluate() -> None:
    """Print the evaluation summary from reports/metrics.json (FR-15)."""
    from creaseiq.utils import read_json

    settings = _bootstrap()
    path = settings.path("reports_dir") / "metrics.json"
    if not path.exists():
        console.print("[red]Error:[/] No metrics yet. Run `creaseiq train` first.")
        raise typer.Exit(code=1)
    _print_metrics(read_json(path))


@app.command()
def ingest(
    append: Path = typer.Option(
        ..., "--append", exists=False, help="CSV of new matches (31 raw columns)."
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Validate only (default) or apply."
    ),
) -> None:
    """Validate and append new matches without touching the raw file (FR-05)."""
    from creaseiq.exceptions import InputError
    from creaseiq.services.ingest_service import process_upload

    settings = _bootstrap()

    def run() -> Any:
        if not append.is_file():
            raise InputError(f"File not found: {append}")
        return process_upload(settings, append.read_bytes(), append.name, dry_run=dry_run)

    report = _guard(run)
    console.print(
        f"received {report.rows_received} · new {report.rows_new} · duplicates {report.rows_duplicate} · applied {report.applied}"
    )
    for msg in report.messages:
        console.print(f"  {msg}")


@app.command()
def predict(
    team_a: str = typer.Argument(..., help="Franchise id, e.g. mi"),
    team_b: str = typer.Argument(..., help="Franchise id, e.g. csk"),
    venue: str = typer.Option(..., "--venue", help="Venue id, e.g. wankhede"),
    date: str | None = typer.Option(None, help="YYYY-MM-DD (default: day after the last match)"),
    stage: str = typer.Option(
        "league", help="league | qualifier_1 | eliminator | qualifier_2 | final"
    ),
    toss_winner: str | None = typer.Option(
        None, help="Franchise id that won the toss (post-toss tier)"
    ),
    toss_decision: str | None = typer.Option(None, help="bat | field"),
) -> None:
    """Predict a match (pre-toss, or post-toss when the toss is given) (FR-16)."""
    from creaseiq.services.context import AppContext
    from creaseiq.services.prediction_service import PredictionRequest, PredictionService

    settings = _bootstrap()
    svc = PredictionService(AppContext(settings))
    out = _guard(
        lambda: svc.predict(
            PredictionRequest(team_a, team_b, venue, date, stage, toss_winner, toss_decision)
        )
    )
    console.print(
        f"[bold]{out['team_a_name']}[/] {out['p_a']:.1%}  vs  [bold]{out['team_b_name']}[/] {out['p_b']:.1%}  ({out['tier']}, {out['model']}, {out['latency_ms']:.0f} ms)"
    )
    console.print(out["explanation"])


@app.command()
def whatif(
    team_a: str = typer.Argument(...),
    team_b: str = typer.Argument(...),
    venue: str = typer.Option(..., "--venue"),
    opponents: bool = typer.Option(False, "--opponents", help="Also compare other opponents"),
) -> None:
    """How the toss, venue or opponent changes P(team A wins) (FR-19)."""
    from creaseiq.services.context import AppContext
    from creaseiq.services.prediction_service import PredictionRequest
    from creaseiq.services.scenario_service import ScenarioService

    settings = _bootstrap()
    table = _guard(
        lambda: ScenarioService(AppContext(settings)).what_if(
            PredictionRequest(team_a, team_b, venue), include_opponents=opponents
        )
    )
    for r in table.itertuples():
        console.print(f"{r.p_a:6.1%}  {r.delta:+6.1%}  {r.scenario}")


@app.command()
def simulate(n_sims: int = typer.Option(10_000, help="Number of simulated seasons")) -> None:
    """Hypothetical season simulation: title and top-4 odds (FR-20, P2)."""
    from creaseiq.services.context import AppContext
    from creaseiq.services.scenario_service import ScenarioService

    settings = _bootstrap()
    odds = _guard(lambda: ScenarioService(AppContext(settings)).season_odds(n_sims))
    for r in odds.itertuples():
        console.print(f"{r.team_name:<30} title {r.p_title:6.1%}   top-4 {r.p_top4:6.1%}")


@app.command()
def benchmark(
    pages: bool = typer.Option(True, "--pages/--no-pages", help="Also time dashboard pages"),
) -> None:
    """Measure pipeline time, prediction latency, page render and memory (NFR-01) -> reports/perf.json."""
    from creaseiq.services.benchmark_service import run_benchmark

    settings = _bootstrap()
    res = _guard(lambda: run_benchmark(settings, include_pages=pages))
    for key, ok in res["passed"].items():
        console.print(
            f"{'[green]PASS[/]' if ok else '[red]FAIL[/]'} {key}: {res[key]:.3f} (target <= {res['targets'][key]})"
        )


@app.command("all")
def run_all() -> None:
    """validate → build-db → analyze → train (the whole pipeline)."""
    validate(strict=False)
    build_db()
    analyze()
    train(no_register=False)


def _print_metrics(metrics: dict[str, Any]) -> None:
    from rich.table import Table

    table = Table(title="Holdout evaluation (2025-26, evaluated once per frozen selection)")
    for col in (
        "tier",
        "model",
        "calibration",
        "log-loss [95% CI]",
        "Brier",
        "accuracy",
        "AUC",
        "vs coin (Δ log-loss)",
    ):
        table.add_column(col)
    for tier, t in metrics["tiers"].items():
        h = t["holdout"]["model"]
        ci = h["ci"]["log_loss"]
        table.add_row(
            tier,
            t["selection"]["chosen"],
            t["calibration"]["chosen"],
            f"{h['log_loss']:.4f} [{ci['low']:.4f}, {ci['high']:.4f}]",
            f"{h['brier']:.4f}",
            f"{h['accuracy']:.1%}",
            f"{h['auc']:.3f}",
            f"{t['holdout_vs_baselines']['B0_constant']['diff']:+.4f}",
        )
    console.print(table)
    for tier, t in metrics["tiers"].items():
        if t["too_good_guard"]["suspicious"]:
            console.print(
                f"[yellow]Warning[/] {tier}: suspiciously good results: {t['too_good_guard']['reasons']}"
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
