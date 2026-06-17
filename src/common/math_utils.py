"""Shared numeric helpers."""
from __future__ import annotations

import math as _math


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp *value* to [low, high]."""
    return max(low, min(high, float(value)))


def binom_pmf(n: int, k: int, p: float) -> float:
    """Binomial probability mass function P(X=k) under Binomial(n, p)."""
    return _math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    """Exact two-sided binomial test p-value (no scipy dependency)."""
    if n <= 0:
        return 1.0
    # Compute each pmf once (was evaluated twice per term — 2x the factorial work).
    pmfs = [binom_pmf(n, i, p0) for i in range(n + 1)]
    p_obs = pmfs[k]
    return min(1.0, sum(pmf for pmf in pmfs if pmf <= p_obs + 1e-15))
