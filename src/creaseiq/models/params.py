"""Build typed parameter objects from ``configs/config.yaml`` (NFR-06: config-driven)."""

from __future__ import annotations

from typing import Any

from creaseiq.config import Settings
from creaseiq.features.builder import FeatureParams
from creaseiq.features.elo import EloParams


def elo_params_from_mapping(cfg: dict[str, Any]) -> EloParams:
    """EloParams from a ``features.elo``-shaped mapping (unknown keys ignored)."""
    fields = EloParams.__dataclass_fields__
    return EloParams(**{k: v for k, v in cfg.items() if k in fields})


def feature_params_from_settings(
    settings: Settings, elo_override: dict[str, Any] | None = None
) -> FeatureParams:
    """FeatureParams from settings, optionally overriding Elo hyperparameters (tuning)."""
    elo_cfg = dict(settings.get("features.elo", {}) or {})
    if elo_override:
        elo_cfg.update(elo_override)
    return FeatureParams(
        elo=elo_params_from_mapping(elo_cfg),
        venue_prior_m=float(settings.get("features.shrinkage_m", 10)),
        h2h_recent_seasons=int(settings.get("features.h2h_recent_seasons", 5)),
        seed=settings.seed,
    )
