# Build status (2026-11-08)

All milestones M0–M9 are done, committed and pushed to https://github.com/cevdetdinler/agentverse. 101 tests pass.

| Item | State |
|---|---|
| E1 parity | 300/300 identical to the kit runner |
| E2 test bank | 0/100 false approvals; power curve by true edge size |
| E3 hidden challenge | 10/10 runs, no provenance warnings; 0/10 significant hidden edges; Skeptic rejected 10/10; a typical backtest screen would have approved 6 |
| E4 translation | 95% field accuracy; 10/10 ambiguous hunches asked. **The gold set should be reviewed by a teammate** |
| Plain language | Website, Gemini prompts and deck use everyday words (luck check, final exam, % not bps); technical terms are kept in the evidence reports and the speaker notes |
| Synthetic market | Labelled switch; the full final-exam → edit → block flow is verified in headless Chromium |
| Screenshot ingest (M9) | Tested live with a fictional finfluencer post. **Video clips are not yet tested** |
| Today's market ideas (D8) | Display-only suggestions from Binance's public 24 h summary; works offline via fallback |
| Pitch deck | 20 slides: https://claude.ai/artifact/DJgbmaLsYEuuJrxHKqCG7P (private until shared) |

## Remaining

1. Make the GitHub repo public, if it isn't already. Optional: `gitleaks git .`
2. Test a fresh clone (README setup, then `pytest`).
3. Deck fill-ins: team names (cover and close), teammate review of the E4 gold set (slide 14 note), and a test of a real video clip or a softer wording of slide 17's footer.
4. Demo rehearsal. Gemini can word the same hunch slightly differently (e.g. RSI "is above 55" vs "crosses above 55"), which changes the result. Rehearse the exact hunches you will type. For a clean synthetic-market run, stop the server and delete `logs/synthetic_ledger.jsonl` first.
5. Optional: an E5 live forward test (`bench.py live`, ~30 min), labelled as a demo of honest operation, not evidence of an edge.

## Housekeeping

- The Gemini key is only in `.env` (gitignored). Rotate it after the event, because it was pasted in chat.
- Each market has its own ledger: logs/ledger.jsonl (real) and logs/synthetic_ledger.jsonl.
