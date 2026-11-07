"""Signal features. Value at bar t uses closes p[0..t] only; NaN where history is too short.

Floats are allowed here (and only here): features decide *when* to trade, never *how much money*.
Every rolling quantity is computed per window with sliding_window_view, so the value at t
depends only on that window's prices and is bit-identical on a prefix and on the full path.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

NAN = float("nan")


def _arr(prices) -> np.ndarray:
    return np.asarray(prices, dtype=np.float64)


def _pad(values: np.ndarray, n: int) -> np.ndarray:
    """Right-align `values` into an array of length n, NaN at the front."""
    out = np.full(n, np.nan)
    if len(values):
        out[n - len(values):] = values
    return out


def sma(p: np.ndarray, w: int) -> np.ndarray:
    n = len(p)
    if w > n:
        return np.full(n, np.nan)
    return _pad(sliding_window_view(p, w).mean(axis=1), n)


def f_return(p: np.ndarray, lookback: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    if lookback < n:
        out[lookback:] = p[lookback:] / p[:-lookback] - 1.0
    return out


def f_price_vs_sma(p: np.ndarray, window: int) -> np.ndarray:
    return p / sma(p, window) - 1.0


def f_sma_ratio(p: np.ndarray, fast: int, slow: int) -> np.ndarray:
    out = sma(p, fast) / sma(p, slow) - 1.0
    return out


def f_rsi(p: np.ndarray, window: int) -> np.ndarray:
    """Simple-average RSI over the last `window` one-bar changes (needs window+1 prices)."""
    n = len(p)
    if window + 1 > n:
        return np.full(n, np.nan)
    d = np.diff(p)
    win = sliding_window_view(d, window)
    gain = np.where(win > 0, win, 0.0).mean(axis=1)
    loss = np.where(win < 0, -win, 0.0).mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + gain / loss)
    rsi = np.where(loss == 0, np.where(gain > 0, 100.0, 50.0), rsi)
    return _pad(rsi, n)


def f_drawdown_from_high(p: np.ndarray, lookback: int) -> np.ndarray:
    n = len(p)
    if lookback + 1 > n:
        return np.full(n, np.nan)
    hi = sliding_window_view(p, lookback + 1).max(axis=1)
    return _pad(p[lookback:] / hi - 1.0, n)


def f_rise_from_low(p: np.ndarray, lookback: int) -> np.ndarray:
    n = len(p)
    if lookback + 1 > n:
        return np.full(n, np.nan)
    lo = sliding_window_view(p, lookback + 1).min(axis=1)
    return _pad(p[lookback:] / lo - 1.0, n)


def f_breakout(p: np.ndarray, lookback: int) -> np.ndarray:
    """p[t] / max(p[t-L..t-1]) - 1 (excludes the current bar)."""
    n = len(p)
    if lookback + 1 > n:
        return np.full(n, np.nan)
    prev_hi = sliding_window_view(p[:-1], lookback).max(axis=1)  # windows ending at t-1, t>=L
    return _pad(p[lookback:] / prev_hi - 1.0, n)


def f_volatility(p: np.ndarray, lookback: int) -> np.ndarray:
    """Population std of the last `lookback` one-bar log returns."""
    n = len(p)
    if lookback + 1 > n:
        return np.full(n, np.nan)
    r = np.diff(np.log(p))
    return _pad(sliding_window_view(r, lookback).std(axis=1), n)


def f_down_streak(p: np.ndarray) -> np.ndarray:
    n = len(p)
    out = np.zeros(n)
    run = 0
    for i in range(1, n):
        run = run + 1 if p[i] < p[i - 1] else 0
        out[i] = run
    return out


def feature_series(name: str, params: dict, prices) -> np.ndarray:
    p = _arr(prices)
    if name == "return":
        return f_return(p, params["lookback"])
    if name == "price_vs_sma":
        return f_price_vs_sma(p, params["window"])
    if name == "sma_ratio":
        return f_sma_ratio(p, params["fast"], params["slow"])
    if name == "rsi":
        return f_rsi(p, params["window"])
    if name == "drawdown_from_high":
        return f_drawdown_from_high(p, params["lookback"])
    if name == "rise_from_low":
        return f_rise_from_low(p, params["lookback"])
    if name == "breakout":
        return f_breakout(p, params["lookback"])
    if name == "volatility":
        return f_volatility(p, params["lookback"])
    if name == "down_streak":
        return f_down_streak(p)
    raise ValueError(f"unknown feature {name!r}")


def apply_op(f: np.ndarray, op: str, value: float) -> np.ndarray:
    """Boolean series; NaN (not enough history) is always False."""
    with np.errstate(invalid="ignore"):
        if op == "<":
            out = f < value
        elif op == "<=":
            out = f <= value
        elif op == ">":
            out = f > value
        elif op == ">=":
            out = f >= value
        elif op in ("crosses_above", "crosses_below"):
            prev = np.concatenate(([np.nan], f[:-1]))
            if op == "crosses_above":
                out = (prev <= value) & (f > value)
            else:
                out = (prev >= value) & (f < value)
        else:
            raise ValueError(f"unknown op {op!r}")
    return out & ~np.isnan(f)


def condition_series(name: str, params: dict, op: str, value: float, prices) -> list[bool]:
    return apply_op(feature_series(name, params, prices), op, value).tolist()
