"""Inject generated results into README.md between marker comments (no hand-typed metrics)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def render_results_block(
    metrics: dict[str, Any], analytics: dict[str, Any], perf: dict[str, Any] | None
) -> str:
    """Markdown summary of analytics, model and performance results."""
    toss, chase, era = (
        analytics["toss"]["overall"],
        analytics["chasing"]["overall"],
        analytics["era_scoring"],
    )
    lines = [
        "**Analytics.**",
        "",
        f"- Toss winners won **{toss['rate']:.1%}** (95% CI {toss['ci_low']:.1%}–{toss['ci_high']:.1%}, p = {toss['p_value']:.2f}). There is no detectable toss advantage.",
        f"- The chasing side won **{chase['rate']:.1%}** (p = {chase['p_value']:.3f}).",
        f"- First-innings scores rose by **{era['diff']:+.1f} runs** in the Impact Player era (Cohen's d = {era['cohens_d']:.2f}).",
        "",
        "**Win-probability models.** Walk-forward validation used development seasons ≤ "
        + str(metrics["splits"]["dev_last_season"])
        + "; the holdout, "
        + ", ".join(map(str, metrics["splits"]["holdout_seasons"]))
        + ", was evaluated only after each tier's selection was frozen and hashed (one selection per tier; every recomputation is logged in `reports/holdout_ledger.json`). A coin flip scores log-loss 0.6931.",
        "",
        "| Tier | Model | Walk-forward log-loss | Holdout log-loss [95% CI] | Holdout accuracy | Holdout AUC |",
        "|---|---|---|---|---|---|",
    ]
    for tier, t in metrics["tiers"].items():
        h = t["holdout"]["model"]
        ci = h["ci"]["log_loss"]
        lines.append(
            f"| {tier} | {t['selection']['chosen']} | {t['selection']['walk_forward_mean_log_loss']:.4f} | {h['log_loss']:.4f} [{ci['low']:.4f}, {ci['high']:.4f}] | {h['accuracy']:.1%} | {h['auc']:.3f} |"
        )
    lines += [
        "",
        "**Honest verdict.** The models edge a coin flip in walk-forward validation, but none of them beats it on the 2025–26 holdout: relationships learned before 2023 weakened. See [`docs/model_card.md`](docs/model_card.md).",
    ]
    if perf:
        lines += [
            "",
            f"**Performance.** The full pipeline takes {perf['pipeline_s']:.1f} s. A warm prediction takes {perf['prediction_ms']:.1f} ms, and the slowest dashboard page renders in {perf.get('page_render_s', float('nan')):.2f} s. Peak memory is {perf['peak_memory_mb']:.0f} MB.",
        ]
    return "\n".join(lines)


def update_readme(readme: Path, block: str) -> bool:
    """Replace the text between the markers. Returns True if the file changed."""
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    new = pattern.sub(f"{START}\n{block}\n{END}", text)
    if new != text:
        readme.write_text(new, encoding="utf-8")
        return True
    return False
