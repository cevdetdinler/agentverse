# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 60 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `3c2ab3d8897455a2c2b301c37ec66d590cb838e30e96101fa83703063c9f06b2`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 4
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| fe800911c82ab667fab0 | £4,794.55 | £143.86 | £4,862.63 | £4,650.69 | 2.86% |
| 6a5e74144675edb386bf | £9,880.45 | £0.00 | £9,858.23 | £9,880.45 | 0.00% |
| 051695fe88be21eb9f84 | £5,473.28 | £27.50 | £4,837.76 | £5,445.78 | 2.38% |
| f1dfa9c4b18457585847 | £1,671.42 | -£2.30 | £1,639.56 | £1,673.72 | 0.13% |
| 1fd92f93629b9c5ab5ac | £5,506.87 | -£310.35 | £4,973.26 | £5,817.22 | 9.99% |
| 44c48388a6ded6dd423d | £3,726.36 | -£237.54 | £4,411.16 | £3,963.90 | 6.36% |
| c627d2cd6103709683d5 | £9,385.82 | £900.37 | £9,237.89 | £8,485.45 | 4.83% |
| 0948d80d0321aa878e16 | £6,836.31 | £0.00 | £7,033.41 | £6,836.31 | 0.00% |
| 9fb66f23339c20d553b7 | £10,795.61 | £1,203.89 | £11,614.64 | £9,591.72 | 11.73% |
| ec49ea54533c04c1d2f6 | £7,845.17 | £602.42 | £7,910.13 | £7,242.75 | 2.37% |
| 1a64025cfa8d0d05ba6f | £8,416.11 | -£404.11 | £7,718.06 | £8,820.22 | 7.94% |
| 00cb3ba17c93ed5c45cc | £3,619.88 | -£4,464.36 | £2,920.48 | £8,084.24 | 63.50% |
| 10bfadcb0307a3c64d73 | £4,093.90 | £0.00 | £4,183.00 | £4,093.90 | 0.00% |
| 41969c82a6aab18f12ba | £7,675.32 | £0.00 | £7,627.26 | £7,675.32 | 0.00% |
| 7f6b6ee9ea71bb610c66 | £7,885.32 | -£1,433.75 | £7,460.26 | £9,319.07 | 20.74% |
| 292b906e0979f76012a3 | £9,445.21 | £0.00 | £9,421.47 | £9,445.21 | 0.00% |
| b20327a64932b80a64b9 | £6,716.87 | £197.08 | £7,305.39 | £6,519.79 | 9.90% |
| 0ddac168bf1a93e3fc6e | £5,746.41 | -£168.07 | £5,165.40 | £5,914.48 | 13.41% |
| b8830178e268aab97a29 | £4,591.97 | £495.81 | £4,453.10 | £4,096.16 | 3.32% |
| 95a1aa039e55eb551e27 | £5,050.26 | £0.00 | £5,085.30 | £5,050.26 | 0.00% |
| fd4003f12f56391b3fb6 | £2,275.92 | £0.00 | £2,317.86 | £2,275.92 | 0.00% |
| 338809f086f85d24f526 | £7,781.01 | -£14.18 | £7,580.75 | £7,795.19 | 3.20% |
| 2ef53812e03c7fb54795 | £8,715.87 | £0.00 | £9,103.29 | £8,715.87 | 0.00% |
| f04900a3cd5ed1664c9d | £2,340.39 | £65.12 | £2,369.30 | £2,275.27 | 2.06% |
| f4c814b87c032de3bb97 | £8,967.32 | -£24.73 | £8,692.57 | £8,992.05 | 3.79% |
| e7b1e844cef79c87e39e | £6,486.97 | £86.04 | £6,452.64 | £6,400.93 | 1.80% |
| c08caaacd96f0b0d8d1a | £4,093.77 | £0.00 | £4,176.27 | £4,093.77 | 0.00% |
| a14c20ec63a3847abe39 | £3,503.11 | £21.10 | £4,782.94 | £3,482.01 | 1.20% |
| 9038b23c74b59497ad2a | £3,018.24 | -£481.16 | £3,527.52 | £3,499.40 | 14.84% |
| 6c936259fb9f4c2e12bf | £2,498.47 | £0.00 | £2,368.51 | £2,498.47 | 0.00% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 33 wins, 27 losses, 0 ties vs buy-and-hold; beat cash on 20. Median excess 0.57% of capital; mean max drawdown 5.80%; sign-test p = 0.519.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
