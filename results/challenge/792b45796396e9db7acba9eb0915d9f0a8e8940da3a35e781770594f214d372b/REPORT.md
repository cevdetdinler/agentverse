# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 56 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `61f1a396aec9c913493e107176a1124eba5459b6ab95a5c395e131bbb136f7a9`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 10
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| e9847c3668b9cffdd175 | £7,114.98 | £57.56 | £7,219.58 | £7,057.42 | 0.47% |
| bdb68a3dee6da27a3b1f | £950.61 | -£127.32 | £1,059.70 | £1,077.93 | 14.83% |
| eda8fdd52208f680448a | £1,297.07 | -£53.76 | £1,408.85 | £1,350.83 | 6.59% |
| a74191a855dd72f89414 | £1,580.06 | -£39.57 | £1,481.03 | £1,619.63 | 7.16% |
| 6f9309ed592128350de1 | £4,422.93 | £50.36 | £4,399.01 | £4,372.57 | 4.53% |
| c1325c1ce3ee93b9cca1 | £5,156.38 | -£511.73 | £5,216.77 | £5,668.11 | 14.41% |
| 525e9b19399abe257eec | £6,921.25 | -£411.84 | £6,525.77 | £7,333.09 | 11.65% |
| a1de44b65b233c38e861 | £1,119.84 | £0.00 | £1,220.60 | £1,119.84 | 0.00% |
| 45992e407ac4272f81d5 | £4,913.88 | £101.54 | £8,057.84 | £4,812.34 | 7.03% |
| 212e36191aeffee3e212 | £4,447.08 | £72.89 | £4,627.11 | £4,374.19 | 2.14% |
| 6bc2f93f449a1176bfdc | £2,617.30 | -£229.04 | £2,583.58 | £2,846.34 | 10.17% |
| 2765fb5af13b2a0217cc | £4,804.58 | £412.10 | £4,451.56 | £4,392.48 | 1.10% |
| 0136462f33b2851f4765 | £8,552.77 | £50.62 | £8,246.70 | £8,502.15 | 2.10% |
| b1f3bcf500ce901de2a0 | £1,779.24 | -£3.60 | £1,657.64 | £1,782.84 | 3.31% |
| 6c175ada2711f151a7bc | £3,625.47 | £149.94 | £4,054.46 | £3,475.53 | 0.82% |
| bbb10c24e29d5564d7e5 | £1,708.89 | -£30.14 | £1,655.65 | £1,739.03 | 2.07% |
| 9ec4319cb7a220264b98 | £1,457.14 | £13.44 | £1,498.58 | £1,443.70 | 1.40% |
| d95cec5d292b4683439b | £2,347.75 | -£511.96 | £2,237.99 | £2,859.71 | 19.80% |
| c5afcff1fc8dc818e2c8 | £6,453.74 | -£35.12 | £4,921.98 | £6,488.86 | 14.16% |
| 537d65ce57f3fec3ff83 | £9,318.59 | -£294.46 | £10,067.39 | £9,613.05 | 6.55% |
| ece2995e8c37a2937afc | £7,844.16 | -£926.28 | £8,293.52 | £8,770.44 | 11.99% |
| 13161843947dac2e98d3 | £2,170.52 | £15.78 | £2,105.92 | £2,154.74 | 1.18% |
| bcddb2ae71ff196cda99 | £5,171.68 | -£468.33 | £5,146.85 | £5,640.01 | 15.70% |
| 213aec3b5d06fc9a94c0 | £8,201.56 | -£121.00 | £9,919.36 | £8,322.56 | 1.83% |
| 18e1e2afe332aa571cbe | £4,160.09 | £313.62 | £7,714.00 | £3,846.47 | 4.27% |
| 15212e9ae8b94ac595cb | £3,976.17 | -£245.50 | £3,873.70 | £4,221.67 | 8.31% |
| 3ace90149290e437089f | £3,328.66 | £202.82 | £2,268.78 | £3,125.84 | 23.53% |
| 8f36f23f42a085544ad0 | £1,223.52 | £55.47 | £1,354.55 | £1,168.05 | 0.29% |
| 5bbb3b6c1fa2e26bfb9d | £6,253.58 | £47.68 | £6,105.38 | £6,205.90 | 2.06% |
| 1a2aff1c390a2a6b3ec7 | £8,904.64 | £190.10 | £11,307.86 | £8,714.54 | 3.58% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 28 wins, 32 losses, 0 ties vs buy-and-hold; beat cash on 27. Median excess -1.63% of capital; mean max drawdown 6.00%; sign-test p = 0.699.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
