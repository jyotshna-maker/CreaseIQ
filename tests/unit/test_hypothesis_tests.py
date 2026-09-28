"""Statistics toolkit: known values, edge cases and property-based checks (FR-08)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint, proportions_ztest

from creaseiq.analytics.hypothesis_tests import (
    binomial_test,
    chi_square,
    holm_adjust,
    minimum_detectable_effect,
    shrunk_mean,
    shrunk_rate,
    two_proportion_ztest,
    wilson_ci,
)


@pytest.mark.parametrize(("s", "n"), [(628, 1218), (0, 10), (10, 10), (7, 30)])
def test_wilson_matches_statsmodels(s: int, n: int) -> None:
    lo, hi = wilson_ci(s, n)
    ref = proportion_confint(s, n, method="wilson")
    assert lo == pytest.approx(ref[0], abs=1e-9) and hi == pytest.approx(ref[1], abs=1e-9)


def test_empty_inputs() -> None:
    assert all(math.isnan(x) for x in wilson_ci(0, 0))
    assert math.isnan(binomial_test(0, 0).rate)
    assert math.isnan(two_proportion_ztest(1, 0, 1, 2).diff)
    assert math.isnan(minimum_detectable_effect(0))


def test_binomial_test_values() -> None:
    t = binomial_test(628, 1218)
    assert t.rate == pytest.approx(628 / 1218)
    assert 0.2 < t.p_value < 0.4
    assert t.mde == pytest.approx(0.0401, abs=1e-3)
    assert t.as_dict()["effect"] == pytest.approx(628 / 1218 - 0.5)


def test_two_proportion_matches_statsmodels() -> None:
    t = two_proportion_ztest(151, 286, 515, 932)
    z, p = proportions_ztest([151, 515], [286, 932])
    assert t.z == pytest.approx(z) and t.p_value == pytest.approx(p)
    assert t.ci_low < t.diff < t.ci_high


def test_chi_square_effect_size() -> None:
    res = chi_square(np.array([[223, 185], [367, 443]]))
    assert res.dof == 1 and res.p_value < 0.01
    assert 0 < res.cramers_v < 0.2


def test_holm_matches_statsmodels() -> None:
    ps = [0.01, 0.04, 0.03, 0.5, 0.2]
    assert holm_adjust(ps) == pytest.approx(list(multipletests(ps, method="holm")[1]))


@given(
    s=st.integers(0, 500),
    extra=st.integers(0, 500),
    prior=st.floats(0.01, 0.99),
    m=st.floats(0.0, 100.0),
)
def test_shrunk_rate_is_between_raw_and_prior(s: int, extra: int, prior: float, m: float) -> None:
    n = s + extra
    value = shrunk_rate(s, n, prior, m)
    lo, hi = sorted([prior, s / n if n else prior])
    assert lo - 1e-12 <= value <= hi + 1e-12


def test_shrinkage_limits() -> None:
    assert shrunk_rate(0, 0, 0.45, 10) == 0.45
    assert shrunk_rate(0, 0, 0.45, 0) == 0.45
    assert shrunk_mean(0, 0, 160.0, 0) == 160.0
    assert shrunk_mean(2000, 10, 160.0, 10) == pytest.approx(180.0)
    assert shrunk_rate(900, 1000, 0.5, 10) == pytest.approx(905 / 1010)
