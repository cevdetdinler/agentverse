"""Our own synthetic generator (independent of the kit's): random walks with optional planted effects,
plus a random rule-card generator. Used by the known-answer test bank (E2) and property tests.

Synthetic results are SELF-ASSESSMENT: we wrote both the generator and the checker.
"""
from __future__ import annotations

import math
import random
from typing import Optional

from skeptic.data import PricePath
from skeptic.spec import RuleCard


def random_walk_path(
    rng: random.Random,
    case_id: str,
    n: Optional[int] = None,
    vol: Optional[float] = None,
    effect: Optional[dict] = None,
) -> PricePath:
    """Crypto-like log random walk. Optional planted effect:

    effect = {"kind": "dip"|"momentum", "lookback": L, "threshold": x, "hold": H, "drift": d}
    dip:      after an L-bar return <= -x, add drift +d per bar for the next H bars.
    momentum: after an L-bar return >= +x, add drift +d per bar for the next H bars.
    Then (giveback, default on) drift -d per bar for H more bars, so buy-and-hold gains nothing from
    the effect on average: only a rule that times entry AND exit can capture it. The benchmark is
    buy-and-hold, so this is what "a real edge" means here.
    The trigger only looks at prices already generated (causal).
    """
    n = n or rng.randint(48, 240)
    vol = vol if vol is not None else rng.uniform(0.005, 0.01)
    logp = [math.log(10000.0)]
    boost_left = 0
    give_left = 0
    giveback = bool(effect.get("giveback", True)) if effect else False
    for t in range(1, n):
        drift = 0.0
        if effect and boost_left > 0:
            drift = effect["drift"]
            boost_left -= 1
            if boost_left == 0 and giveback:
                give_left = effect["hold"]
        elif effect and give_left > 0:
            drift = -effect["drift"]
            give_left -= 1
        logp.append(logp[-1] + rng.gauss(0.0, vol) + drift)
        if effect and boost_left == 0 and give_left == 0:
            L = effect["lookback"]
            if t >= L:
                r = math.exp(logp[t] - logp[t - L]) - 1
                if (effect["kind"] == "dip" and r <= -effect["threshold"]) or (
                    effect["kind"] == "momentum" and r >= effect["threshold"]
                ):
                    boost_left = effect["hold"]
    prices = tuple(max(1, int(round(math.exp(v)))) for v in logp)
    return PricePath(
        case_id=case_id,
        prices=prices,
        initial_cash=rng.randint(100000, 1000000),
        fee=rng.randint(0, 200),
        bps=rng.randint(0, 40),
    )


def synthetic_paths(seed: int, count: int, effect: Optional[dict] = None, prefix: str = "syn") -> list[PricePath]:
    rng = random.Random(seed)
    return [random_walk_path(rng, f"{prefix}-{seed}-{i}", effect=effect) for i in range(count)]


def _random_condition(rng: random.Random) -> dict:
    feat = rng.choice(
        ["return", "price_vs_sma", "sma_ratio", "rsi", "drawdown_from_high",
         "rise_from_low", "breakout", "volatility", "down_streak"]
    )
    ineq = rng.choice(["<", "<=", ">", ">="])
    if feat == "return":
        sign = rng.choice([-1, 1])
        return {"feature": feat, "lookback": rng.randint(1, 48), "op": "<=" if sign < 0 else ">=",
                "value": round(sign * rng.uniform(0.005, 0.06), 4)}
    if feat == "price_vs_sma":
        return {"feature": feat, "window": rng.randint(5, 60), "op": rng.choice([ineq, "crosses_above", "crosses_below"]),
                "value": round(rng.uniform(-0.04, 0.04), 4)}
    if feat == "sma_ratio":
        f = rng.randint(3, 20)
        return {"feature": feat, "fast": f, "slow": rng.randint(f + 5, 80),
                "op": rng.choice([ineq, "crosses_above", "crosses_below"]), "value": round(rng.uniform(-0.01, 0.01), 4)}
    if feat == "rsi":
        low = rng.random() < 0.5
        return {"feature": feat, "window": rng.randint(5, 30), "op": "<" if low else ">",
                "value": round(rng.uniform(20, 40) if low else rng.uniform(60, 80), 1)}
    if feat == "drawdown_from_high":
        return {"feature": feat, "lookback": rng.randint(5, 72), "op": "<=", "value": round(-rng.uniform(0.01, 0.08), 4)}
    if feat == "rise_from_low":
        return {"feature": feat, "lookback": rng.randint(5, 72), "op": ">=", "value": round(rng.uniform(0.01, 0.08), 4)}
    if feat == "breakout":
        return {"feature": feat, "lookback": rng.randint(5, 72), "op": ">", "value": round(rng.uniform(-0.005, 0.01), 4)}
    if feat == "volatility":
        return {"feature": feat, "lookback": rng.randint(5, 48), "op": ineq, "value": round(rng.uniform(0.003, 0.012), 5)}
    return {"feature": "down_streak", "op": ">=", "value": rng.randint(2, 6)}


def random_spec(rng: random.Random, name: str = "random") -> RuleCard:
    entry = [_random_condition(rng) for _ in range(rng.choice([1, 1, 2]))]
    exit_ = {"hold_bars": rng.randint(3, 72), "take_profit": None, "stop_loss": None, "any": []}
    if rng.random() < 0.3:
        exit_["take_profit"] = round(rng.uniform(0.01, 0.08), 4)
    if rng.random() < 0.3:
        exit_["stop_loss"] = round(rng.uniform(0.01, 0.06), 4)
    if rng.random() < 0.2:
        exit_["any"] = [_random_condition(rng)]
    return RuleCard.model_validate(
        {"name": name, "entry": {"all": entry}, "exit": exit_, "cooldown_bars": rng.choice([0, 0, 2, 6])}
    )
