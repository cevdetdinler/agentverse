# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 60 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `0e90335225904397c03e3c008a919dc5e8f44c0c5b9890d1d0c0355a7ce57d0b`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `e7105c8027b99efd35bdf9293afef89ee79a7174`, uncommitted changes: 20
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| c4ef6414aad29bca6dd1 | £9,880.22 | £0.00 | £9,570.97 | £9,880.22 | 0.00% |
| 0c9b6ef26ba92b17ee88 | £3,227.58 | £0.00 | £3,067.80 | £3,227.58 | 0.00% |
| 8dbbd077760dba1509e5 | £8,157.25 | -£53.34 | £7,496.57 | £8,210.59 | 2.33% |
| b55ac8eafcf8efa214e3 | £3,573.71 | £0.00 | £4,260.70 | £3,573.71 | 0.00% |
| fc8d002568f0dbebf7ea | £9,313.37 | £98.16 | £9,285.82 | £9,215.21 | 14.04% |
| fcd0f697a2255d214999 | £2,078.48 | £0.00 | £2,122.87 | £2,078.48 | 0.00% |
| 76615a965b58439e4d1e | £7,965.72 | £0.00 | £10,303.96 | £7,965.72 | 0.00% |
| e24800e0b4d98ce50370 | £4,060.09 | £536.36 | £3,011.09 | £3,523.73 | 3.08% |
| 84d2b0777486ae5e7b6d | £4,348.03 | £0.00 | £4,768.82 | £4,348.03 | 0.00% |
| 4a797d3a4754aa74e17b | £2,706.23 | £0.00 | £3,195.46 | £2,706.23 | 0.00% |
| 32dba2052cfe61fb195d | £9,683.78 | £107.56 | £10,514.96 | £9,576.22 | 2.35% |
| 7ff6302a0fba7b81f431 | £5,455.61 | -£85.89 | £7,062.32 | £5,541.50 | 8.28% |
| 3c18ef627f39fadbe3a0 | £8,492.65 | £0.00 | £9,008.28 | £8,492.65 | 0.00% |
| a57ecb791f5ce922b660 | £6,813.53 | -£36.13 | £6,518.15 | £6,849.66 | 4.18% |
| 6de3e4156a6ff32720b4 | £4,129.25 | -£971.40 | £4,082.29 | £5,100.65 | 33.66% |
| ca6afcaef5c32453b800 | £7,936.04 | £373.24 | £8,490.44 | £7,562.80 | 3.53% |
| 78b7ad3c91b16931aa3e | £9,109.72 | £0.00 | £9,081.06 | £9,109.72 | 0.00% |
| 3694c625242e782af004 | £9,917.03 | £0.00 | £9,945.39 | £9,917.03 | 0.00% |
| e2e7df36abc079c9f640 | £2,638.62 | £60.20 | £3,180.22 | £2,578.42 | 2.56% |
| e97523defe0bcd7f6a31 | £9,947.97 | £0.00 | £16,454.67 | £9,947.97 | 0.00% |
| c7ce78593f6a5a62d59a | £6,347.78 | £0.00 | £6,518.07 | £6,347.78 | 0.00% |
| d59a2e5f168934118151 | £1,198.70 | -£130.33 | £1,184.75 | £1,329.03 | 19.24% |
| f9094c0fa3f05b283e8d | £3,463.73 | -£78.40 | £4,008.51 | £3,542.13 | 2.21% |
| 8cf5eca79a630ff957de | £1,051.74 | -£19.62 | £1,012.68 | £1,071.36 | 2.34% |
| 5285972e8bf220536987 | £4,041.01 | -£111.36 | £3,934.32 | £4,152.37 | 9.65% |
| 86d91b25f777bf81a935 | £8,598.16 | £221.86 | £8,809.63 | £8,376.30 | 1.38% |
| a0b87de4f863abc79440 | £2,551.60 | -£490.44 | £2,312.10 | £3,042.04 | 22.05% |
| 1ca50b6fd9468c2eca3c | £9,027.21 | £499.52 | £10,313.14 | £8,527.69 | 3.11% |
| 0691e75736d059205960 | £7,318.46 | £0.00 | £8,371.76 | £7,318.46 | 0.00% |
| db9e387ff6ca9c0ad869 | £7,503.16 | -£1,295.10 | £6,900.85 | £8,798.26 | 20.84% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 29 wins, 31 losses, 0 ties vs buy-and-hold; beat cash on 17. Median excess -0.27% of capital; mean max drawdown 4.46%; sign-test p = 0.897.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
