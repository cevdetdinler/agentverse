"""Signal features. Value at bar t uses closes p[0..t] only; NaN where history is too short.

Floats are allowed here (and only here): features decide *when* to trade, never *how much money*.
Every rolling quantity is computed per window with sliding_window_view, so the value at t depends only
on that window's prices and is identical on a prefix and on the full path.

All functions work along the LAST axis, so they accept one path (n,) or a batch of paths (K, n).
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as _swv


def _arr(prices) -> np.ndarray:
    return np.asarray(prices, dtype=np.float64)


def _pad(values: np.ndarray, shape) -> np.ndarray:
    """Right-align `values` along the last axis into an array of `shape`, NaN at the front."""
    out = np.full(shape, np.nan)
    m = values.shape[-1]
    if m:
        out[..., shape[-1] - m:] = values
    return out


def _windows(p: np.ndarray, w: int) -> np.ndarray:
    return _swv(p, w, axis=-1)


def sma(p: np.ndarray, w: int) -> np.ndarray:
    if w > p.shape[-1]:
        return np.full(p.shape, np.nan)
    return _pad(_windows(p, w).mean(axis=-1), p.shape)


def f_return(p: np.ndarray, lookback: int) -> np.ndarray:
    out = np.full(p.shape, np.nan)
    if lookback < p.shape[-1]:
        out[..., lookback:] = p[..., lookback:] / p[..., :-lookback] - 1.0
    return out


def f_price_vs_sma(p: np.ndarray, window: int) -> np.ndarray:
    return p / sma(p, window) - 1.0


def f_sma_ratio(p: np.ndarray, fast: int, slow: int) -> np.ndarray:
    return sma(p, fast) / sma(p, slow) - 1.0


def f_rsi(p: np.ndarray, window: int) -> np.ndarray:
    """Simple-average RSI over the last `window` one-bar changes (needs window+1 prices)."""
    if window + 1 > p.shape[-1]:
        return np.full(p.shape, np.nan)
    win = _windows(np.diff(p, axis=-1), window)
    gain = np.where(win > 0, win, 0.0).mean(axis=-1)
    loss = np.where(win < 0, -win, 0.0).mean(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + gain / loss)
    rsi = np.where(loss == 0, np.where(gain > 0, 100.0, 50.0), rsi)
    return _pad(rsi, p.shape)


def f_drawdown_from_high(p: np.ndarray, lookback: int) -> np.ndarray:
    if lookback + 1 > p.shape[-1]:
        return np.full(p.shape, np.nan)
    hi = _windows(p, lookback + 1).max(axis=-1)
    return _pad(p[..., lookback:] / hi - 1.0, p.shape)


def f_rise_from_low(p: np.ndarray, lookback: int) -> np.ndarray:
    if lookback + 1 > p.shape[-1]:
        return np.full(p.shape, np.nan)
    lo = _windows(p, lookback + 1).min(axis=-1)
    return _pad(p[..., lookback:] / lo - 1.0, p.shape)


def f_breakout(p: np.ndarray, lookback: int) -> np.ndarray:
    """p[t] / max(p[t-L..t-1]) - 1 (excludes the current bar)."""
    if lookback + 1 > p.shape[-1]:
        return np.full(p.shape, np.nan)
    prev_hi = _windows(p[..., :-1], lookback).max(axis=-1)  # windows ending at t-1 for t >= L
    return _pad(p[..., lookback:] / prev_hi - 1.0, p.shape)


def f_volatility(p: np.ndarray, lookback: int) -> np.ndarray:
    """Population std of the last `lookback` one-bar log returns."""
    if lookback + 1 > p.shape[-1]:
        return np.full(p.shape, np.nan)
    r = np.diff(np.log(p), axis=-1)
    return _pad(_windows(r, lookback).std(axis=-1), p.shape)


def f_down_streak(p: np.ndarray) -> np.ndarray:
    out = np.zeros(p.shape)
    run = np.zeros(p.shape[:-1])
    for i in range(1, p.shape[-1]):
        run = np.where(p[..., i] < p[..., i - 1], run + 1, 0)
        out[..., i] = run
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
            prev = np.concatenate([np.full(f.shape[:-1] + (1,), np.nan), f[..., :-1]], axis=-1)
            if op == "crosses_above":
                out = (prev <= value) & (f > value)
            else:
                out = (prev >= value) & (f < value)
        else:
            raise ValueError(f"unknown op {op!r}")
    return out & ~np.isnan(f)


def condition_array(name: str, params: dict, op: str, value: float, prices) -> np.ndarray:
    return apply_op(feature_series(name, params, prices), op, value)


def condition_series(name: str, params: dict, op: str, value: float, prices) -> list[bool]:
    return condition_array(name, params, op, value, prices).tolist()
