import random

import numpy as np
import pytest

from eval.synthetic import synthetic_paths
from skeptic import attacks
from skeptic.attacks import (
    _segments,
    a2_permutation,
    a6_trials,
    evaluate,
    random_entry_positions,
    run_battery,
    run_diagnostic,
)
from skeptic.spec import RuleCard

DIP = RuleCard.model_validate({
    "name": "dip", "entry": {"all": [{"feature": "return", "lookback": 12, "op": "<=", "value": -0.03}]},
    "exit": {"hold_bars": 12},
})


def test_random_entry_positions_preserve_lengths_and_bounds():
    rng = np.random.default_rng(0)
    lengths = [5, 1, 9, 3]
    n = 40
    pos = random_entry_positions(lengths, n, 500, rng)
    assert pos.shape == (500, n)
    for row in pos:
        assert not row[n - 1]  # never a target on the last bar (no next-bar fill)
        assert sorted(_segments(row.tolist(), n - 1)) == sorted(lengths)


def test_random_entry_positions_tight_fit():
    rng = np.random.default_rng(1)
    pos = random_entry_positions([3, 3], 8, 50, rng)  # 7 decision bars, 3+1+3 = exactly full
    assert all(row.tolist() == [True, True, True, False, True, True, True, False] for row in pos)


def test_permutation_p_is_not_small_on_null_data():
    paths = synthetic_paths(seed=3, count=80)
    ev = evaluate(DIP, paths)
    res = a2_permutation(DIP, paths, ev, k=200, seed=5)
    assert 0.0 < res.numbers["p_perm"] <= 1.0
    assert res.numbers["p_perm"] > 0.01  # no planted effect: should not look like a strong signal


def test_permutation_detects_planted_effect():
    effect = {"kind": "dip", "lookback": 12, "threshold": 0.03, "hold": 12, "drift": 0.004}
    paths = synthetic_paths(seed=4, count=120, effect=effect)
    ev = evaluate(DIP, paths)
    res = a2_permutation(DIP, paths, ev, k=200, seed=5)
    assert res.numbers["p_perm"] < 0.05


def test_a6_bonferroni():
    class Fake:
        numbers = {"p_perm": 0.012}
    assert a6_trials(DIP, Fake, 1).numbers["p_adj"] == pytest.approx(0.012)
    r = a6_trials(DIP, Fake, 5)
    assert r.numbers["p_adj"] == pytest.approx(0.06) and not r.passed
    assert a6_trials(DIP, Fake, 1000).numbers["p_adj"] == 1.0


def test_gate_rejects_null_and_passes_strong_planted_effect():
    null = run_battery(DIP, synthetic_paths(seed=10, count=120), trials=1, k=100)
    assert null["gate"]["status"] in ("REJECTED", "INCONCLUSIVE")
    assert null["gate"]["failing"]
    effect = {"kind": "dip", "lookback": 12, "threshold": 0.03, "hold": 12, "drift": 0.006}
    planted = run_battery(DIP, synthetic_paths(seed=11, count=150, effect=effect), trials=1, k=100)
    assert planted["gate"]["status"] == "ELIGIBLE", planted["gate"]["failing"]


def test_too_few_trades_is_inconclusive():
    rare = RuleCard.model_validate({
        "entry": {"all": [{"feature": "return", "lookback": 1, "op": "<=", "value": -0.5}]}, "exit": {"hold_bars": 5}})
    out = run_battery(rare, synthetic_paths(seed=12, count=30), trials=1, k=20)
    assert out["gate"]["status"] == "INCONCLUSIVE"


def test_wobble_never_changes_the_spec_and_reports_rank():
    paths = synthetic_paths(seed=13, count=40)
    before = DIP.fingerprint
    res = attacks.a3_wobble(DIP, paths, evaluate(DIP, paths))
    assert DIP.fingerprint == before
    assert res.numbers["neighbours"] >= 6
    assert 1 <= res.numbers["user_spec_rank"] <= res.numbers["rank_out_of"]
    assert res.chart["joint"] is not None


def test_cost_stress_monotone():
    paths = synthetic_paths(seed=14, count=60)
    ev = evaluate(DIP, paths)
    res = attacks.a4_cost_stress(DIP, paths, ev)
    t = res.numbers["table"]
    assert [r["multiplier"] for r in t] == [1, 2, 3]


def test_outlier_drop_counts():
    paths = synthetic_paths(seed=15, count=40)
    res = attacks.a5_outliers(DIP, paths, evaluate(DIP, paths))
    assert res.numbers["dropped_paths"] == 2  # ceil(5% of 40)


@pytest.mark.parametrize("tool,params", [
    ("regime_split", {"by": "path_trend", "buckets": 3}),
    ("regime_split", {"by": "path_volatility"}),
    ("subsample_folds", {"k": 5}),
    ("exposure_check", {}),
    ("holding_sweep", {"values": [6, 24, 48]}),
    ("cost_stress", {"multiplier": 4}),
    ("outlier_drop", {"pct": 10}),
])
def test_diagnostics_run(tool, params):
    paths = synthetic_paths(seed=16, count=45)
    res = run_diagnostic(tool, params, DIP, paths, evaluate(DIP, paths), "D1")
    assert res.id == "D1" and res.kind == "diagnostic" and isinstance(res.passed, bool)


@pytest.mark.parametrize("tool,params", [
    ("regime_split", {"by": "moon_phase"}),
    ("subsample_folds", {"k": 500}),
    ("cost_stress", {"multiplier": 100}),
    ("holding_sweep", {"values": [0, 9999]}),
    ("delete_ledger", {}),
])
def test_diagnostics_reject_bad_params(tool, params):
    paths = synthetic_paths(seed=17, count=10)
    with pytest.raises(ValueError):
        run_diagnostic(tool, params, DIP, paths, evaluate(DIP, paths), "D1")


def test_battery_is_deterministic():
    paths = synthetic_paths(seed=18, count=40)
    a = run_battery(DIP, paths, trials=2, k=50)
    b = run_battery(DIP, paths, trials=2, k=50)
    assert [r.numbers for r in a["results"]] == [r.numbers for r in b["results"]]


def test_cost_stress_never_rewards_higher_costs():
    """Counterexample from a live run: a rarely-trading rule must not 'improve' when costs rise."""
    paths = synthetic_paths(seed=21, count=80)
    ev = evaluate(DIP, paths)
    t = attacks.a4_cost_stress(DIP, paths, ev).numbers["table"]
    per_path = [evaluate(DIP, paths, fee_mult=m, bps_mult=m, positions=ev.positions, stress_benchmark=False).excess
                for m in (1, 2, 3)]
    # Integer share rounding means a costlier entry can buy one share fewer and so lose slightly less on a
    # losing trade; that is real, so require it of almost every path, not all of them.
    worse = sum(a >= b >= c for a, b, c in zip(*per_path))
    assert worse >= 0.95 * len(paths)
    assert t[0]["median_excess_bps"] >= t[1]["median_excess_bps"] >= t[2]["median_excess_bps"]
