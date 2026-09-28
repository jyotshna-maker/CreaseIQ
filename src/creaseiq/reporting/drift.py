"""Feature-drift monitoring with the Population Stability Index (FR-21, NFR-07).

PSI = Σ (a_i − e_i) · ln(a_i / e_i) over bins defined by the reference distribution's
quantiles. Rules of thumb: < 0.1 stable, 0.1–0.25 moderate shift, > 0.25 major shift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-4


def psi(reference: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
    """Population Stability Index of ``current`` against ``reference``."""
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref, cur = ref[~np.isnan(ref)], cur[~np.isnan(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 2:  # constant reference: all mass in one bin
        return 0.0 if np.allclose(cur, ref[0]) else float("inf")
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(ref, edges)[0] / len(ref)
    a = np.histogram(cur, edges)[0] / len(cur)
    e, a = np.clip(e, EPS, None), np.clip(a, EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def drift_report(
    frame: pd.DataFrame,
    columns: list[str],
    reference_mask: np.ndarray,
    current_mask: np.ndarray,
    warn: float = 0.1,
    alert: float = 0.25,
) -> pd.DataFrame:
    """PSI per feature with a status label."""
    rows = []
    for col in columns:
        value = psi(
            frame.loc[reference_mask, col].to_numpy(), frame.loc[current_mask, col].to_numpy()
        )
        status = "alert" if value > alert else "warn" if value > warn else "stable"
        rows.append({"feature": col, "psi": value, "status": status})
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)
