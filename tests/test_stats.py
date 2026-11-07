import math

import pytest

from skeptic.stats import aggregate, bootstrap_median_ci, median_int, sign_test_p, wilson_ci


def test_sign_test_exact_values():
    assert sign_test_p(0, 0) is None
    assert sign_test_p(5, 5) == 1.0
    assert sign_test_p(10, 0) == pytest.approx(2 / 1024)
    # 8 wins, 2 losses: 2 * (1 + 10 + 45) / 1024
    assert sign_test_p(8, 2) == pytest.approx(112 / 1024)
    assert sign_test_p(2, 8) == sign_test_p(8, 2)


def test_median_int_kit_definition():
    assert median_int([3, 1, 2]) == 2
    assert median_int([1, 2, 3, 4]) == 2  # (2 + 3) // 2
    assert median_int([-3, -2]) == -3  # floor of -2.5


def test_aggregate():
    rows = [
        {"final_cash": 1100, "bh_final": 1000, "initial_cash": 1000, "max_drawdown_bps": 100, "trades": 2},
        {"final_cash": 900, "bh_final": 1000, "initial_cash": 1000, "max_drawdown_bps": 300, "trades": 1},
        {"final_cash": 1000, "bh_final": 1000, "initial_cash": 1000, "max_drawdown_bps": 0, "trades": 0},
    ]
    a = aggregate(rows)
    assert (a["wins"], a["losses"], a["ties"]) == (1, 1, 1)
    assert a["median_excess_bps"] == 0
    assert a["mean_max_drawdown_bps"] == 133
    assert a["sign_p"] == 1.0
    assert a["total_trades"] == 3


def test_bootstrap_ci_contains_median_and_is_reproducible():
    vals = list(range(-50, 151))
    lo, hi = bootstrap_median_ci(vals, 500, seed=1)
    assert lo <= median_int(vals) <= hi
    assert (lo, hi) == bootstrap_median_ci(vals, 500, seed=1)


def test_wilson():
    lo, hi = wilson_ci(0, 50)
    assert lo == pytest.approx(0.0, abs=1e-12) and 0.05 < hi < 0.09
    lo, hi = wilson_ci(25, 50)
    assert lo < 0.5 < hi
