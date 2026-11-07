# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 6 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 6 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **6**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `18b721a58f13a9ba4a1f43eede64594d9aca0f6b2f0082db71af6d3a0c2fccfc`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `a058173e301226407ab29edd76b062e782704e2d`, uncommitted changes: 1
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 6 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| af081c73886f60ecbddc | £7,556.61 | -£316.29 | £7,662.76 | £7,872.90 | 7.03% |
| f33eb1ce70ed6e39505c | £6,650.63 | -£585.20 | £7,394.96 | £7,235.83 | 12.04% |
| 0d883a8aefa69913823f | £8,983.59 | -£153.18 | £9,445.99 | £9,136.77 | 1.67% |
| 302ae2ea4fc5ecee6d86 | £4,568.08 | £0.00 | £4,722.42 | £4,568.08 | 0.00% |
| bd56e6a7adbdab0722e1 | £5,883.74 | -£58.11 | £5,273.23 | £5,941.85 | 6.26% |
| 67e1c24d05d41a4bca15 | £1,927.62 | -£9.02 | £1,933.78 | £1,936.64 | 2.31% |

Showing 6 of 6 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 6 paths:** 1 wins, 5 losses, 0 ties vs buy-and-hold; beat cash on 0. Median excess -2.37% of capital; mean max drawdown 4.88%; sign-test p = 0.219.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
