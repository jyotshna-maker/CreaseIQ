"""End-to-end modelling experiment (FR-14, FR-15, FR-17, FR-18, FR-22).

Steps:
1. Tune Elo on the development seasons.
2. Build features with the tuned Elo.
3. For each tier: baselines → model families (walk-forward grid) → one-SE selection →
   time-ordered calibration choice → ablations → **freeze and log the selection** →
   a single holdout evaluation with bootstrap CIs, paired tests against every baseline and
   the "too good" guard → permutation importance on development data.
4. Refit the frozen configuration on all decided matches for serving, and register it.
5. First-innings score regression. 6. Drift (PSI).

Every number the report quotes comes from the ``metrics`` dict returned here, which is
written to ``reports/metrics.json``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from creaseiq.config import Settings
from creaseiq.features.builder import (
    FEATURE_GROUPS,
    FeatureBuilder,
    FeatureSet,
    Tier,
    antisymmetric_columns,
    feature_columns,
)
from creaseiq.features.elo import EloParams
from creaseiq.logging_setup import get_logger, log_event, timed
from creaseiq.models import baselines as bl
from creaseiq.models import evaluate as ev
from creaseiq.models.calibrate import Calibrator, choose_method, time_ordered_calibration
from creaseiq.models.elo_tuning import tune_elo
from creaseiq.models.explain import permutation_importance
from creaseiq.models.params import feature_params_from_settings
from creaseiq.models.registry import ModelBundle, ModelRegistry
from creaseiq.models.score_regressor import build_score_frame, evaluate_score_models
from creaseiq.models.splits import dev_holdout_masks, walk_forward_folds
from creaseiq.models.train import (
    SPECS,
    CVResult,
    Model,
    blend_grid,
    make_model,
    select_model,
    walk_forward,
)
from creaseiq.reporting.drift import drift_report
from creaseiq.utils import git_commit, read_json, write_json

logger = get_logger(__name__)
TIERS: tuple[Tier, ...] = ("pre_toss", "post_toss")


@dataclass
class ExperimentConfig:
    """Modelling settings read from ``configs/config.yaml``."""

    seed: int
    first_valid: int
    dev_last: int
    holdout: list[int]
    n_boot: int
    n_paired: int
    too_good_auc: float
    too_good_acc: float
    elo_grid: dict[str, list[Any]]

    @classmethod
    def from_settings(cls, s: Settings) -> ExperimentConfig:
        """Read the ``modeling`` block."""
        return cls(
            seed=s.seed,
            first_valid=int(s.require("modeling.first_validation_season")),
            dev_last=int(s.require("modeling.dev_last_season")),
            holdout=[int(x) for x in s.require("modeling.holdout_seasons")],
            n_boot=int(s.require("modeling.bootstrap_resamples")),
            n_paired=int(s.require("modeling.paired_bootstrap_resamples")),
            too_good_auc=float(s.require("modeling.too_good_auc")),
            too_good_acc=float(s.require("modeling.too_good_accuracy")),
            elo_grid=dict(s.require("modeling.elo_grid")),
        )


@dataclass
class TierOutcome:
    """Fitted serving bundle plus the evaluation predictions for one tier."""

    bundle: ModelBundle
    metrics: dict[str, Any]
    holdout_frame: pd.DataFrame  # match_id, season, stage, y, p_model, p_<baseline>...
    oof_frame: pd.DataFrame  # match_id, season, y, p (calibrated, time-ordered)


# -- holdout ledger ---------------------------------------------------------------------------
def _selection_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[
        :16
    ]


def log_holdout_access(ledger_path: Path, tier: str, selection: dict[str, Any]) -> dict[str, Any]:
    """Record that the holdout is being evaluated for a frozen selection.

    Re-running the identical frozen selection is a deterministic recomputation, not a new
    look. A *different* selection on the same holdout is flagged as ``reused_with_new_selection``.
    """
    ledger: dict[str, Any] = read_json(ledger_path) if ledger_path.exists() else {}
    h = _selection_hash(selection)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = ledger.setdefault(tier, {"selections": {}})
    sel = entry["selections"].setdefault(
        h, {"first_evaluated_at": now, "evaluations": 0, "selection": selection}
    )
    sel["evaluations"] += 1
    distinct = len(entry["selections"])
    write_json(ledger_path, ledger)
    return {
        "selection_hash": h,
        "first_evaluated_at": sel["first_evaluated_at"],
        "evaluations_of_this_selection": sel["evaluations"],
        "distinct_selections_evaluated": distinct,
        "reused_with_new_selection": distinct > 1,
    }


# -- helpers ------------------------------------------------------------------------------------
def _baseline_walk_forward(
    x: pd.DataFrame, y: pd.Series, folds: list[Any], fns: dict[str, bl.BaselineFn]
) -> dict[str, dict[str, Any]]:
    out = {}
    for name, fn in fns.items():
        losses = {}
        for f in folds:
            p = fn(x[f.train], x[f.valid], y[f.train])
            losses[f.season] = ev.log_loss(y[f.valid].to_numpy(), p)
        vals = list(losses.values())
        out[name] = {
            "mean_log_loss": float(np.mean(vals)),
            "std_log_loss": float(np.std(vals, ddof=1)),
            "folds": {str(k): v for k, v in losses.items()},
        }
    return out


def _ablations(
    x: pd.DataFrame, y: pd.Series, folds: list[Any], tier: Tier, c: float, seed: int
) -> list[dict[str, Any]]:
    """Cumulative feature-group ablation with the logistic model (antisymmetric columns)."""
    order = ["elo", "form", "h2h", "venue"] + (["toss", "squad"] if tier == "post_toss" else [])
    anti = set(antisymmetric_columns(tier))
    rows: list[dict[str, Any]] = []
    cols: list[str] = []
    for group in order:
        cols = cols + [col for col in FEATURE_GROUPS[group] if col in anti]
        spec_cols = list(cols)
        model_losses = {}
        for f in folds:
            m = make_model("logreg", {"C": c}, tier, seed)
            m.columns = spec_cols
            m.fit(x[f.train], y[f.train])
            model_losses[f.season] = ev.log_loss(y[f.valid].to_numpy(), m.predict_proba(x[f.valid]))
        rows.append(
            {
                "groups": "+".join(order[: order.index(group) + 1]),
                "n_features": len(spec_cols),
                "mean_log_loss": float(np.mean(list(model_losses.values()))),
            }
        )
    return rows


def _segment_metrics(df: pd.DataFrame, key: str, p_col: str) -> list[dict[str, Any]]:
    out = []
    for val, g in df.groupby(key):
        out.append(
            {
                key: str(val),
                "n": len(g),
                "log_loss": ev.log_loss(g["y"].to_numpy(), g[p_col].to_numpy()),
                "accuracy": ev.accuracy(g["y"].to_numpy(), g[p_col].to_numpy()),
            }
        )
    return out


# -- per-tier pipeline ---------------------------------------------------------------------------
def run_tier(
    fs: FeatureSet, tier: Tier, cfg: ExperimentConfig, elo: EloParams, ledger: Path, data_sha: str
) -> TierOutcome:
    """Select, calibrate, evaluate once on the holdout, and refit for serving."""
    frame = fs.frame[fs.frame["is_decided"]].reset_index(drop=True)
    x = frame[feature_columns(tier)].astype(float)
    y = frame["a_wins"].astype(float)
    seasons = frame["season_year"]
    dev, hold = dev_holdout_masks(seasons, cfg.dev_last, cfg.holdout)
    xd, yd, sd = (
        x[dev].reset_index(drop=True),
        y[dev].reset_index(drop=True),
        seasons[dev].reset_index(drop=True),
    )
    folds = walk_forward_folds(sd, cfg.first_valid, cfg.dev_last)
    fns = bl.baselines_for(tier, elo.home_bonus)

    with timed(logger, "model_selection", tier=tier):
        baseline_wf = _baseline_walk_forward(xd, yd, folds, fns)
        grid_table: list[dict[str, Any]] = []
        best: dict[str, CVResult] = {}
        for name, spec in SPECS.items():
            for params in spec.grid:
                res = walk_forward(name, params, xd, yd, folds, tier, cfg.seed)
                grid_table.append(res.summary())
                if name not in best or res.mean < best[name].mean:
                    best[name] = res
        for params in blend_grid(best):
            res = walk_forward("blend", params, xd, yd, folds, tier, cfg.seed)
            grid_table.append(res.summary())
            if "blend" not in best or res.mean < best["blend"].mean:
                best["blend"] = res
        chosen, rule = select_model(best)
        chosen_res = best[chosen]

    cal_cmp = time_ordered_calibration(chosen_res.oof, yd, sd)
    method = choose_method(cal_cmp)
    ablation = _ablations(xd, yd, folds, tier, float(best["logreg"].params["C"]), cfg.seed)

    # Time-ordered calibrated OOF predictions (for dev-era segment analysis).
    oof_idx = chosen_res.oof.index
    oof = pd.DataFrame(
        {
            "match_id": frame.loc[dev].reset_index(drop=True).loc[oof_idx, "match_id"].to_numpy(),
            "season_year": sd.loc[oof_idx].to_numpy(),
            "y": yd.loc[oof_idx].to_numpy(),
            "p_raw": chosen_res.oof.to_numpy(),
        }
    )
    dev_frame = frame.loc[dev].reset_index(drop=True)
    oof["stage"] = dev_frame.loc[oof_idx, "stage"].to_numpy()

    # Freeze and log the selection, then touch the holdout exactly once.
    selection = {
        "tier": tier,
        "model": chosen,
        "params": chosen_res.params,
        "calibration": method,
        "elo": asdict(elo),
        "features": feature_columns(tier),
        "data_sha256": data_sha,
    }
    access = log_holdout_access(ledger, tier, selection)
    log_event(
        logger,
        "holdout_access",
        tier=tier,
        **{k: v for k, v in access.items() if k != "first_evaluated_at"},
    )

    final = make_model(chosen, chosen_res.params, tier, cfg.seed).fit(xd, yd)
    calibrator = Calibrator(method).fit(chosen_res.oof.to_numpy(), yd.loc[oof_idx].to_numpy())
    xh, yh = x[hold], y[hold].to_numpy()
    p_model = calibrator.symmetric_transform(final.predict_proba(xh))
    hold_df = pd.DataFrame(
        {
            "match_id": frame.loc[hold, "match_id"].to_numpy(),
            "season_year": seasons[hold].to_numpy(),
            "stage": frame.loc[hold, "stage"].to_numpy(),
            "y": yh,
            "p_model": p_model,
        }
    )
    holdout_metrics: dict[str, Any] = {
        "model": {
            **ev.metric_suite(yh, p_model),
            "ci": ev.bootstrap_ci(yh, p_model, cfg.n_boot, cfg.seed),
        }
    }
    comparisons = {}
    for name, fn in fns.items():
        p_b = fn(xd, xh, yd)
        hold_df[f"p_{name}"] = p_b
        holdout_metrics[name] = ev.metric_suite(yh, p_b)
        comparisons[name] = {
            **ev.paired_bootstrap(yh, p_model, p_b, cfg.n_paired, cfg.seed),
            "diebold_mariano": ev.diebold_mariano(yh, p_model, p_b),
        }
    guard = ev.too_good_check(holdout_metrics["model"], cfg.too_good_auc, cfg.too_good_acc)
    if guard["suspicious"]:
        log_event(logger, "too_good_warning", 30, tier=tier, reasons=";".join(guard["reasons"]))

    # Global importance on development data only: fit on seasons <= dev_last-3, evaluate on the last 3.
    imp_train = sd <= cfg.dev_last - 3
    imp_model = make_model(chosen, chosen_res.params, tier, cfg.seed).fit(
        xd[imp_train], yd[imp_train]
    )
    importance = permutation_importance(
        imp_model,
        xd[~imp_train],
        yd[~imp_train],
        feature_columns(tier)
        if chosen != "logreg" and chosen != "elo_logit"
        else imp_model.columns,
        repeats=10,
        seed=cfg.seed,
    )

    # Serving model: the same frozen configuration refit on every decided match (dev + holdout).
    serve_model: Model = make_model(chosen, chosen_res.params, tier, cfg.seed).fit(x, y)
    serve_cal_p = np.concatenate([chosen_res.oof.to_numpy(), final.predict_proba(xh)])
    serve_cal_y = np.concatenate([yd.loc[oof_idx].to_numpy(), yh])
    serve_cal = Calibrator(method).fit(serve_cal_p, serve_cal_y)
    bundle = ModelBundle(
        tier=tier,
        model=serve_model,
        calibrator=serve_cal,
        feature_columns=feature_columns(tier),
        feature_params=fs.state.params,
        trained_through=int(seasons.max()),
        model_name=chosen,
        params=chosen_res.params,
    )

    oof_cal = Calibrator(method)
    cal_p = np.full(len(oof), np.nan)
    for season in sorted(oof["season_year"].unique()):
        hist, cur = (
            (oof["season_year"] < season).to_numpy(),
            (oof["season_year"] == season).to_numpy(),
        )
        cal_p[cur] = (
            oof_cal.fit(
                oof.loc[hist, "p_raw"].to_numpy(), oof.loc[hist, "y"].to_numpy()
            ).symmetric_transform(oof.loc[cur, "p_raw"].to_numpy())
            if hist.sum() > 50
            else oof.loc[cur, "p_raw"].to_numpy()
        )
    oof["p"] = cal_p

    metrics = {
        "n_decided": len(frame),
        "n_dev": int(dev.sum()),
        "n_holdout": int(hold.sum()),
        "folds": [f.season for f in folds],
        "baselines_walk_forward": baseline_wf,
        "model_grid": grid_table,
        "best_per_family": {k: v.summary() for k, v in best.items()},
        "selection": {
            **rule,
            "params": chosen_res.params,
            "walk_forward_mean_log_loss": chosen_res.mean,
            "walk_forward_std_log_loss": chosen_res.std,
        },
        "calibration": {"comparison": cal_cmp, "chosen": method},
        "ablation": ablation,
        "oof_by_stage": _segment_metrics(
            oof.assign(stage_group=np.where(oof["stage"] == "league", "league", "playoff")),
            "stage_group",
            "p",
        ),
        "oof_by_era": _segment_metrics(
            oof.assign(era=np.where(oof["season_year"] >= 2023, "impact_2023+", "pre_2023")),
            "era",
            "p",
        ),
        "oof_by_season": _segment_metrics(oof, "season_year", "p"),
        "holdout_access": access,
        "holdout": holdout_metrics,
        "holdout_vs_baselines": comparisons,
        "holdout_reliability": ev.reliability_table(yh, p_model, 8),
        "holdout_by_stage": _segment_metrics(
            hold_df.assign(stage_group=np.where(hold_df["stage"] == "league", "league", "playoff")),
            "stage_group",
            "p_model",
        ),
        "holdout_by_season": _segment_metrics(hold_df, "season_year", "p_model"),
        "too_good_guard": guard,
        "permutation_importance": importance.to_dict(orient="records"),
    }
    return TierOutcome(bundle, metrics, hold_df, oof)


def run_experiment(
    settings: Settings,
    matches: pd.DataFrame,
    players: pd.DataFrame,
    data_sha: str,
    register: bool = True,
) -> tuple[dict[str, Any], dict[str, TierOutcome], FeatureSet]:
    """Run the whole experiment; optionally register serving models. Returns (metrics, outcomes, features)."""
    cfg = ExperimentConfig.from_settings(settings)
    base_params = feature_params_from_settings(settings)
    with timed(logger, "elo_tuning"):
        elo_res = tune_elo(
            matches, cfg.elo_grid, base_params.elo, cfg.seed, cfg.first_valid, cfg.dev_last
        )
    tuned = feature_params_from_settings(settings, elo_override=elo_res["best"])
    with timed(logger, "features"):
        fs = FeatureBuilder(tuned).build(matches, players)
    ledger = settings.path("reports_dir") / "holdout_ledger.json"
    outcomes: dict[str, TierOutcome] = {}
    for tier in TIERS:
        with timed(logger, "tier", tier=tier):
            outcomes[tier] = run_tier(fs, tier, cfg, tuned.elo, ledger, data_sha)
    with timed(logger, "score_regression"):
        score = evaluate_score_models(
            build_score_frame(matches, fs),
            cfg.first_valid,
            cfg.dev_last,
            cfg.holdout,
            cfg.seed,
            cfg.n_boot,
        )
    decided = fs.frame[fs.frame["is_decided"]].reset_index(drop=True)
    latest = int(decided["season_year"].max())
    drift = drift_report(
        decided,
        feature_columns("post_toss"),
        (decided["season_year"] <= cfg.dev_last).to_numpy(),
        (decided["season_year"] == latest).to_numpy(),
        float(settings.get("monitoring.psi_warn", 0.1)),
        float(settings.get("monitoring.psi_alert", 0.25)),
    )
    commit = git_commit(settings.root)
    metrics: dict[str, Any] = {
        "generated_by": "creaseiq train",
        "git_commit": commit,
        "data_sha256": data_sha,
        "seed": cfg.seed,
        "splits": {
            "first_validation_season": cfg.first_valid,
            "dev_last_season": cfg.dev_last,
            "holdout_seasons": cfg.holdout,
            "scheme": "expanding-window walk-forward by season",
        },
        "elo_tuning": elo_res,
        "elo_params_used": asdict(tuned.elo),
        "tiers": {t: o.metrics for t, o in outcomes.items()},
        "score_regression": score,
        "drift": {
            "reference": f"seasons <= {cfg.dev_last}",
            "current": f"season {latest}",
            "table": drift.to_dict(orient="records"),
        },
    }
    if register:
        registry = ModelRegistry(settings.path("models_dir"))
        for tier_name, o in outcomes.items():
            summary = {
                "holdout_log_loss": o.metrics["holdout"]["model"]["log_loss"],
                "holdout_auc": o.metrics["holdout"]["model"]["auc"],
            }
            entry = registry.register(
                o.bundle, data_sha256=data_sha, git_commit=commit, metrics=summary
            )
            metrics["tiers"][tier_name]["registry_run_id"] = entry["run_id"]
    return metrics, outcomes, fs
