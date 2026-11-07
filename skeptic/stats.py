"""Aggregate statistics with the same definitions as the kit's market report, plus uncertainty."""
from __future__ import annotations

import math

import numpy as np


def sign_test_p(wins: int, losses: int) -> float | None:
    """Exact two-sided sign test, ties excluded: p = min(1, 2 * sum_{k<=min(w,l)} C(n,k) / 2^n)."""
    n = wins + losses
    if n == 0:
        return None
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def median_int(values) -> int:
    """Integer median; for an even count, the integer (floor) mean of the middle two."""
    ordered = sorted(int(v) for v in values)
    if not ordered:
        raise ValueError("median of empty list")
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def mean_int(values) -> int:
    values = [int(v) for v in values]
    return sum(values) // len(values)


def aggregate(rows: list[dict]) -> dict:
    """rows: per-path dicts with final_cash, bh_final, initial_cash, max_drawdown_bps, trades."""
    if not rows:
        return {"paths": 0}
    excess = [(r["final_cash"] - r["bh_final"]) * 10000 // r["initial_cash"] for r in rows]
    wins = sum(r["final_cash"] > r["bh_final"] for r in rows)
    losses = sum(r["final_cash"] < r["bh_final"] for r in rows)
    beat_cash = sum(r["final_cash"] > r["initial_cash"] for r in rows)
    dd = [r["max_drawdown_bps"] for r in rows]
    return {
        "paths": len(rows),
        "wins": wins,
        "losses": losses,
        "ties": len(rows) - wins - losses,
        "beat_cash": beat_cash,
        "median_excess_bps": median_int(excess),
        "mean_excess_bps": mean_int(excess),
        "mean_max_drawdown_bps": mean_int(dd),
        "sign_p": sign_test_p(wins, losses),
        "total_trades": sum(r.get("trades", 0) for r in rows),
    }


def bootstrap_median_ci(values, resamples: int, seed: int, level: float = 0.95) -> tuple[int, int]:
    """Percentile bootstrap CI for the median, resampling paths with replacement."""
    arr = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(resamples, len(arr)))
    meds = np.median(arr[idx], axis=1)
    lo, hi = np.quantile(meds, [(1 - level) / 2, 1 - (1 - level) / 2])
    return int(math.floor(lo)), int(math.ceil(hi))


def wilson_ci(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    phat = successes / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))
