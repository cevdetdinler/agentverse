"""The vault: a locked holdout, opened at most once per idea lineage, only by a human click.

This is the ONLY module that knows where the holdout lives (enforced by tests/test_provenance.py).
No LLM tool can reach it: the agent layer has no function that calls open_vault.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import config
from .attacks import evaluate
from .data import PricePath, parse_rows
from .ledger import Ledger
from .spec import RuleCard
from .stats import aggregate, bootstrap_median_ci
from .verdict import decide

VAULT_INPUTS = config.DATA_DIR / "vault" / "inputs.jsonl"
BLOCK_MESSAGE = ("This idea already took its final exam. Changes made after seeing the result can't be tested fairly.")


class VaultError(Exception):
    def __init__(self, code: str, message: str, payload: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload or {}


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[PricePath, ...]:
    p = Path(path)
    if not p.exists():
        raise VaultError("vault_missing", f"Vault data missing at {p}. Fetch it first: see docs/COMMANDS.md")
    with p.open(encoding="utf-8") as fh:
        return tuple(parse_rows(fh))


def vault_status(ledger: Ledger, fingerprint: str) -> dict:
    """Read-only view for the UI: can this spec open the vault, and if not, why."""
    approved = ledger.last("spec_approved", fingerprint=fingerprint)
    if not approved:
        return {"state": "unknown_spec", "can_open": False, "reason": "Approve the rules first."}
    idea_id = approved["payload"]["idea_id"]
    stored = ledger.last("vault_result", fingerprint=fingerprint)
    if stored:
        return {"state": "opened", "can_open": False, "reason": "Already taken for these exact rules.",
                "result": stored["payload"]}
    other = [e for e in ledger.find("vault_result", idea_id=idea_id) if e["payload"]["fingerprint"] != fingerprint]
    if other:
        return {"state": "contaminated", "can_open": False, "reason": BLOCK_MESSAGE,
                "opened_by": other[-1]["payload"]["fingerprint"]}
    practice = ledger.last("verdict", fingerprint=fingerprint, stage="practice")
    if not practice:
        return {"state": "locked", "can_open": False, "reason": "Run the checks first."}
    if not practice["payload"]["gate"]["vault_eligible"]:
        return {"state": "ineligible", "can_open": False,
                "reason": "Only ideas that pass every check can take the final exam: " + practice["payload"]["gate"]["headline"]}
    return {"state": "ready", "can_open": True, "reason": "One attempt. The result is final for this idea."}


def is_contaminated(ledger: Ledger, fingerprint: str) -> bool:
    if ledger.find("vault_blocked", fingerprint=fingerprint):
        return True
    approved = ledger.last("spec_approved", fingerprint=fingerprint)
    if not approved:
        return False
    idea_id = approved["payload"]["idea_id"]
    first_approval = ledger.find("spec_approved", fingerprint=fingerprint)[0]["seq"]
    return any(e["seq"] < first_approval and e["payload"]["fingerprint"] != fingerprint
               for e in ledger.find("vault_result", idea_id=idea_id))


def open_vault(ledger: Ledger, fingerprint: str, session_id: str = "", vault_inputs=None) -> dict:
    """Human-only action (called from the HTTP endpoint behind a button, never from the agent)."""
    approved = ledger.last("spec_approved", fingerprint=fingerprint)
    if not approved:
        raise VaultError("unknown_spec", "This rule card was never approved.")
    spec = RuleCard.model_validate(approved["payload"]["spec"])
    if spec.fingerprint != fingerprint:
        raise VaultError("fingerprint_mismatch", "Stored rule card does not match its fingerprint.")
    idea_id = approved["payload"]["idea_id"]

    # 1. same fingerprint already opened -> return the stored result, never rerun
    stored = ledger.last("vault_result", fingerprint=fingerprint)
    if stored:
        return {**stored["payload"], "replayed": True}

    # 2. another version of this idea already opened -> block and mark contaminated
    other = [e for e in ledger.find("vault_result", idea_id=idea_id) if e["payload"]["fingerprint"] != fingerprint]
    if other:
        ledger.append("vault_blocked", {
            "fingerprint": fingerprint, "idea_id": idea_id, "session_id": session_id,
            "opened_by_fingerprint": other[-1]["payload"]["fingerprint"], "contaminated": True,
            "message": BLOCK_MESSAGE,
        })
        raise VaultError("vault_blocked", BLOCK_MESSAGE, {"contaminated": True})

    # 3. eligibility comes from the ledger, not from the caller
    practice = ledger.last("verdict", fingerprint=fingerprint, stage="practice")
    if not practice or not practice["payload"]["gate"]["vault_eligible"]:
        raise VaultError("not_eligible", "Only rule cards that passed every practice check may open the vault.")

    # 4. pre-commit the pass mark BEFORE touching the data
    if isinstance(vault_inputs, (list, tuple)):  # an in-memory holdout (the synthetic market)
        paths = tuple(vault_inputs)
    else:
        paths = _load(str(vault_inputs or VAULT_INPUTS))
    ledger.append("vault_precommit", {
        "fingerprint": fingerprint, "idea_id": idea_id, "session_id": session_id,
        "pass_mark": dict(config.VAULT_PASS), "vault_paths": len(paths),
    })

    # 5. one run of the frozen spec on every vault path
    ev = evaluate(spec, paths)
    agg = aggregate(ev.rows)
    lo, hi = bootstrap_median_ci(ev.excess, config.BOOTSTRAP_RESAMPLES, config.SEEDS["bootstrap"])
    bars_in = sum(r["bars_in_position"] for r in ev.rows)
    decisions = sum(r["decisions"] for r in ev.rows)
    stats = {**agg, "sign_p": None if agg["sign_p"] is None else round(agg["sign_p"], 4),
             "median_excess_ci95_bps": [lo, hi],
             "exposure_pct": round(100.0 * bars_in / decisions, 1) if decisions else 0.0}
    gate = practice["payload"]["gate"]
    verdict = decide(gate, stats, contaminated=is_contaminated(ledger, fingerprint))
    practice_a1 = practice["payload"].get("a1", {})
    result = {
        "fingerprint": fingerprint, "idea_id": idea_id, "session_id": session_id,
        "vault": stats, "practice": practice_a1, "verdict": verdict,
        "edge_retained_pct": _retained(practice_a1.get("median_excess_bps"), stats["median_excess_bps"]),
    }
    ledger.append("vault_result", result)
    ledger.append("verdict", {**verdict, "fingerprint": fingerprint, "idea_id": idea_id, "stage": "final",
                              "decided_on": verdict["stage"], "session_id": session_id})
    return {**result, "replayed": False}


def _retained(practice_median: Optional[int], vault_median: int) -> Optional[float]:
    if not practice_median or practice_median <= 0:
        return None
    return round(100.0 * vault_median / practice_median, 1)
