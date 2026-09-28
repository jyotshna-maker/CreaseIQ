"""Unsupervised venue profiling with k-means (ADR-001: unsupervised-learning component).

Venues are described by three standardised features: shrunk first-innings average, shrunk
chase win rate, and the share of toss winners choosing to field. k is chosen by silhouette
score over a small range. With about 20 eligible venues the clusters are descriptive
("high-scoring chase grounds", ...). They are not used as model inputs, so no leakage risk
arises.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FEATURES = ["avg_first_innings_shrunk", "chase_win_rate_shrunk", "field_share"]


@dataclass
class VenueClustering:
    """Result of :func:`cluster_venues`."""

    k: int
    silhouette_by_k: dict[int, float]
    assignments: pd.DataFrame  # venue_id, venue, cluster, label, features...
    centroids: pd.DataFrame


def _label(row: pd.Series, med: pd.Series) -> str:
    # Labels are relative to the median venue: chase rates are above 50% almost everywhere,
    # so "less chase-friendly" is accurate where "defend-friendly" would overstate it.
    score = (
        "higher-scoring"
        if row["avg_first_innings_shrunk"] >= med["avg_first_innings_shrunk"]
        else "lower-scoring"
    )
    chase = (
        "more chase-friendly"
        if row["chase_win_rate_shrunk"] >= med["chase_win_rate_shrunk"]
        else "less chase-friendly"
    )
    return f"{score}, {chase}"


def cluster_venues(
    profiles: pd.DataFrame, min_matches: int = 10, k_range: range = range(2, 6), seed: int = 42
) -> VenueClustering:
    """Cluster venues with at least ``min_matches`` matches; choose k by silhouette score."""
    eligible = profiles[profiles["matches"] >= min_matches].reset_index(drop=True)
    x = StandardScaler().fit_transform(eligible[FEATURES].to_numpy())
    scores: dict[int, float] = {}
    models: dict[int, KMeans] = {}
    for k in k_range:
        if k >= len(eligible):
            break
        km = KMeans(n_clusters=k, n_init=20, random_state=seed).fit(x)
        scores[k] = float(silhouette_score(x, km.labels_))
        models[k] = km
    best_k = max(scores, key=lambda kk: scores[kk])
    labels = models[best_k].labels_
    assigned = eligible[["venue_id", "venue", "matches", *FEATURES]].assign(cluster=labels)
    centroids = assigned.groupby("cluster")[FEATURES].mean()
    med = eligible[FEATURES].median()
    centroids["label"] = [_label(r, med) for _, r in centroids.iterrows()]
    assigned["label"] = assigned["cluster"].map(centroids["label"])
    return VenueClustering(
        best_k,
        scores,
        assigned.sort_values(["cluster", "venue"]).reset_index(drop=True),
        centroids.reset_index(),
    )


def silhouette_is_meaningful(result: VenueClustering) -> bool:
    """Silhouette above 0.25 indicates at least weak structure (common rule of thumb)."""
    return bool(np.nanmax(list(result.silhouette_by_k.values())) > 0.25)
