"""The rule card: a small, closed strategy DSL the kit's runner can execute.

Long-only, all-in/all-out, bar-based. The LLM may *propose* a card; only a human approves it,
and only this module (plus features.py) turns it into positions.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import config
from .features import condition_series

FeatureName = Literal[
    "return",
    "price_vs_sma",
    "sma_ratio",
    "rsi",
    "drawdown_from_high",
    "rise_from_low",
    "breakout",
    "volatility",
    "down_streak",
]
Op = Literal["<", "<=", ">", ">=", "crosses_above", "crosses_below"]

# Which integer parameters each feature takes.
FEATURE_PARAMS: dict[str, tuple[str, ...]] = {
    "return": ("lookback",),
    "price_vs_sma": ("window",),
    "sma_ratio": ("fast", "slow"),
    "rsi": ("window",),
    "drawdown_from_high": ("lookback",),
    "rise_from_low": ("lookback",),
    "breakout": ("lookback",),
    "volatility": ("lookback",),
    "down_streak": (),
}
INT_PARAMS = ("lookback", "window", "fast", "slow")


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: FeatureName
    op: Op
    value: float
    lookback: Optional[int] = None
    window: Optional[int] = None
    fast: Optional[int] = None
    slow: Optional[int] = None

    @model_validator(mode="after")
    def _params_match_feature(self) -> "Condition":
        need = FEATURE_PARAMS[self.feature]
        for name in INT_PARAMS:
            val = getattr(self, name)
            if name in need:
                if val is None:
                    raise ValueError(f"feature '{self.feature}' needs '{name}'")
                if not 1 <= val <= config.LIMITS["max_lookback"]:
                    raise ValueError(
                        f"'{name}' must be between 1 and {config.LIMITS['max_lookback']} bars (got {val})"
                    )
            elif val is not None:
                raise ValueError(f"feature '{self.feature}' does not take '{name}'")
        if self.feature == "sma_ratio" and not self.fast < self.slow:
            raise ValueError("sma_ratio needs fast < slow")
        if self.feature == "volatility" and self.lookback < 2:
            raise ValueError("volatility needs lookback >= 2")
        if self.feature == "rsi" and not 0 <= self.value <= 100:
            raise ValueError("rsi value must be between 0 and 100")
        return self

    def params(self) -> dict:
        return {k: getattr(self, k) for k in FEATURE_PARAMS[self.feature]}

    def describe(self) -> str:
        p = ", ".join(f"{k}={v}" for k, v in self.params().items())
        return f"{self.feature}({p}) {self.op} {self.value:g}"


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all: list[Condition] = Field(min_length=1)


class Exit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hold_bars: Optional[int] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    any: list[Condition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one_exit(self) -> "Exit":
        if self.hold_bars is None and self.take_profit is None and self.stop_loss is None and not self.any:
            raise ValueError("a rule card needs at least one exit rule")
        if self.hold_bars is not None and not 1 <= self.hold_bars <= config.LIMITS["max_hold_bars"]:
            raise ValueError(f"hold_bars must be between 1 and {config.LIMITS['max_hold_bars']}")
        if self.take_profit is not None and not 0 < self.take_profit <= 10:
            raise ValueError("take_profit is a positive fraction, e.g. 0.05 for +5%")
        if self.stop_loss is not None and not 0 < self.stop_loss < 1:
            raise ValueError("stop_loss is a positive fraction below 1, e.g. 0.03 for -3%")
        return self


class RuleCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    name: str = Field(default="Untitled idea", max_length=200)
    hunch_text: str = Field(default="", max_length=config.LIMITS["hunch_chars"])
    entry: Entry
    exit: Exit
    cooldown_bars: int = Field(default=0, ge=0, le=config.LIMITS["max_lookback"])
    assumptions: list[str] = Field(default_factory=list)
    parent_fingerprint: Optional[str] = None
    idea_id: Optional[str] = None

    @model_validator(mode="after")
    def _limits(self) -> "RuleCard":
        n = len(self.entry.all) + len(self.exit.any)
        if n > config.LIMITS["max_conditions"]:
            raise ValueError(f"at most {config.LIMITS['max_conditions']} rule conditions (got {n})")
        return self

    @field_validator("assumptions")
    @classmethod
    def _short_assumptions(cls, v: list[str]) -> list[str]:
        return [a[:300] for a in v[:12]]

    # -------------------------------------------------------------- identity
    def rules_dict(self) -> dict:
        """The part of the card that determines trading behaviour."""
        return {
            "entry": self.entry.model_dump(mode="json"),
            "exit": self.exit.model_dump(mode="json"),
            "cooldown_bars": self.cooldown_bars,
        }

    @property
    def fingerprint(self) -> str:
        return fingerprint_of(self.rules_dict())

    def conditions(self) -> list[Condition]:
        return list(self.entry.all) + list(self.exit.any)

    def describe(self) -> list[str]:
        lines = ["ENTER when " + " AND ".join(c.describe() for c in self.entry.all)]
        exits = []
        if self.exit.hold_bars is not None:
            exits.append(f"held {self.exit.hold_bars} bars")
        if self.exit.take_profit is not None:
            exits.append(f"up {self.exit.take_profit:.2%} from entry")
        if self.exit.stop_loss is not None:
            exits.append(f"down {self.exit.stop_loss:.2%} from entry")
        exits += [c.describe() for c in self.exit.any]
        lines.append("EXIT when " + " OR ".join(exits))
        if self.cooldown_bars:
            lines.append(f"WAIT {self.cooldown_bars} bars after an exit before re-entering")
        return lines


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint_of(rules: dict) -> str:
    return hashlib.sha256(canonical_json(rules).encode("utf-8")).hexdigest()


def new_idea_id() -> str:
    return "idea_" + secrets.token_hex(4)


# ------------------------------------------------------------------ positions
def _cond_bool(c: Condition, prices) -> list[bool]:
    return condition_series(c.feature, c.params(), c.op, c.value, prices)


def compute_positions(spec: RuleCard, prices) -> list[bool]:
    """Target position for the decision at each bar. One O(n) pass after the feature series.

    Decision at bar i may only use prices[0..i]; the fill happens at i+1 (engine/runner).
    """
    n = len(prices)
    if n == 0:
        return []
    entry_cols = [_cond_bool(c, prices) for c in spec.entry.all]
    exit_cols = [_cond_bool(c, prices) for c in spec.exit.any]
    hold, tp, sl = spec.exit.hold_bars, spec.exit.take_profit, spec.exit.stop_loss
    cooldown = spec.cooldown_bars

    out = [False] * n
    in_pos = False
    entry_bar = -1
    last_exit = None
    for i in range(n):
        if not in_pos:
            if all(col[i] for col in entry_cols) and (last_exit is None or i - last_exit > cooldown):
                in_pos = True
                entry_bar = i + 1  # fill bar; entry_ref = prices[entry_bar], known from bar i+1 on
        else:
            if i >= entry_bar:
                ref = prices[entry_bar]
                move = prices[i] / ref - 1.0
                if (
                    (hold is not None and i - entry_bar >= hold)
                    or (tp is not None and move >= tp)
                    or (sl is not None and move <= -sl)
                    or any(col[i] for col in exit_cols)
                ):
                    in_pos = False
                    last_exit = i
        out[i] = in_pos
    return out


def positions_to_action(want_in: bool, shares: int) -> str:
    """The single conversion rule shared by engine.simulate and adapter.py."""
    if want_in and shares == 0:
        return "buy"
    if not want_in and shares > 0:
        return "sell"
    return "hold"
