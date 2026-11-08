# Decisions and deviations from the spec

Each entry records what the spec said, what we did instead, why, and the evidence.

## D1: A2 is a shuffled-returns test, not an in-path random-entry permutation

**Spec §6 A2:** keep the same number of trades and the same holding lengths, place the entries at random bars on each path, and compare.

**Problem we measured:** on synthetic random walks with no edge (40 random rule cards × 150 paths, K = 200), the in-path random-entry permutation gave **p < 0.05 for 9 of 40 rules (22.5%)** (expected 5%). It is biased in favour of mean-reversion ("buy the dip") rules.

The cause is that it compares entries *within the same realised path*. The start and end prices are fixed (a random-walk bridge), so after a drop the rest of the path must, on average, climb back to the fixed end price. Dip-buying entries therefore beat random entries even when there is nothing to find. On real data this bias would wave through exactly the hunches Skeptic exists to challenge.

**What we do instead:** for each practice path we build K surrogate paths from the path's own one-bar log returns in random order. Each surrogate has the same start price, the same end price (up to integer rounding), and the same moves and volatility, but no information in the order of moves. We run the **exact same rule** on every surrogate with the same engine and costs, then compute p_perm = (1 + #{surrogate mean excess ≥ observed}) / (1 + K). Under the null ("the rule's timing carries no information"), the real path is exchangeable with its surrogates, so the test is valid.

**Evidence:** on the same kind of null data (100 random rule cards × 100 paths, K = 200), the share of rules with p < 0.05 is **6%** and with p < 0.10 it is **12%** ( `tests/test_attacks.py::test_shuffled_test_is_calibrated_on_null_data` guards it). On real practice data, the E1 parity rule's p moved from 0.004 (old test, misleading) to 0.32 (new test).

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

## D6: A labelled synthetic market for the live vault moment

**Problem:** on real practice data no realistic hunch passes the practice gate. The best reach a median of +40–90 bps, but their sign-test p is 0.09–0.33 and every mean is negative. So the §18 demo step "open the vault, tweak, get blocked" cannot happen live on real data.

**Team decision:** add a second market, selectable in the top bar as **"Synthetic market"**. Its prices come from our own generator (`skeptic/synthetic.py`, seeds in `config.SYNTHETIC_MARKET`) with a planted dip-then-rebound pattern. It has its own ledger, trial counts and vault, and nothing crosses between the two markets (`tests/test_server.py::test_synthetic_market_is_isolated_and_labelled`). The UI always says "Synthetic market … Not real market data", and the trace drawer names the generator and seed. Real data stays the default and is the only source of any reported result.

## D7: A second naive screen in E3

All ten E3 hunches have a negative practice *mean* excess, so the spec's naive screen ("approve if mean excess > 0") rejects every one and the comparison carries no information. We add a second naive screen, "approve if the rule beat buy-and-hold on more than half of the practice paths", which is a common retail "win rate" readout. It was added after seeing that the first screen was degenerate, but **before** any hidden-challenge result existed.

## D8: Ideas from today's real markets in the empty hunch box (added at the user's request; not in the spec)

When the hunch box is empty, the app suggests ideas built from today's actual market moves. For example: "XRP $1.16, −1.5% today → Buy XRP if it drops 3% or more within 24 hours, and sell 24 hours later". `app/today.py` reads Binance's free, public **24-hour summary** (`ticker/24hr`: last price, 24 h change, high, low) for six large coins. Plain code turns those numbers into rule-expressible ideas; no model is called. It caps the list at two ideas per coin and two per kind, so a quiet day doesn't produce six identical suggestions.

**Display only:**
- The live data never reaches a backtest, an attack, the vault or `adapter.py`.
- It fetches no price history, so nothing in it could be used to look up a hidden test path.
- `tests/test_today.py::test_live_data_never_reaches_the_maths` checks that no file under `skeptic/`, `eval/` or `adapter.py` imports it or contains a live-market URL.
- The kit's provenance strings stay absent (`tests/test_provenance.py`).

**Offline-safe:**
- The request is made server-side with a 2.5 s timeout and cached for 5 minutes. After a failure it is retried after 30 s.
- On any failure the box shows the library examples instead and never waits on the network (`test_offline_falls_back_silently`).
