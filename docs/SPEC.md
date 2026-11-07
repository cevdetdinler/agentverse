# Skeptic: build specification

> **For Claude Code.** This is the full spec for our UCL AgentVerse 2026 Finance track entry.
> Read it all before writing code. Build in the milestone order in §14.
> Where this spec says **MUST**, treat it as a hard requirement: it either affects the judging rubric or would get us flagged.

---

## 0. Context in 60 seconds

- **Event:** UCL AgentVerse 2026 hackathon (UCL AI Society, Google DeepMind main sponsor), Sat 7 to Sun 8 Nov 2026. Judging is Sunday afternoon. **Check the exact submission time with the organisers.** New features are frozen **2 hours before** it.
- **Track:** Finance ("Agents you would let near your own money"). Supported by Jane Street, in collaboration with the UCL Trading Society. Expected judges include people from Jane Street, JP Morgan and Stripe.
- **Deliverables:** (1) a public GitHub repo with a short README and a runnable demo; (2) a pitch deck (**judges score every team from the deck**, so all the evidence must be in it); (3) a live pitch for the top 3 only: 4 minutes plus 2 minutes of questions.
- **Rubric:**

| Weight | Criterion | What a top score looks like |
|---|---|---|
| 25% | Traceable reasoning | Any decision traces from raw data to output, **with the maths kept apart from the model**. |
| 25% | Testing on unseen data | Unseen data, real costs, a fitting benchmark and stated uncertainty. |
| 15% | Risk controls and oversight | Limits enforced in code, every action logged, **one control shown live**. |
| 20% | Relevance and impact | A specific user, with the failure that would hurt them handled on screen. |
| 15% | Ambition and technical quality | Does something a conventional program couldn't, built to a high standard. |

  "No leaderboard. **An honest result that misses its benchmark can still score top marks.**"
- **Second prize we're also aiming at:** Google DeepMind's *Best Use of Gemini*. It needs 2+ modalities in one loop, Gemini outputs verified by a real check, and an interactive experience with humans in control.

## 1. The product

**Skeptic is an AI reviewer that cross-examines trading ideas.**

- **User:** a trader testing a hunch, e.g. a UCL Trading Society member or a retail crypto trader.
- **The bad decision we prevent:** believing a backtest that only looked good because of luck, over-tweaking, leaked future data or ignored costs, and then putting money behind it.
- **The flow (the "hunch system"):**
  1. The trader types a **hunch** in plain English: *"BTC bounces back after a big drop."* Autocomplete helps as they type (§9).
  2. **Gemini** turns it into a precise **rule card** (a JSON strategy spec) and asks clarifying questions where the hunch is ambiguous. **The human approves the rule card.**
  3. **Deterministic Python** backtests it on practice data with real fees and slippage.
  4. Skeptic **attacks** the idea: a fixed set of statistical attacks, plus **alternative explanations proposed by Gemini** for this specific idea. Each one is turned into a tool call, and the Python tools run it.
  5. The trader may open the **vault** (a locked holdout) **once** for that idea.
  6. **Verdict:** `SURVIVED` / `INCONCLUSIVE` / `REJECTED`, decided by pre-registered thresholds in code. Gemini writes a plain-English explanation, and a number guard makes sure it only quotes numbers produced by the tools.
- **Pitch line:** *"Every trading bot here will tell you how much money it made. Ours tells you whether to believe it."*
- **Framing for each judge:**
  - **Jane Street:** rigour against overfitting.
  - **JP Morgan:** this is automated "effective challenge" in the sense of the Fed's SR 11-7 model-validation guidance, with an audit log and human sign-off.
  - **Stripe:** product craft and reliability.

### Golden rule: maths kept apart

**The LLM never computes, edits or invents a number.**

- It translates text into a rule card, chooses which tools to call (with parameters), and writes explanations that cite tool outputs.
- All arithmetic happens in plain, tested Python using **integer pence and integer basis points**, the same as the kit.

## 2. Hard constraints

### From the AgentVerse finance kit (`agentverse/` folder)

- The kit lives at `<project>/agentverse/` (it may be called `agentverse 2`, so quote paths). **Never modify it.** Read `agentverse/START-HERE.md`, `agentverse/finance/TESTING.md` and `agentverse/finance/DATA.md` first.
- Judges run every team through the **hidden challenge**:
  ```
  bench.py challenge --seed-prompt --team "<name>" --pack <pack> --cases 60 --project <repo> --adapter <command>
  ```
  Only **challenge** (or **live**) numbers may be quoted as results. Practice numbers never.
- The **provenance scan** flags these patterns in any `.py .js .mjs .cjs .ts .tsx .jsx .ipynb .sh` file in our repo. They **MUST NOT** appear in those files:
  - `import core` / `import bench` / `import testbed` / `import example_adapter` (and the `from … import` forms)
  - the strings `finance/core`, `finance/bench`, `finance/testbed`, or the same with `.` or `\` instead of `/`
  - `answers.jsonl`, `SEED-REVEAL`, `organiser-seed`
  - `AGENTVERSE_CHALLENGE`, `agentverse-v2:`, `agentverse-seal`
  - `data.binance.vision`, `/api/v3/klines`

  Put every command that calls the kit in **Markdown docs only** (`docs/COMMANDS.md`, `README.md`). Markdown isn't scanned.
- **Never read `answers.jsonl`.** Our data loaders read `inputs.jsonl` only.
- Our code must **not** wrap or copy the kit's `core.py`, `testbed.py` or `bench.py`. Our engine is written independently to the same published contract (§4). We prove parity by running the kit's runner against our adapter (§12, E1).

### From the Google builder guide

- **Gemini must be called live.** No mocked screens and no hard-coded JSON pretending to be a model response. A `FakeLLM` is allowed **only in unit tests**.
- The guide explicitly bans *"autonomous financial trading tools without deterministic verification checks and human approval gates."* Skeptic has both: put that quote on a slide.
- **No API keys in the repo, ever.** Use a `.env` file (gitignored) plus `.env.example`.
- All code is written during the hackathon. Open-source libraries and public datasets are fine.
- **Paper trading only.** There must be no broker, exchange-order or real-money code anywhere in the repo.

### Environment

- The team is on **Windows**. Use `py -3`, Python **3.11+**. Use `pathlib` everywhere, no hard-coded `/` paths, and quote paths that contain spaces.
- Dependencies: `fastapi`, `uvicorn`, `pydantic>=2`, `numpy`, `python-dotenv`, `google-genai>=2.3.0`, and `pytest` for dev. Nothing paid. No database: everything is JSON/JSONL files.

## 3. Data plan (three layers)

| Layer | How we get it | Used for | Who may read it |
|---|---|---|---|
| **Practice** | Kit `fetch` with seed A, 300 paths of real Binance data (anonymised, half return-inverted) → `data/practice/inputs.jsonl` | Backtests, every attack | `skeptic/data.py`, from the attack code |
| **Vault** | Kit `fetch` with seed B (≠ A), 150 paths → `data/vault/inputs.jsonl` | One-shot holdout per idea | **only** `skeptic/vault.py` |
| **Kit challenge** | `bench.py challenge --pack real-markets` (cases built in memory, seed committed before the run) | Independent final evidence for the deck | the kit's runner, through `adapter.py` |

Fetch commands go in `docs/COMMANDS.md`, never in a script:
```
py -3 "agentverse/finance/bench.py" fetch --cases 300 --seed <A> --output data/practice
py -3 "agentverse/finance/bench.py" fetch --cases 150 --seed <B> --output data/vault
```

- The kit allows 1–500 cases per fetch. Each line of `inputs.jsonl` looks like:
  ```json
  {"case_id": "...", "task": "markets", "input": {"prices_pence": [...], "dates": [...], "initial_cash_pence": int, "fee_pence": int, "slippage_bps": int}}
  ```
- Paths are 48–240 bars long. Bars are 1h or 4h, but **the interval is hidden** and the dates are fake daily dates.
- `data/` is **gitignored**: Binance Vision data is CC BY-NC-SA, and the kit never bundles it. The README says how to fetch it and credits "Binance Vision".
- **Known limitation (put it in the deck):** practice and vault windows come from the same pool of symbols and months, so some may overlap in time. The kit challenge is the stronger, independent test.

## 4. Execution contract: the engine MUST match the kit exactly

Write `skeptic/engine.py` independently, but implement **exactly** these semantics. They match the kit's walk-forward runner.

```
inputs:  prices[0..n-1] (int pence), initial_cash, fee (int pence), bps (int slippage)
cash = initial_cash; shares = 0; equity = [cash]
for i in 0 .. n-2:
    action = policy(prefix prices[0..i], cash, shares)     # decision uses ONLY bars <= i
    nxt = prices[i+1]                                       # fill at NEXT bar
    if action == "buy":
        fill  = (nxt * (10000 + bps) + 9999) // 10000       # adverse, rounded up
        units = max(0, cash - fee) // fill
        if units: cash -= units*fill + fee; shares += units
    elif action == "sell" and shares:
        fill = nxt * (10000 - bps) // 10000                 # adverse, rounded down
        cash += shares*fill - fee; shares = 0
    if cash < 0: error
    equity.append(cash + shares*nxt)
if shares:                                                   # forced final liquidation
    fill = prices[-1] * (10000 - bps) // 10000
    cash += shares*fill - fee; shares = 0
equity.append(cash)
max_drawdown_bps = max over equity of (running_peak - value) * 10000 // running_peak
```

- **Buy-and-hold benchmark** (as the kit computes it):
  ```
  buy  = (prices[1]*(10000+bps)+9999)//10000
  sell = prices[-1]*(10000-bps)//10000
  units = max(0, cash-fee)//buy
  bh_final = cash + units*(sell-buy) - (2*fee if units else 0)
  ```
- **Cash benchmark:** `initial_cash`.
- **Per-path excess:** `excess_bps = (final_cash - bh_final) * 10000 // initial_cash`.
- **Aggregate stats** (same definitions as the kit):
  - wins, losses and ties vs buy-and-hold
  - median `excess_bps` (for an even count, integer mean of the middle two)
  - mean max drawdown
  - **exact two-sided sign-test p-value**, ties excluded: `p = min(1, 2 * sum_{k<=min(w,l)} C(n,k) / 2^n)`
- Integer arithmetic only, in money paths. Floats are allowed **only** inside feature computation for signals (§5).
- `engine.simulate(prices, positions, initial_cash, fee, bps)` takes a **target-position array** (`bool` per bar for the decision at that bar) and converts it to actions:
  - `buy` if the target is in and `shares == 0`
  - `sell` if the target is out and `shares > 0`
  - `hold` otherwise
- The same conversion is used by `adapter.py`, so the engine and the adapter behave identically.

## 5. The rule card (strategy DSL)

`skeptic/spec.py` uses Pydantic models. The rules are **long-only, all-in/all-out and bar-based**, because the kit can't execute anything else.

```json
{
  "schema_version": 1,
  "name": "Buy a 5% dip, hold 72 bars",
  "hunch_text": "BTC bounces back after a big drop",
  "entry": { "all": [ {"feature": "return", "lookback": 24, "op": "<=", "value": -0.05} ] },
  "exit": {
    "hold_bars": 72,
    "take_profit": null,
    "stop_loss": null,
    "any": []
  },
  "cooldown_bars": 0,
  "assumptions": ["1 bar treated as 1 hour (test data is 1h or 4h; interval hidden)",
                  "drop measured close-to-close"],
  "parent_fingerprint": null,
  "idea_id": "idea_7f3a"
}
```

**Features.** Each is computed only from closes `p[0..t]`. If there isn't enough history, the condition is `false`.

| feature | params | definition |
|---|---|---|
| `return` | lookback L | `p[t]/p[t-L] - 1` |
| `price_vs_sma` | window W | `p[t]/SMA_W(t) - 1` |
| `sma_ratio` | fast F, slow S (F<S) | `SMA_F(t)/SMA_S(t) - 1` |
| `rsi` | window W | simple-average RSI over the last W one-bar changes, range 0–100 |
| `drawdown_from_high` | lookback L | `p[t]/max(p[t-L..t]) - 1` |
| `rise_from_low` | lookback L | `p[t]/min(p[t-L..t]) - 1` |
| `breakout` | lookback L | `p[t]/max(p[t-L..t-1]) - 1` (excludes the current bar) |
| `volatility` | lookback L | standard deviation of one-bar log returns over the last L bars |
| `down_streak` | none | number of consecutive bars ending at t with `p[i] < p[i-1]` |

**Operators:** `<`, `<=`, `>`, `>=`, `crosses_above`, `crosses_below`. The crosses operators compare the feature at t−1 and at t against `value`.

**Position logic.** `compute_positions(spec, prices) -> list[bool]` is a single O(n) pass:
- **When flat:** if the entry conditions are true at bar `i` and the cooldown has passed, the target goes in from bar `i`. The signal is at `i` and the fill is at `i+1`. Set `entry_bar = i+1` and `entry_ref = p[i+1]`. `entry_ref` is only used once `t ≥ i+1`.
- **When in a position, at bars `i ≥ entry_bar`,** exit if any of these holds:
  - `i - entry_bar >= hold_bars`
  - `p[i]/entry_ref - 1 >= take_profit`
  - `p[i]/entry_ref - 1 <= -stop_loss`
  - any of the `exit.any` conditions is true
- At least one exit rule is required.
- **Fingerprint** = SHA-256 of the canonical JSON (sorted keys, no whitespace) of `entry`, `exit` and `cooldown_bars` only. Names and text don't count.
- **Lineage:** a card created by editing another stores `parent_fingerprint` and inherits its `idea_id`. A new hunch gets a new `idea_id`.

> **No-look-ahead property (MUST be a test):** for random specs and random price paths, `compute_positions(spec, prices[:k+1])[k] == compute_positions(spec, prices)[k]` for every `k`. This is our leak guarantee: it proves no decision uses the future.

## 6. Attacks and diagnostics (`skeptic/attacks.py`)

Every attack is a pure function: `(spec, practice_paths, params, seed) -> AttackResult`. `AttackResult` holds:
- an id like `A1`
- the name
- the hypothesis being tested
- the numbers, including uncertainty
- pass/fail against its threshold
- the inputs used

Every result is written to the ledger (§8). Seeds are fixed and logged, so every number can be reproduced.

**Always run (the fixed battery):**

1. **A1 Baseline backtest:** the §4 stats on all practice paths, plus:
   - a **bootstrap 95% CI of the median excess** (2,000 path resamples)
   - total trades
   - exposure (% of bars in position)
2. **A2 Random-entry permutation test:** on each path, keep the same number of trades and the same holding lengths, but place the entries at random valid bars with no overlaps. Do this K times (default 200, 1,000 for final evaluation runs). `p_perm = (1 + #{perm_mean_excess >= observed}) / (1 + K)`. Use numpy for speed.
3. **A3 Wobble (parameter sensitivity):**
   - **One at a time:** vary each numeric parameter by ±10%, ±20% and ±30%. Integers are rounded and kept ≥ 1.
   - **Joint:** a 3×3 grid over the two most important parameters.
   - **Report:** the share of neighbours with median excess > 0, and where the user's spec ranks among them.
   - **Knife-edge** if fewer than 60% of neighbours are positive.
   - Skeptic **never** swaps in the best neighbour. Wobble is a diagnostic, not a search.
4. **A4 Cost stress:** rerun with fees ×2 and ×3 and slippage ×2 and ×3. Does the median excess stay above 0?
5. **A5 Outlier dependence:** drop the top 5% of paths by excess and recompute the median and mean. Does the sign flip?
6. **A6 Too-many-tries:** `trials` = the number of distinct fingerprints the user has backtested in this `idea_id` lineage. Report `p_adj = min(1, p_perm × trials)` (Bonferroni: simple and explainable). Show it live in the UI.

**Agent-proposed diagnostics.** Gemini picks 2–3 of these and writes, **before seeing results**, the alternative explanation it's testing and what result would support or refute it. That pre-registration is logged.
- `regime_split(by="path_trend" | "path_volatility", buckets=3)`: is the edge only present in one kind of market?
- `subsample_folds(k=5)`: is the sign of the edge consistent across folds?
- `exposure_check()`: is it mostly just buy-and-hold in disguise (high exposure, small excess)?
- `holding_sweep(values=[…])`: does the edge depend on one holding period?
- `cost_stress(multiplier=m)`
- `outlier_drop(pct=p)`

**Practice gate.** Every test must pass for the idea to be eligible for the vault. The thresholds live in `config.py`.

| Check | Pass condition |
|---|---|
| Trade count | Total trades ≥ 30, otherwise `INCONCLUSIVE: too few trades` |
| A1 | Median excess > 0 **and** sign-test p < 0.05 |
| A6 | `p_adj` < 0.05 (this already uses `p_perm` from A2) |
| A4 | Median excess > 0 with costs ×2 |
| A3 | ≥ 60% of neighbours positive |
| A5 | Median stays > 0 |

If the gate fails, the verdict is `REJECTED`, with every failing check listed in plain English.

## 7. The vault (`skeptic/vault.py`)

- It is the **only** module that reads `data/vault/inputs.jsonl`. Add a test that greps the codebase to enforce this.
- **Open vault** is allowed only for a spec that passed the practice gate. The steps:
  1. Freeze the spec and compute its fingerprint.
  2. Check the ledger:
     - If this fingerprint already opened the vault, **return the stored result**. Don't rerun anything.
     - If any spec in the same `idea_id` lineage already opened the vault, **block** it. Log `vault_blocked` and mark the spec `contaminated`. A contaminated spec can never get `SURVIVED`.
  3. **Pre-commit:** write a `vault_precommit` ledger entry with the fingerprint and the exact pass mark (from config) **before** running anything.
  4. Run the frozen spec once on all vault paths using the engine.
  5. Write `vault_result` with the full stats. Return them.
- **Final verdict:**
  - `SURVIVED` if the vault median excess > 0 **and** the vault sign-test p < 0.05.
  - `REJECTED` if the vault median excess ≤ 0.
  - `INCONCLUSIVE` otherwise.
- **The result card shows Practice vs Vault side by side,** so the user can see how much of the edge disappeared.
- **Only a human click can open the vault.** The LLM has no tool that can approve a spec or open the vault. It only receives tool *results*. This is a key risk control.

## 8. The ledger (`skeptic/ledger.py`)

- Append-only JSONL at `logs/ledger.jsonl` (gitignored). Each entry looks like:
  ```json
  {"seq": 12, "ts": "...", "type": "...", "payload": {...}, "prev_hash": "...", "hash": "sha256(prev_hash + canonical(entry without hash))"}
  ```
- **Entry types:**
  - `hunch_submitted`, `llm_call` (with model id, interaction id, purpose, token counts)
  - `spec_proposed`, `spec_approved`
  - `attack_planned` (the pre-registered alternative explanation), `attack_run`, `trial_counted`
  - `vault_precommit`, `vault_result`, `vault_blocked`
  - `verdict`, `number_guard_violation`, `suggestion_shown`, `limit_hit`
- `verify_chain()` runs on startup and from `GET /api/ledger/verify`. The UI shows **"Log intact ✓"** or **"Log tampered ✗"**.
- **Demo-able:** the UI's Log tab shows every entry. If someone edits a line by hand, the chain check fails.

## 9. Gemini layer (`skeptic/agent.py`, `skeptic/suggest.py`)

Model IDs come from the event builder guide. Put them in `config.py`:
```python
MODEL_IDS = {"reason": "gemini-4-argon", "fast": "gemini-3.8-flash", "router": "gemini-3.5-flash-lite"}
```

**SDK:**
- Use `google-genai>=2.3.0` with the **Interactions API**: `client.interactions.create(model=..., input=..., generation_config={"thinking_level": "low"|"medium"|"high"})`. The response text is `interaction.output_text`.
- Don't pass temperature, top-p or top-k: Argon ignores them.
- These APIs are newer than most training data. **Before writing Gemini code, install the official Gemini API skill** (`npx skills add google-gemini/gemini-skills --skill gemini-api-dev`) and check the current docs for:
  - structured or JSON-schema output on the Interactions API
  - multi-turn state (previous interaction IDs)
  - file uploads
  - the correct API-key environment variable

  If structured output isn't available, ask for JSON, validate it with Pydantic, and retry once with the validation error.
- Wrap every call in `agent.call(purpose, model, prompt, schema=None)`. It:
  - enforces per-session limits (default 60 Argon calls, 300 Flash-Lite calls)
  - sets a timeout (60 s for Argon)
  - logs an `llm_call` ledger entry
  - returns the interaction ID, which the UI trace shows as proof the calls are live

**Calls:**

1. **`translate_hunch(hunch, history)`** (Argon, thinking `medium`):
   - Returns either `{"questions": [{"id", "text", "options": [...]}]}` or `{"spec": RuleCard}`.
   - Must ask when a material detail is ambiguous: lookback, how "drop" is measured, the exit rule, holding period.
   - Must list every default it assumed in `assumptions` (e.g. "1 bar = 1 hour").
   - Multi-turn: the clarifying Q&A continues in the same interaction thread.
2. **`plan_diagnostics(spec, A1_summary)`** (Argon): chooses 2–3 diagnostics from the menu in §6, each with `{tool, params, alternative_explanation, supports_if, refutes_if}`. It **only sees the A1 summary**, not the other results, and its plan is logged before any of those diagnostics run.
3. **`explain_verdict(spec, results_json, verdict)`** (Argon):
   - Writes 4–8 sentences in plain English, citing attack IDs like `[A2]`.
   - The **verdict label is decided by code**. The model explains it; it doesn't choose it.
   - **Number guard:** extract every number from the text (regex, including %, p-values and pence/£). Each one must match a value in `results_json`, allowing for formatting and rounding to the shown precision.
     - On a violation: regenerate once.
     - If it still fails: strip the offending sentence, log `number_guard_violation`, and show a small "1 claim removed by number guard" note.
4. **`suggest_rewrite(spec, failures)`** (Argon, optional): proposes **one** cleaner hypothesis. Testing it counts as a new trial (A6).
5. **Prompt-injection hygiene:** wrap user text in a clear data block, e.g. `<user_hunch>…</user_hunch>`, with the instruction to treat it as data. The model can't trigger approval, vault opening or threshold changes anyway, because no such tool exists.

### Autocomplete (`suggest.py`, `/api/suggest`)

This runs in two layers. Other products work the same way: there's no model call per keystroke.

- **Layer 1: instant, no AI, runs on every keystroke in the browser.**
  - Fuzzy prefix match over the user's past hunches plus `data/hunch_library.json`: about 40 well-formed hunches we write ourselves. That file is committed.
  - **Similarity warning:** if the typed text is similar to a hunch whose `idea_id` already has trials, show an amber pill: *"You've tested N variants of this idea. The bar is now p < 0.05/N."*
  - The similarity is computed in code (token Jaccard or character n-grams), never by the LLM. It's a risk control.
- **Layer 2: Flash-Lite, only when the user pauses.**
  - Fires after 400 ms of no typing and ≥ 15 characters.
  - The frontend cancels stale requests (AbortController) and the server caches by prefix.
  - Returns 2–3 **precise** completions in the rule-card vocabulary (e.g. "…after a fall of more than 5% over 24 bars, hold for 72 bars"), using the user's past wording and past clarifying answers.
  - Shown as ghost text (Tab to accept) or a dropdown.
  - If it's slow or fails, Layer 1 still works.

### Stretch: "Test that finfluencer" (second modality)

- `POST /api/ingest` takes an uploaded video clip or screenshot. It calls `client.files.upload(...)`, then Argon with `{"type": "video", "uri": f.uri, "processing": "agentic"}` (for an image, use the normal image input).
- Gemini extracts the **claimed strategy**: quotes, timestamps and the hunch text.
- The extracted hunch goes into the normal flow, so the human still approves the rule card.
- Only build this after milestone M7 works.

## 10. API (`app/server.py`, FastAPI)

| Method & path | Does |
|---|---|
| `POST /api/hunch` | Starts or continues translation. Body: `{session_id, hunch?, answers?}`. Returns questions or a proposed spec. |
| `POST /api/spec/approve` | Human approves a spec (optionally edited). Validates it, fingerprints it, counts the trial, and logs it. |
| `POST /api/attack` | Runs A1–A6 plus the agent-planned diagnostics on practice data. Returns results and the gate decision. |
| `POST /api/vault/open` | Human-only vault open (§7). |
| `POST /api/explain` | Generates the verdict text with the number guard. |
| `GET /api/suggest?q=` | Layer 2 autocomplete (Layer 1 runs client-side). |
| `GET /api/history` | Past hunches, specs and verdicts for this user/session (feeds autocomplete). |
| `GET /api/ledger` and `/api/ledger/verify` | The log and the chain check. |
| `POST /api/ingest` | Stretch: video or image → hunch. |
| `GET /` | Serves `app/static/index.html`. |

**Limits enforced in code** (each returns a clear error and logs `limit_hit`):
- hunch length ≤ 1,000 characters
- ≤ 5 rule conditions
- lookbacks/windows ≤ 200 bars
- permutation K ≤ 2,000
- LLM call caps per session

## 11. UI (`app/static/index.html` plus `app.css` and `app.js`)

- A single page with **vanilla JS**: no build step.
- If you use a chart library, **vendor it locally** in `app/static/vendor/` so the demo works offline. Small inline SVG charts are also fine.

**Design system** (adapted from a Cal.com-style DESIGN.md). Put these tokens at the top of `app.css` as CSS variables:

- **Colours:**
  - `--primary #111111`, `--primary-active #242424`
  - `--ink #111111`, `--body #374151`, `--muted #6b7280`
  - `--hairline #e5e7eb`, `--canvas #ffffff`, `--surface-soft #f8f9fa`, `--surface-card #f5f5f5`
  - `--surface-dark #101010`, `--surface-dark-elevated #1a1a1a`, `--on-dark #ffffff`, `--on-dark-soft #a1a1aa`
  - `--success #10b981`, `--warning #f59e0b`, `--error #ef4444`
  - `--badge-violet #8b5cf6`, `--badge-orange #fb923c`, `--badge-pink #ec4899`, `--badge-emerald #34d399`
- **Type:**
  - Headings: **Inter 600 with negative letter-spacing** (−0.5 to −2px). **Do not use Cal Sans**: it's licensed to Cal.com.
  - Body: Inter 400.
  - Numbers and rule cards: **JetBrains Mono**.
  - Load the fonts from Google Fonts, with system fallbacks for offline use.
- **Radii:** 8px for buttons and inputs, 12px for cards, 16px for the hero card, pill shape for badges and tabs.
- **Spacing:** 4px base unit. 24px gutters, 32px card padding.
- **Rules:**
  - Monochrome actions: **one black primary button per step**.
  - Show real product data in cards, not illustrations.
  - **The vault is the ONLY dark card on the screen.** Dark is a scarce signal.
- **No Cal.com name, logo or wordmark anywhere.**

**Layout, top to bottom:**
1. **Top bar:** the "Skeptic" wordmark, pill tabs (**Test an idea · History · Log**), a "Log intact ✓" badge, and the model ID in use.
2. **Hunch box:** a large input with Layer 1 and Layer 2 autocomplete and the amber "N variants tested" pill.
3. **Clarifying questions:** small cards with pill-button answers.
4. **Rule card:** a white card with a hairline border. Shows the rules in mono, the assumptions list, the fingerprint (short hash) and the trial counter. Black **Approve rules** button.
5. **Attacks:** a grid of grey cards (A1–A6 plus the diagnostics). Each has a tiny chart, the key number with its CI, a pass/fail badge, and the pre-registered alternative explanation for agent diagnostics.
6. **Vault:**
   - **Locked:** dark card with a lock icon and the black/white **Open vault (one shot)** button. It is disabled with a reason if the idea is ineligible or contaminated.
   - **Opened:** the Practice vs Vault table.
7. **Verdict:** a large badge (SURVIVED green / INCONCLUSIVE amber / REJECTED red) and the Gemini explanation. Each `[A2]` citation scrolls to its card.
8. **Trace drawer:** for any number, show its source: raw data file → spec fingerprint → function → output. Also list the LLM interaction IDs.

**Live risk-control moment for the demo:** after a vault result, the user edits one parameter and clicks Open vault. It's blocked with *"This idea already used its vault. Changes made after seeing the vault can't be tested fairly."* and the block appears in the Log tab.

## 12. Evaluation (this is what wins the 25% "unseen data" criterion)

The deck must label each piece as **independent evidence** or **self-assessment**.

**E1: Engine parity (correctness).**
- Run the kit's runner in practice mode against `adapter.py` with a fixed spec.
- Compare each case's `final_cash_pence` with `engine.simulate`. They must be **identical**.
- `eval/compare_parity.py` takes two file paths as arguments. It doesn't reference the kit.
- The command lives in `docs/COMMANDS.md`.

**E2: Known-answer test bank (self-assessment, labelled as such).** `eval/testbank.py` uses **our own** synthetic generator, not the kit's:
- **Synthetic generator:**
  - Random walks with crypto-like per-bar volatility (0.5–1%), 48–240 bars.
  - **Planted effects** with a controllable strength `d`. Example: after an L-bar return ≤ −x, add drift +d per bar for H bars. Also a momentum variant.
  - Generate fresh practice **and** vault paths per strategy.
- **The bank:**
  - **Null, guaranteed:** 50 random DSL specs on synthetic paths with no planted effect. Expected: reject.
  - **Null, presumed:** 30 random specs on real practice data. Expected: mostly reject. Label as presumed.
  - **Planted:** 30 specs that target the planted effect, run at several strengths `d`. Report a **power curve**, not one cherry-picked strength.
  - **P-hacked:** 20 cases where the best of 50 variants was selected in-sample on null data. Run them twice: once with the honest trial count, and once where the user "hides" their tries (trials = 1), so only the vault can catch it.
- **Baseline ("naive backtester"):** approve if the mean excess vs buy-and-hold on practice is > 0. That's what typical retail backtest screens imply.
- **Report:**
  - false-approval rate on nulls and p-hacked cases, and true-approval rate on planted cases
  - Wilson 95% CIs for each rate
  - Skeptic vs naive, side by side
- **Output:** `results/testbank/summary.json` and `REPORT.md`.

**E3: Kit hidden challenge (independent evidence, the deck headline).**
- Take ~10 realistic hunches (written by the team **before** looking at any results).
- For each: record the naive backtester's verdict and Skeptic's verdict (on practice + vault). Then freeze the spec in `results/certified/<fp>.json` and run:
  ```
  bench.py challenge --pack real-markets --cases 60 --project . --output results/challenge/<fp> --adapter py -3 adapter.py --spec results/certified/<fp>.json
  ```
  (Check how the kit passes adapter arguments: everything after `--adapter` is the command.)
- Commit `REPORT.md`, `summary.json`, `COMMITMENT.txt` and `SEED-REVEAL.txt` for every run.
- **Headline table:** hunch | naive verdict | Skeptic verdict | hidden wins vs B&H | median excess | sign p | drawdown.
- **Honest framing:** most simple strategies will be "not distinguishable from buy-and-hold". That is expected and fine. The claim is about whether **Skeptic's verdicts predicted the hidden outcome better than the naive backtester did**.

**E4: LLM translation accuracy (self-assessment).**
- 30 hunches with gold rule cards, written by a teammate **before** running the model. Measure field-level exact match.
- 10 deliberately ambiguous hunches. Measure the share where the model asked a clarifying question instead of guessing.

**E5 (optional): live forward test.** Run `bench.py live` for 30 minutes on one certified spec. It's a demo of honest operation, **not** proof of an edge.

**Stated uncertainty everywhere:** CIs on medians and rates, p-values, the number of paths and seeds. No synthetic or backtest number is ever presented as real-world performance.

## 13. Adapter (`adapter.py`, repo root)

- Run as: `py -3 adapter.py --spec <path to frozen spec json>`. It loads the spec and checks its fingerprint matches the filename.
- **Protocol:**
  - Read one JSON object per line from stdin.
  - For `task == "market_step"`: take `prices = [h["price_pence"] for h in input["history"]]` and compute `want_in = compute_positions(spec, prices)[-1]`. Then:
    - `buy` if `want_in` and `input["shares"] == 0`
    - `sell` if not `want_in` and `shares > 0`
    - `hold` otherwise
  - Reply `{"request_id": <same>, "output": {"action": "..."}}`, one line, then **flush**.
- **Logs go to stderr only.** A stray print to stdout breaks the run.
- **No LLM calls in the adapter:** it's fast, free and deterministic. It must handle 240-bar paths well within the 10 s per-response limit.
- Imports only from `skeptic/`. Never from the kit.

## 14. Milestones (build in this order; commit after each)

| # | Milestone | Done when |
|---|---|---|
| M0 | Repo skeleton, `.gitignore` (`.env`, `data/`, `logs/`, `agentverse/`, `__pycache__/`), `.env.example`, requirements, `docs/COMMANDS.md`, data fetched | `pytest` runs; practice and vault `inputs.jsonl` exist |
| M1 | `spec.py` + features + `compute_positions` + `engine.simulate` + stats | Unit tests incl. **no-look-ahead property test** and hand-computed accounting cases pass |
| M2 | `adapter.py` + E1 parity + one self-serve `challenge --pack real-markets --cases 6` | Parity identical; challenge report generated with no provenance warnings |
| M3 | `attacks.py` A1–A6 + practice gate + diagnostics menu | Tests pass; one full attack run on 300 paths finishes in under ~60 s |
| M4 | `ledger.py` + `vault.py` | Chain verifies; tamper test fails as expected; re-open returns stored result; contaminated block works |
| M5 | `agent.py`: translate (with questions), plan diagnostics, explain + number guard; live Gemini calls logged | End-to-end from the CLI: hunch → questions → spec → attacks → verdict text |
| M6 | FastAPI + UI (§10, §11) | Full flow in the browser, including the live vault-block moment |
| M7 | Evaluation E2, E3, E4 (start the long runs in the background early) | `results/` filled; headline tables generated |
| M8 | Autocomplete Layers 1 + 2 + variant warning | Instant suggestions; AI suggestions on pause; warning pill shows |
| M9 | Stretch: video/screenshot ingest | A clip yields a hunch → rule card |
| M10 | README, deck evidence, rehearsal, secret scan (use the kit's `review-and-push` skill before pushing) | Freeze 2 h before the deadline |

**Suggested split for 3–5 people:**
- **A:** engine, adapter, attacks
- **B:** ledger, vault, evaluation
- **C:** Gemini layer and autocomplete
- **D:** UI
- **E:** deck and README

Work on branches, open PRs into `main`, and keep each person in their own files.

## 15. Repo layout

```
skeptic/                      # repo root
├── README.md                 # user/problem, 1-command setup, model IDs, how to reproduce every deck number
├── requirements.txt
├── .env.example              # GEMINI_API_KEY=  (verify exact var name in SDK docs)
├── .gitignore
├── adapter.py
├── docs/COMMANDS.md          # every kit command (fetch, run, challenge, live) — Markdown only
├── skeptic/
│   ├── config.py             # thresholds, limits, model IDs, seeds
│   ├── spec.py  features.py  engine.py  stats.py
│   ├── data.py               # loads practice inputs.jsonl only
│   ├── attacks.py  vault.py  ledger.py
│   ├── agent.py  suggest.py  numberguard.py
├── app/server.py  app/static/{index.html,app.css,app.js,vendor/}
├── data/hunch_library.json   # committed (our own text); everything else in data/ is gitignored
├── eval/testbank.py  eval/synthetic.py  eval/run_e3.py  eval/compare_parity.py  eval/translation_gold.json
├── results/                  # committed evidence: challenge reports, testbank summaries
└── tests/
```

`agentverse/` sits inside the project folder on disk but is **gitignored**. The scan skips it anyway.

## 16. README must include

- The named user and the problem, in two sentences. A screenshot.
- Setup:
  ```
  py -3 -m pip install -r requirements.txt
  ```
  then copy `.env.example` to `.env` and add your key, fetch the data (link to `docs/COMMANDS.md`), and run:
  ```
  py -3 -m uvicorn app.server:app
  ```
- **Exact Gemini model IDs used** and what each does, plus the verification loop (the "maths kept apart" diagram).
- **How to reproduce every number in the deck**, with commands and seeds.
- **Limits and honest caveats:**
  - long-only, all-in/all-out, price-only data
  - the interval is hidden, so the "1 bar = 1 hour" assumption
  - possible practice/vault overlap
  - synthetic test bank = self-assessment
  - no claim of real-world profitability
- Data attribution: **"Binance Vision"**, CC BY-NC-SA 4.0, non-commercial educational use; the data isn't redistributed.

## 17. Deck evidence checklist (judges score from the deck)

1. **Problem and user:** the trader with a hunch, and the false "this works" that costs them money.
2. **What Skeptic does:** hunch → rule card → attacks → vault → verdict, as one diagram showing **where the LLM stops and the maths starts**.
3. **Traceable reasoning:** one real trace from a raw price file to the verdict sentence, with fingerprints and interaction IDs.
4. **Evaluation:**
   - the E3 table (independent: organiser-style hidden challenge, seed commitments)
   - the E2 table with CIs (self-assessment, labelled)
   - E1 parity
   - E4 translation accuracy
5. **Risk controls:** the vault, the trial counter, human-only approval and vault, the number guard, the hash-chained log, call limits, paper-only. Include a screenshot of the live block.
6. **Limits:** the honest caveats from §16.
7. **Why an agent:** it reads vague ideas, asks the right questions, and proposes alternative explanations specific to *this* idea. A fixed program can't do that.
8. **Judge framings:**
   - rigour (Jane Street)
   - SR 11-7 "effective challenge" (JP Morgan)
   - craft and reliability (Stripe)
   - the guide's ban on unverified autonomous trading tools: we're the opposite

## 18. Demo script (under 3 minutes; open straight on the running app)

1. *(0:00)* "A trader has a hunch." Type it. Show the autocomplete, including the "variants tested" warning.
2. *(0:25)* Gemini asks 2 clarifying questions. Answer them. The rule card appears. **Approve it.**
3. *(0:50)* The attacks run. Point at the random-entry p-value, the wobble map and the cost stress. Show one Gemini-proposed alternative explanation and its test result.
4. *(1:40)* **Open the vault.** Show Practice vs Vault side by side and how much of the edge disappeared.
5. *(2:05)* **Live control:** tweak one parameter and try the vault again. It's **blocked and logged**. Show the Log tab with "Log intact ✓".
6. *(2:30)* Cut to the deck's E3 table: "the naive backtester approved X; on the organisers' hidden test, Y of those failed; Skeptic had rejected them."
7. Keep a screen recording as a backup in case the wifi fails.

## 19. Working rules for Claude Code

- Make one small, tested change at a time, and commit after each milestone with a clear message.
- **Never** modify `agentverse/`, never read `answers.jsonl`, never import kit code, and never put flagged strings in scanned file types (§2).
- Integer money arithmetic only. Floats only inside feature calculations.
- Every new function gets a test, including a counterexample.
- Every statistical claim shown to users carries its uncertainty and its source attack ID.
- **Before adding a feature that isn't in this spec, ask.** Before the deadline freeze, prefer polish and reliability over new features.
- If a requirement here conflicts with the kit's docs or the builder guide, **follow the kit or guide** and leave a note in `docs/DECISIONS.md`.
