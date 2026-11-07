import math
import random

import numpy as np
import pytest
from pydantic import ValidationError

from eval.synthetic import random_spec, random_walk_path
from skeptic.features import feature_series, condition_series
from skeptic.spec import RuleCard, compute_positions, compute_positions_batch, positions_to_action


def card(entry, exit_=None, cooldown=0):
    return RuleCard.model_validate(
        {"entry": {"all": entry}, "exit": exit_ or {"hold_bars": 2}, "cooldown_bars": cooldown}
    )


# ---------------------------------------------------------------- features
def test_return_feature():
    f = feature_series("return", {"lookback": 2}, [100, 110, 90, 99])
    assert math.isnan(f[0]) and math.isnan(f[1])
    assert f[2] == pytest.approx(-0.10)
    assert f[3] == pytest.approx(-0.10)


def test_breakout_excludes_current_bar():
    f = feature_series("breakout", {"lookback": 2}, [100, 105, 110, 104])
    assert f[2] == pytest.approx(110 / 105 - 1)
    assert f[3] == pytest.approx(104 / 110 - 1)


def test_drawdown_and_rise_include_current_bar():
    p = [100, 120, 90, 95]
    dd = feature_series("drawdown_from_high", {"lookback": 2}, p)
    rl = feature_series("rise_from_low", {"lookback": 2}, p)
    assert dd[2] == pytest.approx(90 / 120 - 1)
    assert rl[3] == pytest.approx(95 / 90 - 1)
    assert dd[1] != dd[1]  # NaN: needs L+1 bars


def test_sma_features():
    p = [10, 20, 30, 40]
    assert feature_series("price_vs_sma", {"window": 2}, p)[3] == pytest.approx(40 / 35 - 1)
    assert feature_series("sma_ratio", {"fast": 1, "slow": 3}, p)[3] == pytest.approx(40 / 30 - 1)


def test_rsi_simple_average():
    # changes over last 4: +2, -1, +2, -1 -> avg gain 1, avg loss 0.5 -> RS 2 -> RSI 66.67
    p = [10, 12, 11, 13, 12]
    assert feature_series("rsi", {"window": 4}, p)[4] == pytest.approx(100 - 100 / 3)
    assert feature_series("rsi", {"window": 2}, [1, 2, 3])[2] == 100.0  # no losses
    assert feature_series("rsi", {"window": 2}, [5, 5, 5])[2] == 50.0  # flat


def test_volatility_and_down_streak():
    p = [100, 101, 100, 101]
    v = feature_series("volatility", {"lookback": 3}, p)
    r = np.diff(np.log(p))
    assert v[3] == pytest.approx(np.std(r))
    assert list(feature_series("down_streak", {}, [5, 4, 3, 4, 3])) == [0, 1, 2, 0, 1]


def test_crosses():
    p = [100, 100, 100, 103, 104, 100]
    up = condition_series("return", {"lookback": 1}, "crosses_above", 0.02, p)
    assert up == [False, False, False, True, False, False]
    dn = condition_series("return", {"lookback": 1}, "crosses_below", 0.0, p)
    assert dn == [False, False, False, False, False, True]


# ---------------------------------------------------------------- rule card
def test_validation_rejects_bad_cards():
    with pytest.raises(ValidationError):
        card([{"feature": "return", "op": "<", "value": -0.05}])  # missing lookback
    with pytest.raises(ValidationError):
        card([{"feature": "return", "lookback": 500, "op": "<", "value": -0.05}])  # > 200
    with pytest.raises(ValidationError):
        card([{"feature": "sma_ratio", "fast": 50, "slow": 10, "op": ">", "value": 0}])
    with pytest.raises(ValidationError):
        RuleCard.model_validate({"entry": {"all": [{"feature": "down_streak", "op": ">=", "value": 3}]},
                                 "exit": {}})  # no exit rule
    with pytest.raises(ValidationError):
        card([{"feature": "down_streak", "op": ">=", "value": 3}] * 6)  # > 5 conditions
    with pytest.raises(ValidationError):
        card([{"feature": "down_streak", "op": ">=", "value": 3, "lookback": 5}])  # extra param


def test_fingerprint_ignores_names_and_text():
    a = card([{"feature": "return", "lookback": 24, "op": "<=", "value": -0.05}], {"hold_bars": 72})
    b = a.model_copy(update={"name": "other", "hunch_text": "different words", "assumptions": ["x"]})
    c = card([{"feature": "return", "lookback": 24, "op": "<=", "value": -0.06}], {"hold_bars": 72})
    assert a.fingerprint == b.fingerprint
    assert a.fingerprint != c.fingerprint
    assert len(a.fingerprint) == 64


def test_positions_hold_exit_and_signal_timing():
    # 1-bar drop of >=5% at bar 2 -> in from bar 2, entry fill bar 3, exits when i - 3 >= 2 (bar 5)
    p = [100, 100, 90, 91, 92, 93, 94, 95]
    spec = card([{"feature": "return", "lookback": 1, "op": "<=", "value": -0.05}], {"hold_bars": 2})
    assert compute_positions(spec, p) == [False, False, True, True, True, False, False, False]


def test_take_profit_and_stop_loss_use_entry_fill_price():
    p = [100, 90, 100, 110, 120, 130]
    spec = card([{"feature": "return", "lookback": 1, "op": "<=", "value": -0.05}],
                {"take_profit": 0.15})
    # signal at bar 1, entry_ref = p[2] = 100; bar 4: 120/100-1 = 0.2 >= 0.15 -> out
    assert compute_positions(spec, p) == [False, True, True, True, False, False]
    spec_sl = card([{"feature": "return", "lookback": 1, "op": "<=", "value": -0.05}], {"stop_loss": 0.05})
    q = [100, 90, 100, 96, 94, 99]
    assert compute_positions(spec_sl, q) == [False, True, True, True, False, False]


def test_cooldown_blocks_reentry():
    p = [100, 94, 94, 88, 83, 78, 73, 69]  # keeps dropping: entry signal every bar
    base = card([{"feature": "return", "lookback": 1, "op": "<=", "value": -0.05}], {"hold_bars": 1})
    cool = card([{"feature": "return", "lookback": 1, "op": "<=", "value": -0.05}], {"hold_bars": 1}, cooldown=2)
    # base: in at 1 (fill 2), out at 3, re-enter at 4 (fill 5), out at 6, re-enter at 7
    assert compute_positions(base, p) == [False, True, True, False, True, True, False, True]
    # cooldown 2: after the exit at 3, entries need i - 3 > 2, so the next entry is bar 6
    assert compute_positions(cool, p) == [False, True, True, False, False, False, True, True]


def test_positions_to_action():
    assert positions_to_action(True, 0) == "buy"
    assert positions_to_action(True, 5) == "hold"
    assert positions_to_action(False, 5) == "sell"
    assert positions_to_action(False, 0) == "hold"


def test_no_look_ahead_property():
    """Leak guarantee: the decision at bar k is identical whether or not the future exists."""
    rng = random.Random(2026)
    checked = 0
    for trial in range(150):
        spec = random_spec(rng)
        path = random_walk_path(rng, f"p{trial}", n=rng.randint(30, 120))
        prices = list(path.prices)
        full = compute_positions(spec, prices)
        for k in range(len(prices)):
            assert compute_positions(spec, prices[: k + 1])[k] == full[k], (spec.rules_dict(), k)
            checked += 1
    assert checked > 5000


def test_look_ahead_detector_would_catch_a_cheat():
    """Counterexample: a rule that peeks one bar ahead must fail the same check."""
    def cheating_positions(prices):
        return [i + 1 < len(prices) and prices[i + 1] > prices[i] for i in range(len(prices))]

    prices = [100, 101, 99, 102, 98, 103]
    full = cheating_positions(prices)
    mismatches = sum(cheating_positions(prices[: k + 1])[k] != full[k] for k in range(len(prices)))
    assert mismatches > 0


def test_batch_positions_equal_scalar():
    rng = random.Random(31)
    for trial in range(120):
        spec = random_spec(rng)
        paths = [random_walk_path(rng, f"b{trial}-{j}", n=90) for j in range(6)]
        P = np.array([p.prices for p in paths])
        batch = compute_positions_batch(spec, P)
        for j, p in enumerate(paths):
            assert batch[j].tolist() == compute_positions(spec, p.prices), (spec.rules_dict(), j)
