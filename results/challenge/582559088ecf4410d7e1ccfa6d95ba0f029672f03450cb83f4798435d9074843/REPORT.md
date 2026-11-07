# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 58 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `c5c186eee0e135f2c47b0c0e29a89971d75c8583434ef739c763ca1c72ca9fd4`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `97605fc7715a84d561fe418c752e118d5aedd7db`, uncommitted changes: 2
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21dfea5eec7e65f2f38d | £3,045.40 | -£41.16 | £3,223.72 | £3,086.56 | 3.15% |
| d9bc1a9d6f47b6e9ac5c | £7,245.85 | £1,277.34 | £6,743.71 | £5,968.51 | 2.27% |
| 2515f70c0e1d8b0c6d35 | £7,811.88 | £157.84 | £7,505.74 | £7,654.04 | 0.29% |
| d1563fb1e155ccd657ea | £7,175.21 | £33.85 | £7,557.43 | £7,141.36 | 5.26% |
| f589bed276cb3d7d659b | £4,670.35 | £377.87 | £4,442.30 | £4,292.48 | 4.98% |
| cec5bde117d9f10bf430 | £893.68 | -£5,315.56 | £1,689.77 | £6,209.24 | 88.67% |
| 05684a30ea7414462e4e | £4,258.14 | -£2,638.48 | £6,537.10 | £6,896.62 | 41.97% |
| 757584248ef31235dcf0 | £8,123.31 | £0.00 | £8,748.35 | £8,123.31 | 0.00% |
| 6d860f8d8ebec4ee9381 | £7,725.54 | -£86.35 | £8,098.97 | £7,811.89 | 6.58% |
| 17df425254dc0d3057dc | £2,061.20 | £0.00 | £2,087.12 | £2,061.20 | 0.00% |
| 8755d26290b05f69bb26 | £3,510.09 | £293.24 | £3,824.56 | £3,216.85 | 13.96% |
| 1f9cdcae747e3f00caa2 | £5,356.06 | £0.00 | £6,178.64 | £5,356.06 | 0.00% |
| a6b07e4b55acb776f32a | £9,918.36 | £769.31 | £9,056.99 | £9,149.05 | 2.17% |
| 0b07a3f3946f778b38b6 | £3,952.75 | -£3.62 | £4,621.71 | £3,956.37 | 1.88% |
| f1eb189fdb646a686cff | £3,246.36 | £786.14 | £2,516.28 | £2,460.22 | 4.83% |
| 4f257a70225f2a55307f | £2,254.64 | -£8.36 | £2,225.78 | £2,263.00 | 1.21% |
| b89a7f5f6d7ca524c5c0 | £4,341.73 | -£16.83 | £4,240.33 | £4,358.56 | 1.79% |
| ae2d94798c2b00302314 | £1,996.91 | £0.00 | £2,035.97 | £1,996.91 | 0.00% |
| cab8701944a63ddb494d | £3,812.24 | -£472.89 | £3,648.21 | £4,285.13 | 16.17% |
| 8f734c98ad795269308b | £4,724.95 | -£66.16 | £4,611.08 | £4,791.11 | 2.16% |
| 1fd787bfe26cf94a7494 | £1,097.53 | £0.00 | £1,141.15 | £1,097.53 | 0.00% |
| 8748e7a620dab12eaf2d | £1,794.30 | £16.68 | £1,750.05 | £1,777.62 | 2.70% |
| ffd6ee8de2ffe978c20c | £4,587.16 | £207.77 | £5,147.73 | £4,379.39 | 4.14% |
| 39463ac420ceb4b7be43 | £1,558.97 | -£314.43 | £1,582.55 | £1,873.40 | 22.62% |
| c63950f99fa4e286e05c | £9,356.78 | £26.00 | £9,222.22 | £9,330.78 | 0.54% |
| f73d97a215f6429ebe95 | £9,612.17 | -£118.09 | £9,057.54 | £9,730.26 | 6.89% |
| 1ced4b782f824af15f87 | £9,989.64 | £220.05 | £9,062.25 | £9,769.59 | 4.03% |
| 93b94d153f5a8fd10d6b | £7,330.69 | £156.40 | £9,842.89 | £7,174.29 | 7.67% |
| e38d72a35b487ad8269a | £8,382.70 | -£207.11 | £7,598.97 | £8,589.81 | 11.54% |
| d29ea47df71d9391299a | £7,363.86 | -£846.61 | £7,346.27 | £8,210.47 | 14.68% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 34 wins, 26 losses, 0 ties vs buy-and-hold; beat cash on 21. Median excess 1.35% of capital; mean max drawdown 7.16%; sign-test p = 0.366.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
