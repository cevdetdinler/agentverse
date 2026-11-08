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
                "reasons": ["Too few trades to judge either way."] + gate["failing"]}
    if status == "REJECTED":
        return {"label": REJECTED, "stage": "practice", "reasons": gate["failing"]}
    if vault is None:
        reasons = ["Passed every check. The final exam (prices it has never seen) has not been taken yet."]
        if contaminated:
            reasons = ["Passed every check, but this version was made after seeing the idea's final exam, "
                       "so it can never be tested fairly."]
        return {"label": INCONCLUSIVE, "stage": "practice", "reasons": reasons}
    med, p = vault["median_excess_bps"], vault["sign_p"]
    p_txt = "n/a" if p is None else f"{p:.4f}"
    if med <= config.VAULT_PASS["median_excess_bps_gt"]:
        return {"label": REJECTED, "stage": "vault",
                "reasons": [f"On the final exam the typical result was {med / 100:+.2f}% vs holding (needs to be above 0%)."]}
    if p is not None and p < config.VAULT_PASS["sign_p_lt"]:
        if contaminated:
            return {"label": INCONCLUSIVE, "stage": "vault",
                    "reasons": ["The final exam looks good, but the rule was changed after seeing it, so it doesn't count."]}
        return {"label": SURVIVED, "stage": "vault",
                "reasons": [f"On the final exam it beat holding: typical result {med / 100:+.2f}%, luck score {p_txt} "
                            f"(below {config.VAULT_PASS['sign_p_lt']})."]}
    return {"label": INCONCLUSIVE, "stage": "vault",
            "reasons": [f"On the final exam the typical result was {med / 100:+.2f}%, but the luck score was {p_txt} "
                        f"(needs below {config.VAULT_PASS['sign_p_lt']}): it could still be luck."]}
