# Build status (checkpoint 2026-11-07, evening)

## Done (committed)

| Milestone | State |
|---|---|
| M0 skeleton, data fetched | ✅ practice 300 paths (seed 20261107), vault 150 (seed 91802611) |
| M1 spec / features / engine / stats | ✅ includes the no-look-ahead property test |
| M2 adapter + E1 parity | ✅ 300/300 cases identical to the kit runner; aggregate stats identical; 6-case self-serve challenge has no provenance warnings |
| M3 attacks + gate | ✅ A2 replaced by a calibrated shuffled-returns test (see DECISIONS D1) |
| M4 ledger + vault | ✅ |
| M5 Gemini layer | ✅ live; retry/fallback for intermittent stalls |
| M6 API + UI | ✅ driven end to end in headless Chromium; screenshots look right on desktop and phone |
| M8 autocomplete | ✅ layer 1 (local) + layer 2 (Flash-Lite) + variant warning pill |
| E2 test bank | ✅ `results/testbank/REPORT.md`: 0 false approvals on 100 no-edge cases; power rises with true edge size |
| E4 translation | ✅ `results/e4/REPORT.md`: 95% field accuracy, 10/10 ambiguous hunches asked. **A teammate should review the gold set.** |

## In flight / next

1. **E3 hidden challenges.** 10 runs were started in the background, writing to `results/challenge/<fp>/`. Then:
   - Add the second naive screen (win rate over 50% vs buy-and-hold) to `eval/run_e3.py table`. The patch failed to apply and still has to be redone. The reason: all 10 hunches have a negative practice *mean*, so the spec's naive screen rejects everything. Record this as DECISIONS D6.
   - Run `.venv\Scripts\python.exe eval\run_e3.py table`.
2. **M9 ingest.** The endpoint and UI are written but have not been tested live with a real clip.
3. **README** (setup, model IDs, maths-kept-apart diagram, how to reproduce every number, caveats, Binance Vision attribution) and the deck evidence summary.
4. Run the `review-and-push` skill (secret scan) before pushing. Gitleaks and gh are not installed yet.

## Decision needed from the team

**Demoing the vault.** No realistic hunch passes the practice gate on real data. The best have a median of +40–90 bps but sign-test p of 0.09–0.33, and every one has a negative mean. The §18 demo step "open the vault, then get blocked" therefore can't happen naturally. Options:

- (a) Demo the vault on a clearly labelled **synthetic demo market** with a planted effect.
- (b) Pre-record the vault/block moment from a test run.
- (c) Make "almost nothing survives on real data" the headline, and show the block via the HTTP test or a recording.

## Housekeeping

- The app server may still be running on port 8000. Stop it with Ctrl+C in its terminal, or end the uvicorn process.
- The Gemini key lives only in `.env` (gitignored). It was pasted in chat, so rotate it after the hackathon.
