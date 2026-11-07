# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 59 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `1640477f108d375bb542bc5ef6cf7b77c3477183bbf39ff56502e1cb428f94cf`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 13
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5e59789b75f70fae40b5 | £3,722.79 | £0.00 | £3,566.07 | £3,722.79 | 0.00% |
| c40277b8d4ba81b55d5e | £7,384.86 | -£233.72 | £6,770.78 | £7,618.58 | 3.94% |
| 0d332f53f12dd56f05d8 | £2,087.30 | -£107.22 | £2,258.32 | £2,194.52 | 4.95% |
| cc2a2a67c0afb2b34cea | £3,884.64 | £239.15 | £3,858.11 | £3,645.49 | 1.35% |
| eaf21013db5585650543 | £7,586.68 | £458.74 | £6,911.48 | £7,127.94 | 4.18% |
| bef7f58b5e2a9c174597 | £3,834.42 | £47.26 | £4,276.70 | £3,787.16 | 0.03% |
| c7807f035e97e6288205 | £2,727.30 | -£50.73 | £2,713.87 | £2,778.03 | 1.82% |
| 080ce958746afebeb583 | £9,113.85 | -£123.64 | £8,569.89 | £9,237.49 | 4.45% |
| 074d59a8d9c66fd25d38 | £1,964.14 | £178.39 | £2,003.77 | £1,785.75 | 3.21% |
| 9d68ef1fad2396bb9610 | £3,263.45 | -£182.92 | £3,783.79 | £3,446.37 | 10.23% |
| f3f4ff92ec5ce243487a | £6,470.63 | £511.40 | £6,464.63 | £5,959.23 | 4.51% |
| 7a37468e1755db2b326f | £3,415.70 | -£21.08 | £3,347.38 | £3,436.78 | 0.61% |
| 51bdcd2c7b00c859f82e | £8,569.37 | £0.00 | £7,839.25 | £8,569.37 | 0.00% |
| c13343e848e898bbbca6 | £4,567.66 | -£134.08 | £4,618.08 | £4,701.74 | 5.20% |
| 394967cd7d1557e7f6bc | £6,123.06 | -£25.14 | £6,488.22 | £6,148.20 | 0.40% |
| 05b84e9de08519d6ecb8 | £3,822.28 | £347.10 | £3,716.44 | £3,475.18 | 6.43% |
| 49311e2425efeec4a452 | £3,524.74 | £0.00 | £3,423.53 | £3,524.74 | 0.00% |
| 8c4487c43231ab7a4f8f | £9,005.21 | -£338.62 | £10,010.87 | £9,343.83 | 4.91% |
| dc5b8b8070608d996d85 | £1,637.70 | -£322.42 | £2,023.14 | £1,960.12 | 17.39% |
| 631c0d661eb9e779ac72 | £2,776.24 | -£89.28 | £2,712.80 | £2,865.52 | 3.64% |
| 28267e48e99e9bf4840a | £2,542.99 | -£45.71 | £2,714.37 | £2,588.70 | 4.43% |
| 3fd6614b9218f171f0c3 | £6,202.21 | -£10.56 | £6,162.42 | £6,212.77 | 0.65% |
| 081e0279b1195febe8df | £4,057.74 | £118.21 | £3,628.59 | £3,939.53 | 8.50% |
| 7eeef3254768f7246791 | £5,768.58 | -£710.30 | £6,352.36 | £6,478.88 | 14.18% |
| eb3f241a75028bc5aa3f | £4,121.89 | -£207.68 | £4,266.76 | £4,329.57 | 5.85% |
| 872445e57133ee5f9843 | £6,468.41 | £485.22 | £6,947.18 | £5,983.19 | 5.39% |
| 55ba30bb575f82ca6e7a | £6,569.73 | -£84.92 | £6,505.33 | £6,654.65 | 1.27% |
| 9c67b95994e61f306a27 | £3,539.29 | £281.54 | £3,233.44 | £3,257.75 | 5.34% |
| 4b2b9936cfb107344044 | £6,789.90 | -£244.73 | £9,767.07 | £7,034.63 | 14.06% |
| 59aa4874fc652a8a8e4b | £2,705.89 | £2.52 | £2,707.36 | £2,703.37 | 0.38% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 35 wins, 25 losses, 0 ties vs buy-and-hold; beat cash on 22. Median excess 0.66% of capital; mean max drawdown 5.43%; sign-test p = 0.245.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
