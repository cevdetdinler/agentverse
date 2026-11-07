# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 57 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `552e057c5001a14048e8e3a59bfa612c7fc637ec377ef94b323963a931680b9f`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 19
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8414b732e2a762f9f5aa | £3,565.43 | £48.67 | £3,180.00 | £3,516.76 | 0.93% |
| 75e56e229f5bd1762333 | £3,040.07 | -£246.08 | £2,736.39 | £3,286.15 | 7.48% |
| d8d61de4e324e222be29 | £2,467.42 | £0.00 | £2,416.53 | £2,467.42 | 0.00% |
| 8a40e46298850eabb8d2 | £3,770.60 | £67.52 | £3,773.08 | £3,703.08 | 4.63% |
| d43202c92f2f92758fd6 | £2,734.75 | £13.77 | £3,160.39 | £2,720.98 | 2.74% |
| 4ab7fb30e02b9dc4c7c2 | £9,553.50 | £320.20 | £10,205.02 | £9,233.30 | 3.10% |
| 3b61cb2335398c5f5f40 | £2,753.72 | £96.08 | £2,629.28 | £2,657.64 | 0.12% |
| ebb63901434bfff43b19 | £3,698.59 | -£757.21 | £2,897.64 | £4,455.80 | 23.97% |
| 43ee8fbc2b2014e10cb6 | £6,244.79 | -£576.92 | £6,345.55 | £6,821.71 | 11.76% |
| 55986f922cce07e0a11f | £2,141.95 | -£36.56 | £2,222.45 | £2,178.51 | 1.67% |
| f77aa69bf2222aa81312 | £3,394.94 | -£269.91 | £3,137.61 | £3,664.85 | 7.36% |
| 018a77edc3eba2330569 | £2,397.05 | -£55.65 | £2,293.94 | £2,452.70 | 4.51% |
| 47e02ba95e702aed79cf | £2,872.86 | -£30.11 | £3,252.89 | £2,902.97 | 1.99% |
| 0b3366fe251944872de7 | £6,512.72 | -£163.41 | £6,662.31 | £6,676.13 | 4.17% |
| 905023be62bcd756bdcb | £9,084.37 | -£476.16 | £8,876.32 | £9,560.53 | 5.04% |
| 539a069162420e99501d | £1,193.89 | £44.06 | £1,322.11 | £1,149.83 | 2.13% |
| bf72d0a0434cd1e84047 | £7,725.93 | -£271.14 | £8,300.33 | £7,997.07 | 3.39% |
| bd633c9a6e41ca279c21 | £9,131.74 | -£748.25 | £7,360.15 | £9,879.99 | 14.59% |
| 522ae8f965b14c94f1d1 | £1,268.28 | £0.00 | £1,291.04 | £1,268.28 | 0.00% |
| 946ca105454a4c23545c | £6,866.11 | -£203.37 | £6,629.72 | £7,069.48 | 2.88% |
| c42286618f98cc45c1dc | £6,856.64 | £432.02 | £8,647.52 | £6,424.62 | 1.52% |
| a9bf40af321e5cea531d | £4,728.64 | -£182.70 | £4,907.23 | £4,911.34 | 4.67% |
| c95bfc49afbdbd5d14ff | £7,276.09 | -£51.19 | £7,287.82 | £7,327.28 | 0.69% |
| 490abc4bc043a3c86898 | £1,752.01 | £71.30 | £1,097.23 | £1,680.71 | 26.23% |
| 0a458195431796ce93fb | £6,599.81 | -£441.04 | £6,521.23 | £7,040.85 | 10.58% |
| 75fc143778a6d038280a | £7,541.07 | -£225.23 | £9,002.90 | £7,766.30 | 3.07% |
| 308d13e6af41830dbf2d | £5,055.72 | -£24.68 | £5,117.42 | £5,080.40 | 1.39% |
| 2cdef20ef742dfcbb229 | £6,207.46 | £0.00 | £6,543.48 | £6,207.46 | 0.00% |
| 4d7275a5e1ff63c9c949 | £6,011.93 | -£368.44 | £5,073.58 | £6,380.37 | 11.18% |
| 86ce38adf496176b0282 | £2,560.76 | -£220.95 | £1,933.87 | £2,781.71 | 14.14% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 30 wins, 30 losses, 0 ties vs buy-and-hold; beat cash on 19. Median excess 0.30% of capital; mean max drawdown 5.29%; sign-test p = 1.000.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
