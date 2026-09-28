"""Small, well-tested statistics toolkit used by the analytics (FR-08).

Every result reports an **effect size with a confidence interval**, not just a p-value
(research R4). When a test is not significant, the minimum detectable effect says how
large an effect would have been needed for the sample to detect it.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class ProportionTest:
    """Result of a one-sample test of a proportion against ``p0``."""

    successes: int
    n: int
    rate: float
    ci_low: float
    ci_high: float
    p0: float
    p_value: float
    mde: float  # minimum detectable effect (absolute, two-sided alpha=0.05, power=0.8)

    @property
    def effect(self) -> float:
        """Rate minus the null value, in percentage points / 100."""
        return self.rate - self.p0

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form."""
        return {**asdict(self), "effect": self.effect}


def wilson_ci(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Returns (nan, nan) when n == 0."""
    if n == 0:
        return (math.nan, math.nan)
    z = float(stats.norm.ppf(1 - alpha / 2))
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def minimum_detectable_effect(
    n: int, p0: float = 0.5, alpha: float = 0.05, power: float = 0.8
) -> float:
    """Approximate absolute MDE for a one-sample proportion test at the given n."""
    if n <= 0:
        return math.nan
    z_a = float(stats.norm.ppf(1 - alpha / 2))
    z_b = float(stats.norm.ppf(power))
    return (z_a + z_b) * math.sqrt(p0 * (1 - p0) / n)


def binomial_test(successes: int, n: int, p0: float = 0.5) -> ProportionTest:
    """Exact two-sided binomial test with a Wilson CI and the MDE."""
    if n == 0:
        return ProportionTest(0, 0, math.nan, math.nan, math.nan, p0, math.nan, math.nan)
    lo, hi = wilson_ci(successes, n)
    p = float(stats.binomtest(successes, n, p0).pvalue)
    return ProportionTest(
        successes, n, successes / n, lo, hi, p0, p, minimum_detectable_effect(n, p0)
    )


@dataclass(frozen=True)
class TwoProportionTest:
    """Result of a two-sample z-test for proportions."""

    rate_a: float
    n_a: int
    rate_b: float
    n_b: int
    diff: float
    ci_low: float
    ci_high: float
    z: float
    p_value: float

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form."""
        return asdict(self)


def two_proportion_ztest(s_a: int, n_a: int, s_b: int, n_b: int) -> TwoProportionTest:
    """Pooled two-proportion z-test; the CI on the difference uses the unpooled SE."""
    if n_a == 0 or n_b == 0:
        return TwoProportionTest(
            math.nan, n_a, math.nan, n_b, math.nan, math.nan, math.nan, math.nan, math.nan
        )
    pa, pb = s_a / n_a, s_b / n_b
    pooled = (s_a + s_b) / (n_a + n_b)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (pa - pb) / se_pooled if se_pooled > 0 else 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    se = math.sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    return TwoProportionTest(
        pa, n_a, pb, n_b, pa - pb, pa - pb - 1.96 * se, pa - pb + 1.96 * se, z, p
    )


@dataclass(frozen=True)
class ChiSquareTest:
    """Chi-square test of independence with Cramér's V as the effect size."""

    chi2: float
    dof: int
    p_value: float
    cramers_v: float
    table: list[list[int]]

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form."""
        return asdict(self)


def chi_square(table: np.ndarray) -> ChiSquareTest:
    """Chi-square test of independence on a contingency table (no Yates correction)."""
    arr = np.asarray(table, dtype=float)
    chi2, p, dof, _ = stats.chi2_contingency(arr, correction=False)
    n = arr.sum()
    k = min(arr.shape) - 1
    v = math.sqrt(chi2 / (n * k)) if n > 0 and k > 0 else math.nan
    return ChiSquareTest(float(chi2), int(dof), float(p), v, arr.astype(int).tolist())


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (controls the family-wise error rate)."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def shrunk_rate(successes: float, n: float, prior: float, m: float) -> float:
    """Empirical-Bayes style shrinkage: ``(successes + m*prior) / (n + m)``.

    With ``n == 0`` this returns the prior; as ``n`` grows it approaches the raw rate.
    """
    if n + m <= 0:
        return prior
    return (successes + m * prior) / (n + m)


def shrunk_mean(total: float, n: float, prior_mean: float, m: float) -> float:
    """Shrink a sample mean toward ``prior_mean`` with pseudo-count ``m``."""
    if n + m <= 0:
        return prior_mean
    return (total + m * prior_mean) / (n + m)
