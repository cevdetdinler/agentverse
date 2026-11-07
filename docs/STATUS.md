# Build status (2026-11-07, late evening)

All milestones M0–M8 are done and committed, M9 is written, and the README is in place. 95 tests pass.

| Item | State |
|---|---|
| E1 parity | 300/300 identical to the kit runner |
| E2 test bank | 0/100 false approvals; power curve by true edge size |
| E3 hidden challenge | 10/10 runs, no provenance warnings; 0/10 significant hidden edges; Skeptic rejected 10/10; win-rate screen would have approved 6 |
| E4 translation | 95% field accuracy; 10/10 ambiguous hunches asked. **Gold set should be reviewed by a teammate** |
| Synthetic market | labelled switch; full vault, edit and block flow verified in headless Chromium |

## Remaining

1. M9 ingest: the endpoint and UI are written but have not been tested with a real video or screenshot.
2. Deck: the evidence is in README "Evidence", results/*/REPORT.md and docs/DECISIONS.md (the D1 A2 story is a strong slide).
3. Push: run the kit's `review-and-push` skill first. It needs gitleaks, which is not installed yet, and gh for PRs.
4. Optional: E5 live forward test (`bench.py live`, ~30 min), labelled as a demo of honest operation, not an edge.

## Housekeeping

- The Gemini key is only in `.env` (gitignored). Rotate it after the event, since it was pasted in chat.
- Each market has its own ledger: logs/ledger.jsonl (real) and logs/synthetic_ledger.jsonl.
