# E2 known-answer test bank: SELF-ASSESSMENT

> Our own synthetic generator (`eval/synthetic.py`) and our own checker. This is **not** independent
> evidence. It checks that Skeptic's verdicts behave as designed when the right answer is known.

Generated 2026-11-07 17:31 · 130 cases · permutation K = 1000 · 300 practice + 150 vault paths per synthetic case · seeds in `cases.jsonl`.

**Approve** means Skeptic's final verdict is SURVIVED (it passed every practice check *and* the one-shot vault).
**Naive backtester** means approve if the practice mean excess vs buy-and-hold is > 0, which is what a typical
retail backtest screen implies.

## False approvals (lower is better)

| Group | Truth | Naive backtester | Skeptic |
|---|---|---|---|
| Null, guaranteed (random rules, random walks) | no edge | 9/50 = 18% (95% CI 10–31%) | 0/50 = 0% (95% CI 0–7%) |
| Null, presumed (random rules, real practice data) | presumed none | 2/30 = 7% (95% CI 2–21%) | 0/30 = 0% (95% CI 0–11%) |
| P-hacked, honest trial count (best of 50) | no edge | 4/20 = 20% (95% CI 8–42%) | 0/20 = 0% (95% CI 0–16%) |
| P-hacked, tries hidden (trials = 1) | no edge | same | 0/20 = 0% (95% CI 0–16%) |

With tries hidden, 1/20 = 5% (95% CI 1–24%) of p-hacked rules still passed the practice gate, so they were caught (or not) only by the vault.

## Power on planted effects (higher is better)

Planted timing effect: after a 24-bar move of 4% (down for *dip*, up for *momentum*), the price drifts +d per bar
for 24 bars, then gives it back over the next 24 bars, so buy-and-hold gains nothing from the effect on average.
Test rules use nearby but not identical parameters (lookback 12/24/36, threshold 3–5%, hold 12/24/36).

| drift d per bar | Naive approves | Skeptic approves | Skeptic verdicts |
|---|---|---|---|
| 0.001 | 2/3 = 67% (95% CI 21–94%) | 0/3 = 0% (95% CI 0–56%) | INCONCLUSIVE 2, REJECTED 1 |
| 0.002 | 4/4 = 100% (95% CI 51–100%) | 0/4 = 0% (95% CI 0–49%) | INCONCLUSIVE 2, REJECTED 2 |
| 0.003 | 3/3 = 100% (95% CI 44–100%) | 1/3 = 33% (95% CI 6–79%) | INCONCLUSIVE 1, REJECTED 1, SURVIVED 1 |
| 0.004 | 4/4 = 100% (95% CI 51–100%) | 3/4 = 75% (95% CI 30–95%) | REJECTED 1, SURVIVED 3 |
| 0.006 | 3/3 = 100% (95% CI 44–100%) | 0/3 = 0% (95% CI 0–56%) | INCONCLUSIVE 1, REJECTED 2 |

## Reading this honestly

- On no-edge rules the naive screen approved 9/50 (random walks), 2/30 (real data) and 4/20 (p-hacked); Skeptic approved 0/50, 0/30 and 0/20 (even with the tries hidden).
- Planted rules whose oracle median excess (3,000 fresh paths) was not positive are excluded from the power table (13 excluded): a planted effect does not mean every nearby rule profits from it.
- Skeptic trades power for safety: at weak strengths it says REJECTED or INCONCLUSIVE. With 6 rules per strength the
  confidence intervals are wide; read the trend, not single cells.
- Synthetic random walks are not markets. None of these rates says anything about real-world profitability.

Reproduce: `.venv\Scripts\python.exe eval\testbank.py` (seeds are fixed in `build_cases`).
