# Decisions and deviations from the spec

Each entry records what the spec said, what we did instead, why, and the evidence.

## D1: A2 is a shuffled-returns test, not an in-path random-entry permutation

**Spec §6 A2:** keep the same number of trades and the same holding lengths, place the entries at random bars on each path, and compare.

**Problem we measured:** on synthetic random walks with no edge (100 random rule cards × 100 paths, K = 200), the in-path random-entry permutation gave **p < 0.05 for 22.5% of rules** (expected 5%). It is biased in favour of mean-reversion ("buy the dip") rules.

The cause is that it compares entries *within the same realised path*. The start and end prices are fixed (a random-walk bridge), so after a drop the rest of the path must, on average, climb back to the fixed end price. Dip-buying entries therefore beat random entries even when there is nothing to find. On real data this bias would wave through exactly the hunches Skeptic exists to challenge.

**What we do instead:** for each practice path we build K surrogate paths from the path's own one-bar log returns in random order. Each surrogate has the same start price, the same end price (up to integer rounding), and the same moves and volatility, but no information in the order of moves. We run the **exact same rule** on every surrogate with the same engine and costs, then compute p_perm = (1 + #{surrogate mean excess ≥ observed}) / (1 + K). Under the null ("the rule's timing carries no information"), the real path is exchangeable with its surrogates, so the test is valid.

**Evidence:** on the same kind of null data, the share of rules with p < 0.05 is **6%** and with p < 0.10 it is **12%** (100 rules; `tests/test_attacks.py::test_shuffled_test_is_calibrated_on_null_data` guards it). On real practice data, the E1 parity rule's p moved from 0.004 (old test, misleading) to 0.32 (new test).

**Limits:** shuffling also destroys volatility clustering, so a rule that exploits volatility regimes (not direction) can look significant. A6 still applies the Bonferroni trial count to this p_perm. A future refinement is a block shuffle.

## D2: Cost stress keeps the benchmark at real costs

**Spec §6 A4:** rerun with fees and slippage multiplied.

**Problem we observed in a live run:** when buy-and-hold also pays the multiplied costs, a rule that rarely trades "improves" as costs rise (39 → 71 → 81 bps at ×1/×2/×3). On paths where the rule sits in cash, only the benchmark gets more expensive.

**What we do:** the rule pays ×m fees and slippage, and buy-and-hold keeps the real costs. This is the conservative reading of "does the edge survive more expensive trading?". A regression test guards it.

## D3: Python 3.11 virtual environment as the adapter command

**Spec §2:** use `py -3`, Python 3.11+.

On the build machine `py -3` resolves to 3.9. The kit itself runs fine on 3.9 (standard library only). Our package needs 3.11+ and the pip packages, so we use `.venv` and pass the venv interpreter as the adapter command (`.venv\Scripts\python.exe adapter.py --spec …`). See `docs/COMMANDS.md`.

## D4: Interactions are stored (`store=True`)

Multi-turn clarifying questions continue the same thread with `previous_interaction_id`. In testing, continuing an interaction that was not stored hung until the client timeout. We therefore set `store=True` on every call.

## D5: Number guard is value-based

The guard checks that every number in the explanation equals some tool output, allowing for rounding and unit conversions. It cannot prove that a number is attached to the right label: "12%" passes if some p-value is 0.1189. The cited attack IDs and the trace drawer let a human check that. This is documented in `skeptic/numberguard.py`.
