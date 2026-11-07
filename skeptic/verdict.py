"""Verdict labels are decided here, by pre-registered rules. The LLM only explains them."""
from __future__ import annotations

from typing import Optional

from . import config

SURVIVED, INCONCLUSIVE, REJECTED = "SURVIVED", "INCONCLUSIVE", "REJECTED"


def decide(gate: dict, vault: Optional[dict] = None, contaminated: bool = False) -> dict:
    """gate: practice_gate() output. vault: vault stats (aggregate) or None if not opened."""
    status = gate["status"]
    if status == "INCONCLUSIVE":
        return {"label": INCONCLUSIVE, "stage": "practice",
                "reasons": ["Too few trades on practice data to judge."] + gate["failing"]}
    if status == "REJECTED":
        return {"label": REJECTED, "stage": "practice", "reasons": gate["failing"]}
    if vault is None:
        reasons = ["Passed every practice check, but the vault (unseen holdout) has not been opened."]
        if contaminated:
            reasons = ["Passed practice checks, but this version was designed after the idea's vault was used, "
                       "so it can never be tested fairly."]
        return {"label": INCONCLUSIVE, "stage": "practice", "reasons": reasons}
    med, p = vault["median_excess_bps"], vault["sign_p"]
    p_txt = "n/a" if p is None else f"{p:.4f}"
    if med <= config.VAULT_PASS["median_excess_bps_gt"]:
        return {"label": REJECTED, "stage": "vault",
                "reasons": [f"On the vault the median excess was {med} bps (needs > 0)."]}
    if p is not None and p < config.VAULT_PASS["sign_p_lt"]:
        if contaminated:
            return {"label": INCONCLUSIVE, "stage": "vault",
                    "reasons": ["Vault numbers look good, but the idea is contaminated (changed after seeing the vault)."]}
        return {"label": SURVIVED, "stage": "vault",
                "reasons": [f"On the vault the median excess was {med} bps (> 0) and the sign-test p = {p_txt} "
                            f"(< {config.VAULT_PASS['sign_p_lt']})."]}
    return {"label": INCONCLUSIVE, "stage": "vault",
            "reasons": [f"On the vault the median excess was {med} bps (> 0) but the sign-test p = {p_txt} "
                        f"(needs < {config.VAULT_PASS['sign_p_lt']}): could be chance."]}
