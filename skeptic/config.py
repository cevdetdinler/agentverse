"""Single source of truth for thresholds, limits, model IDs and seeds.

Everything the verdict depends on is pre-registered here, before any data is seen.
Changing a threshold is a code change that shows up in git history, never a runtime option.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
LEDGER_PATH = LOG_DIR / "ledger.jsonl"
HUNCH_LIBRARY = DATA_DIR / "hunch_library.json"

# ---------------------------------------------------------------- models
# IDs from the event builder guide. "reason" = Argon, "fast" = Flash, "router" = Flash-Lite.
MODEL_IDS = {
    "reason": "gemini-4-argon",
    "fast": "gemini-3.8-flash",
    "router": "gemini-3.5-flash-lite",
}
LLM_TIMEOUT_S = {"reason": 60, "fast": 30, "router": 10}
LLM_CALL_CAPS = {"reason": 60, "fast": 120, "router": 300}  # per session

# ---------------------------------------------------------------- practice gate
ALPHA = 0.05
GATE = {
    "min_trades": 30,            # below this: INCONCLUSIVE (too few trades)
    "alpha": ALPHA,              # A1 sign test and A6 adjusted permutation p
    "cost_gate_multiplier": 2,   # A4 must stay > 0 at fees x2 and slippage x2
    "wobble_min_share": 0.60,    # A3 share of neighbours with median excess > 0
    "outlier_drop_pct": 5,       # A5 drops the top 5% of paths by excess
}
# Vault pass mark (pre-committed in the ledger before every vault run).
VAULT_PASS = {"median_excess_bps_gt": 0, "sign_p_lt": ALPHA}

# ---------------------------------------------------------------- attack settings
PERM_K_DEFAULT = 200
PERM_K_FINAL = 1000
BOOTSTRAP_RESAMPLES = 2000
WOBBLE_STEPS = (-0.30, -0.20, -0.10, 0.10, 0.20, 0.30)
WOBBLE_JOINT_STEPS = (-0.20, 0.0, 0.20)
COST_MULTIPLIERS = (2, 3)

# Fixed seeds: every number shown in the UI can be reproduced exactly.
SEEDS = {
    "bootstrap": 1101,
    "permutation": 1102,
    "folds": 1103,
}

# ---------------------------------------------------------------- limits (enforced in code)
LIMITS = {
    "hunch_chars": 1000,
    "max_conditions": 5,
    "max_lookback": 200,
    "max_hold_bars": 240,
    "max_perm_k": 2000,
    "max_diagnostics": 3,
    "max_upload_bytes": 20 * 1024 * 1024,
}

# Assumption stated on every rule card: the kit hides the bar interval (1h or 4h).
BAR_ASSUMPTION = "1 bar treated as 1 hour (test data is 1h or 4h bars; the interval is hidden)"
