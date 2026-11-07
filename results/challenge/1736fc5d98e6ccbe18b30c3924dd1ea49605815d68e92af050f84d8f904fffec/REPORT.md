# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 57 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `b2bd32789a96dcf13485697cc5f5588fe28d6cc923a433f6ecd6c3e45fe983e6`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 0
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 923d2f926aa6651592c6 | £2,056.30 | £0.00 | £1,960.36 | £2,056.30 | 0.00% |
| 14ba017f69caf1950e45 | £8,987.79 | £0.00 | £5,717.49 | £8,987.79 | 0.00% |
| fa5b4ab67b1dffe0914c | £4,758.48 | £0.00 | £5,159.46 | £4,758.48 | 0.00% |
| 5d02080ade1d94acff89 | £6,520.55 | £345.27 | £7,378.60 | £6,175.28 | 5.23% |
| f719b39ac6de06f96d7a | £8,409.65 | -£71.09 | £11,476.08 | £8,480.74 | 24.92% |
| d1798afe4f6e6f1ab823 | £5,857.41 | £0.00 | £6,120.97 | £5,857.41 | 0.00% |
| d68da269b3e13e25d9f1 | £5,304.63 | -£303.34 | £5,282.51 | £5,607.97 | 7.56% |
| 891394c71e74c243da3e | £9,172.04 | £0.00 | £9,312.14 | £9,172.04 | 0.00% |
| a138a5a3282efacb0299 | £4,713.40 | £0.00 | £4,484.78 | £4,713.40 | 0.00% |
| 683eeb15283f938e9da9 | £3,079.17 | £0.00 | £3,280.15 | £3,079.17 | 0.00% |
| ea3b59b806dca42f325a | £6,599.61 | £0.00 | £6,320.13 | £6,599.61 | 0.00% |
| cfb5bc1eb644ad4dfb12 | £5,019.56 | £0.00 | £4,750.84 | £5,019.56 | 0.00% |
| 450dc878d9ee335224d8 | £2,332.91 | -£95.09 | £2,067.84 | £2,428.00 | 4.93% |
| 82d4ee521ec8e04996cb | £7,283.47 | £0.00 | £7,085.47 | £7,283.47 | 0.00% |
| 7701679dcab668446549 | £4,761.80 | £0.00 | £4,551.90 | £4,761.80 | 0.00% |
| 1f736dae8696c30c6a98 | £4,696.39 | -£5.60 | £4,423.51 | £4,701.99 | 1.19% |
| bae7d3186e27939929be | £7,050.74 | £0.00 | £7,307.29 | £7,050.74 | 0.00% |
| 89d2283131e5edcb7c71 | £4,672.93 | £0.00 | £4,688.15 | £4,672.93 | 0.00% |
| 9a6c628540c8307a609a | £7,928.74 | £0.00 | £7,876.79 | £7,928.74 | 0.00% |
| bd76a7e48be1ffa4c468 | £5,458.66 | £266.72 | £5,785.90 | £5,191.94 | 2.69% |
| 54f079f332a86cd24091 | £2,701.97 | £0.00 | £3,166.95 | £2,701.97 | 0.00% |
| d01fa640e211cea2be7d | £7,282.94 | £0.00 | £8,215.90 | £7,282.94 | 0.00% |
| 808b6d0d4e04bc1aaa0e | £1,352.08 | £0.00 | £1,344.96 | £1,352.08 | 0.00% |
| 212147aea8cb32c0d975 | £4,281.08 | £0.00 | £4,108.67 | £4,281.08 | 0.00% |
| 86adcef7ddaed8a99215 | £9,861.51 | £427.15 | £10,272.03 | £9,434.36 | 3.27% |
| 249160d91e430a94057b | £4,328.34 | -£8.82 | £4,764.05 | £4,337.16 | 5.82% |
| cec095327f4e4fd21773 | £6,282.59 | £0.00 | £6,739.25 | £6,282.59 | 0.00% |
| 09c2032bc47f23b8ab94 | £8,642.86 | £0.00 | £9,158.52 | £8,642.86 | 0.00% |
| fcd39f2e8f3dba197172 | £7,342.34 | £0.00 | £6,691.80 | £7,342.34 | 0.00% |
| 1550cb89223074b23e31 | £7,592.51 | £376.63 | £7,210.46 | £7,215.88 | 2.04% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 26 wins, 34 losses, 0 ties vs buy-and-hold; beat cash on 7. Median excess -1.36% of capital; mean max drawdown 1.79%; sign-test p = 0.366.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
