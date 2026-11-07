# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 59 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `e01f1c4adae76fdf42811465f69fab0e85db3113138a010dd927750c0d4881cd`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 21
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2820a591d5051b3fc967 | £9,532.34 | £0.00 | £9,202.76 | £9,532.34 | 0.00% |
| 482bad69ca0f92e90864 | £8,450.29 | £0.00 | £6,454.33 | £8,450.29 | 0.00% |
| 6fa6039c3d09bcc4ad2a | £6,140.11 | £0.00 | £5,468.71 | £6,140.11 | 0.00% |
| d0a81ce692e144709baa | £1,757.03 | £0.00 | £1,802.35 | £1,757.03 | 0.00% |
| edc7ea5135e4ec6eeae5 | £8,466.85 | £0.00 | £7,986.07 | £8,466.85 | 0.00% |
| a4558edd25f1dd5c3863 | £4,525.56 | £0.00 | £4,222.65 | £4,525.56 | 0.00% |
| 4b2b07e330c66d11fbd3 | £6,804.09 | -£15.20 | £7,081.19 | £6,819.29 | 0.22% |
| b6b43356eaeaec443c8e | £8,488.65 | £0.00 | £7,806.55 | £8,488.65 | 0.00% |
| 2eea21ba190609c7c513 | £1,974.77 | £0.00 | £2,209.50 | £1,974.77 | 0.00% |
| 67ff86906327635e0791 | £6,356.89 | £0.00 | £5,664.21 | £6,356.89 | 0.00% |
| 4236826df5229e03ec75 | £8,354.14 | -£46.38 | £10,803.44 | £8,400.52 | 2.45% |
| 307619b7b094b29a5674 | £8,201.91 | £0.00 | £8,028.11 | £8,201.91 | 0.00% |
| 860362f624be1797aa6f | £4,918.81 | £0.00 | £4,872.91 | £4,918.81 | 0.00% |
| 0057784fa381185d422e | £3,954.64 | £0.00 | £3,675.30 | £3,954.64 | 0.00% |
| c427a2b4f7911f69bc03 | £6,866.39 | £0.00 | £7,150.85 | £6,866.39 | 0.00% |
| c9822467ffc10e262a6e | £6,468.70 | £2.30 | £6,157.58 | £6,466.40 | 2.32% |
| c55eb8d2fe3be49329f2 | £3,784.15 | £0.00 | £3,664.37 | £3,784.15 | 0.00% |
| 77d1d863eb62ed647962 | £2,549.65 | -£24.50 | £2,647.09 | £2,574.15 | 1.07% |
| 4004d4b7235c4c2e0de0 | £7,902.67 | £0.00 | £8,310.66 | £7,902.67 | 0.00% |
| 96ab04a39a56715c8e70 | £6,987.04 | £0.00 | £7,745.95 | £6,987.04 | 0.00% |
| 56accb421735f71a14a1 | £8,364.11 | -£31.33 | £8,370.11 | £8,395.44 | 4.87% |
| b1d190e8111ebe899b35 | £3,649.92 | £0.00 | £3,198.40 | £3,649.92 | 0.00% |
| 46e96f15ca873a24e635 | £7,689.56 | £0.00 | £7,891.01 | £7,689.56 | 0.00% |
| 8236077d9f8d09a9e120 | £4,674.91 | £0.00 | £5,358.43 | £4,674.91 | 0.00% |
| 3dd0940162a2fbdfebe6 | £4,831.62 | £0.00 | £4,383.38 | £4,831.62 | 0.00% |
| 63a4c1dd63197aa73698 | £1,043.39 | £0.00 | £871.58 | £1,043.39 | 0.00% |
| 4ab5e2d7cd9cc1c66d69 | £5,615.91 | £0.00 | £3,963.21 | £5,615.91 | 0.00% |
| 01755a938d53ea6bb9d2 | £5,974.85 | £31.10 | £8,227.58 | £5,943.75 | 1.32% |
| 7448df8375fee8647ffe | £6,473.62 | -£159.88 | £6,565.00 | £6,633.50 | 5.04% |
| dc79718bc82a805919b4 | £4,017.69 | £0.00 | £4,634.55 | £4,017.69 | 0.00% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 31 wins, 29 losses, 0 ties vs buy-and-hold; beat cash on 2. Median excess 0.44% of capital; mean max drawdown 0.33%; sign-test p = 0.897.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
