# E3: hidden challenge vs Skeptic's verdicts (INDEPENDENT EVIDENCE)

Each frozen rule card was run once through the AgentVerse kit's `challenge --pack real-markets --cases 60`.
The cases are built in memory from real Binance Vision windows, the seed is committed before the run and
revealed after, and our adapter only sees the observed prefix. Practice and vault verdicts were recorded **before** the
challenge runs (`verdicts.json`, logs/e3_ledger.jsonl).

Naive screens use practice data only: **mean** = approve if mean excess vs buy-and-hold > 0 (spec definition);
**win rate** = approve if the rule beat buy-and-hold on more than half the paths (added before any hidden run, D7).
A hunch *fails* the hidden challenge if its hidden median excess vs buy-and-hold is ≤ 0.

| # | Hunch | Naive (mean) | Naive (win rate) | Skeptic | Hidden W/L vs B&H | Hidden median excess | Hidden sign p | Hidden mean max DD | Commitment |
|---|---|---|---|---|---|---|---|---|---|
| H01 | Buy a 5% drop over 24 bars, hold 24 bars | REJECT | APPROVE | REJECTED | 33/27 | 57 bps | 0.519 | 580 bps | `3c2ab3d8897455a2…` |
| H02 | Buy when RSI(14) < 30, sell when RSI(14) > 50 | REJECT | APPROVE | REJECTED | 28/32 | -163 bps | 0.699 | 600 bps | `61f1a396aec9c913…` |
| H03 | 10/50 moving-average crossover | REJECT | REJECT | REJECTED | 35/25 | 66 bps | 0.245 | 543 bps | `1640477f108d375b…` |
| H04 | Breakout above the 48-bar high, hold 24 bars, 3% stop | REJECT | REJECT | REJECTED | 29/31 | -38 bps | 0.897 | 421 bps | `4122de1c9706127e…` |
| H05 | Momentum: buy after +5% over 24 bars, hold 24 bars | REJECT | REJECT | REJECTED | 28/32 | -58 bps | 0.699 | 516 bps | `6656a6a62b93a353…` |
| H06 | Buy after 4 down bars in a row, hold 6 bars | REJECT | REJECT | REJECTED | 30/30 | 30 bps | 1.000 | 529 bps | `552e057c5001a140…` |
| H07 | Buy 3% below the 50-bar average, sell back at the average | REJECT | APPROVE | REJECTED | 29/31 | -27 bps | 0.897 | 446 bps | `0e90335225904397…` |
| H08 | Trend filter: hold while above the 200-bar average | REJECT | APPROVE | REJECTED | 31/29 | 44 bps | 0.897 | 33 bps | `e01f1c4adae76fdf…` |
| H09 | Buy a 3% dip over 6 bars, take +1.5% or exit after 12 bars | REJECT | APPROVE | REJECTED | 34/26 | 135 bps | 0.366 | 716 bps | `c5c186eee0e135f2…` |
| H10 | Buy a 10% drawdown from the 72-bar high, hold 48 bars or +5% | REJECT | APPROVE | REJECTED | 26/34 | -136 bps | 0.366 | 179 bps | `b2bd32789a96dcf1…` |

## What this shows

- Hidden runs completed: 10 of 10. Rules with a **significant** hidden edge (median > 0 and sign-test p < 0.05): **0 of 10**.
- Skeptic rejected 10; of those, 0 turned out to have a significant hidden edge (a missed edge would show up here).
- The naive win-rate screen approved 6: 3 of them lost to buy-and-hold on the hidden median, and 0 had a significant hidden edge.
- The naive mean screen approved 0; on the hidden challenge 0 of those had a median excess vs buy-and-hold ≤ 0.
- Skeptic approved (SURVIVED) 0; 0 of those failed on the hidden challenge.

Honest framing: 60 hidden paths per rule are few, and most simple rules are not distinguishable from
buy-and-hold. The claim is only that Skeptic's verdicts were better calibrated than the naive screen's, on these rules.
Because none of these rules had a hidden edge, E3 tests Skeptic's false approvals but cannot test its power to
approve a real edge; power is covered (as self-assessment) by the planted-pattern part of E2.

Hunch list provenance: see `eval/e3_hunches.json` (`note`).

Run log: H01's first challenge was interrupted when the session ended, before any case was scored (only its seed
commitment existed). It was rerun once with a fresh seed. Nine other first attempts failed to start at all (a
line-ending bug in our shell loop gave the kit an invalid output path), and were simply started. No completed
run was discarded.
