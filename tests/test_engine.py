import random

import numpy as np
import pytest

from eval.synthetic import random_spec, random_walk_path
from skeptic.engine import (
    EngineError,
    buy_and_hold_final,
    excess_bps,
    max_drawdown_bps,
    simulate,
    simulate_batch,
    simulate_batch_paths,
    buy_and_hold_batch,
)
from skeptic.spec import compute_positions


def test_hand_computed_round_trip():
    # buy fills at 110*1.01 rounded up = 112; 8 units; sell fills at floor(121*0.99) = 119
    r = simulate([100, 110, 121, 100], [True, False, False], 1000, 5, 100, keep_equity=True)
    assert r.final_cash == 1046
    assert r.equity == [1000, 979, 1046, 1046, 1046]
    assert r.max_drawdown_bps == 210
    assert r.trades == 1 and r.fees_paid == 10
    assert r.bars_in_position == 1 and r.decisions == 3


def test_hand_computed_buy_and_hold_and_excess():
    bh = buy_and_hold_final([100, 110, 121, 100], 1000, 5, 100)
    assert bh == 886  # 8 units * (99 - 112) - 2 fees
    assert excess_bps(1046, bh, 1000) == 1600


def test_forced_final_liquidation():
    r = simulate([100, 110, 121, 100], [True, True, True], 1000, 5, 100)
    assert r.final_cash == 886  # sold at floor(100*0.99) = 99 at the end


def test_never_in_position_keeps_cash():
    r = simulate([100, 50, 200], [False, False], 777, 3, 10)
    assert r.final_cash == 777 and r.trades == 0 and r.max_drawdown_bps == 0


def test_cannot_afford_one_share_does_nothing():
    # counterexample: fee eats all cash -> zero units, no fee charged
    r = simulate([100, 100, 100], [True, True], 104, 5, 0)
    assert r.final_cash == 104 and r.trades == 0


def test_negative_cash_is_an_error():
    # 1 unit at 100 leaves cash 0; selling at 1 with a fee of 10 would need borrowing
    with pytest.raises(EngineError):
        simulate([100, 100, 1, 1], [True, False, False], 110, 10, 0)
    # counterexample: the same trade with fee 1 is fine (cash ends at exactly 0)
    assert simulate([100, 100, 1, 1], [True, False, False], 101, 1, 0).final_cash == 0


def test_all_in_positions_equal_buy_and_hold_property():
    rng = random.Random(7)
    for i in range(200):
        p = random_walk_path(rng, f"t{i}")
        r = simulate(p.prices, [True] * (len(p.prices) - 1), p.initial_cash, p.fee, p.bps)
        assert r.final_cash == buy_and_hold_final(p.prices, p.initial_cash, p.fee, p.bps)


def test_batch_equals_scalar():
    rng = random.Random(11)
    nrng = np.random.default_rng(11)
    for i in range(40):
        p = random_walk_path(rng, f"t{i}")
        n = len(p.prices)
        pos = nrng.random((16, n)) < 0.5
        batch = simulate_batch(p.prices, pos, p.initial_cash, p.fee, p.bps)
        for k in range(16):
            assert batch[k] == simulate(p.prices, pos[k].tolist(), p.initial_cash, p.fee, p.bps).final_cash


def test_batch_equals_scalar_on_strategy_positions():
    rng = random.Random(5)
    for i in range(60):
        spec = random_spec(rng)
        p = random_walk_path(rng, f"s{i}")
        pos = compute_positions(spec, p.prices)
        a = simulate(p.prices, pos, p.initial_cash, p.fee, p.bps).final_cash
        b = simulate_batch(p.prices, np.array([pos]), p.initial_cash, p.fee, p.bps)[0]
        assert a == b


def test_max_drawdown_integer():
    assert max_drawdown_bps([100, 120, 90, 130]) == 2500
    assert max_drawdown_bps([100, 101, 102]) == 0


def test_batch_paths_equals_scalar():
    rng = random.Random(3)
    nrng = np.random.default_rng(3)
    for i in range(30):
        paths = [random_walk_path(rng, f"q{i}-{j}", n=70) for j in range(8)]
        P = np.array([p.prices for p in paths])
        pos = nrng.random(P.shape) < 0.4
        cash, fee, bps = 500000, 75, 12
        finals = simulate_batch_paths(P, pos, cash, fee, bps)
        bhs = buy_and_hold_batch(P, cash, fee, bps)
        for j, p in enumerate(paths):
            assert finals[j] == simulate(p.prices, pos[j].tolist(), cash, fee, bps).final_cash
            assert bhs[j] == buy_and_hold_final(p.prices, cash, fee, bps)
