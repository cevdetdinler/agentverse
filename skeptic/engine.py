"""Walk-forward execution engine. Integer pence and integer basis points only.

Written independently to the published execution contract of the AgentVerse market runner:
decision at bar i uses prices[0..i], the order fills at bar i+1 with adverse rounded slippage,
fixed fees, all-in/all-out, no leverage, forced liquidation at the last price.
Parity with the official runner is checked by eval/compare_parity.py (E1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .spec import positions_to_action


class EngineError(ValueError):
    pass


def buy_fill(price: int, bps: int) -> int:
    return (price * (10000 + bps) + 9999) // 10000


def sell_fill(price: int, bps: int) -> int:
    return price * (10000 - bps) // 10000


@dataclass
class SimResult:
    final_cash: int
    max_drawdown_bps: int
    trades: int            # completed round trips (entries that filled)
    fees_paid: int
    bars_in_position: int  # bars where shares > 0 after the decision
    decisions: int
    equity: list[int] = field(default_factory=list, repr=False)

    @property
    def exposure(self) -> float:
        return self.bars_in_position / self.decisions if self.decisions else 0.0


def max_drawdown_bps(equity) -> int:
    peak, worst = equity[0], 0
    for value in equity:
        if value > peak:
            peak = value
        dd = (peak - value) * 10000 // peak
        if dd > worst:
            worst = dd
    return worst


def simulate(prices, positions, initial_cash: int, fee: int, bps: int, keep_equity: bool = False) -> SimResult:
    """Reference implementation (scalar). `positions[i]` is the target for the decision at bar i."""
    n = len(prices)
    if n < 2:
        raise EngineError("need at least 2 prices")
    if len(positions) < n - 1:
        raise EngineError("positions must cover every decision bar")
    cash, shares, fees, trades, in_bars = initial_cash, 0, 0, 0, 0
    equity = [cash]
    for i in range(n - 1):
        action = positions_to_action(bool(positions[i]), shares)
        nxt = prices[i + 1]
        if action == "buy":
            fill = buy_fill(nxt, bps)
            units = max(0, cash - fee) // fill
            if units:
                cash -= units * fill + fee
                shares += units
                fees += fee
                trades += 1
        elif action == "sell" and shares:
            fill = sell_fill(nxt, bps)
            cash += shares * fill - fee
            fees += fee
            shares = 0
        if cash < 0:
            raise EngineError("order cannot cover fees; borrowing is not supported")
        if shares:
            in_bars += 1
        equity.append(cash + shares * nxt)
    if shares:
        cash += shares * sell_fill(prices[-1], bps) - fee
        fees += fee
        shares = 0
        if cash < 0:
            raise EngineError("final liquidation cannot cover fees")
    equity.append(cash)
    return SimResult(
        final_cash=cash,
        max_drawdown_bps=max_drawdown_bps(equity),
        trades=trades,
        fees_paid=fees,
        bars_in_position=in_bars,
        decisions=n - 1,
        equity=equity if keep_equity else [],
    )


def buy_and_hold_final(prices, initial_cash: int, fee: int, bps: int) -> int:
    buy = buy_fill(prices[1], bps)
    sell = sell_fill(prices[-1], bps)
    units = max(0, initial_cash - fee) // buy
    return initial_cash + units * (sell - buy) - (2 * fee if units else 0)


def excess_bps(final_cash: int, bh_final: int, initial_cash: int) -> int:
    return (final_cash - bh_final) * 10000 // initial_cash


def simulate_batch(prices, positions: np.ndarray, initial_cash: int, fee: int, bps: int) -> np.ndarray:
    """Final cash for K target-position rows at once (numpy int64). Must equal `simulate` row by row.

    Used by the permutation test (A2). Only final cash is needed there.
    """
    pos = np.asarray(positions, dtype=bool)
    if pos.ndim != 2:
        raise EngineError("positions must be a 2-D array (K x bars)")
    k = pos.shape[0]
    n = len(prices)
    cash = np.full(k, initial_cash, dtype=np.int64)
    shares = np.zeros(k, dtype=np.int64)
    for i in range(n - 1):
        want = pos[:, i]
        nxt = int(prices[i + 1])
        buy = want & (shares == 0)
        sell = (~want) & (shares > 0)
        if buy.any():
            fill = buy_fill(nxt, bps)
            units = np.maximum(0, cash - fee) // fill
            do = buy & (units > 0)
            cash = np.where(do, cash - units * fill - fee, cash)
            shares = np.where(do, shares + units, shares)
        if sell.any():
            fill = sell_fill(nxt, bps)
            cash = np.where(sell, cash + shares * fill - fee, cash)
            shares = np.where(sell, 0, shares)
        if (cash < 0).any():
            raise EngineError("order cannot cover fees; borrowing is not supported")
    held = shares > 0
    if held.any():
        cash = np.where(held, cash + shares * sell_fill(int(prices[-1]), bps) - fee, cash)
    return cash


def simulate_batch_paths(prices: np.ndarray, positions: np.ndarray, initial_cash: int, fee: int, bps: int) -> np.ndarray:
    """Final cash for K different price paths (K x n int64), each with its own target positions."""
    P = np.asarray(prices, dtype=np.int64)
    pos = np.asarray(positions, dtype=bool)
    k, n = P.shape
    cash = np.full(k, initial_cash, dtype=np.int64)
    shares = np.zeros(k, dtype=np.int64)
    for i in range(n - 1):
        want = pos[:, i]
        nxt = P[:, i + 1]
        buy = want & (shares == 0)
        sell = (~want) & (shares > 0)
        if buy.any():
            fill = (nxt * (10000 + bps) + 9999) // 10000
            units = np.maximum(0, cash - fee) // fill
            do = buy & (units > 0)
            cash = np.where(do, cash - units * fill - fee, cash)
            shares = np.where(do, shares + units, shares)
        if sell.any():
            fill = nxt * (10000 - bps) // 10000
            cash = np.where(sell, cash + shares * fill - fee, cash)
            shares = np.where(sell, 0, shares)
        if (cash < 0).any():
            raise EngineError("order cannot cover fees; borrowing is not supported")
    held = shares > 0
    if held.any():
        last = P[:, -1] * (10000 - bps) // 10000
        cash = np.where(held, cash + shares * last - fee, cash)
    return cash


def buy_and_hold_batch(prices: np.ndarray, initial_cash: int, fee: int, bps: int) -> np.ndarray:
    P = np.asarray(prices, dtype=np.int64)
    buy = (P[:, 1] * (10000 + bps) + 9999) // 10000
    sell = P[:, -1] * (10000 - bps) // 10000
    units = np.maximum(0, initial_cash - fee) // buy
    return initial_cash + units * (sell - buy) - np.where(units > 0, 2 * fee, 0)
