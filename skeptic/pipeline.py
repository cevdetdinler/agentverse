"""Orchestration shared by the web app, the CLI and the evaluation scripts.

Hunch -> (LLM) rule card -> HUMAN approves -> (code) attacks -> (LLM) diagnostics plan, pre-registered
-> (code) diagnostics -> (code) practice verdict -> HUMAN opens vault -> (code) final verdict -> (LLM) explanation.
Every step writes to the hash-chained ledger.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from pydantic import ValidationError

from . import config
from .attacks import (
    a1_baseline,
    a2_permutation,
    a3_wobble,
    a4_cost_stress,
    a5_outliers,
    a6_trials,
    evaluate,
    practice_gate,
    run_diagnostic,
)
from .data import load_practice
from .ledger import Ledger
from .spec import RuleCard, new_idea_id
from .vault import is_contaminated, open_vault, vault_status
from .verdict import decide


_BAR_RE = re.compile(r"\b1\s*bar\s*(=|is|equals|treated as)\s*1\s*hour", re.I)


class LimitError(ValueError):
    def __init__(self, limit: str, message: str):
        super().__init__(message)
        self.limit = limit
        self.message = message


class Skeptic:
    def __init__(self, ledger: Optional[Ledger] = None, practice_paths=None, vault_inputs=None):
        self.ledger = ledger or Ledger()
        self._paths = practice_paths
        self._vault_inputs = vault_inputs

    @property
    def paths(self):
        if self._paths is None:
            self._paths = load_practice()
        return self._paths

    def limit(self, name: str, message: str, session_id: str = "", **extra) -> LimitError:
        self.ledger.append("limit_hit", {"limit": name, "message": message, "session_id": session_id, **extra})
        return LimitError(name, message)

    # ------------------------------------------------------------------ approval (human)
    def approve_spec(self, session_id: str, spec_data: dict, parent_fingerprint: Optional[str] = None) -> dict:
        try:
            card = RuleCard.model_validate(spec_data)
        except ValidationError as exc:
            msgs = "; ".join(e["msg"] for e in exc.errors()[:5])
            raise self.limit("spec_validation", f"Rule card rejected: {msgs}", session_id) from exc
        fp = card.fingerprint
        # lineage: an edited card inherits the parent's idea_id; a fresh hunch gets a new one
        idea_id = None
        same_rules = self.ledger.find("spec_approved", fingerprint=fp)
        if same_rules:  # identical rules re-submitted under a "new" hunch are still the same idea
            idea_id = same_rules[0]["payload"]["idea_id"]
        if idea_id is None and parent_fingerprint:
            parent = self.ledger.last("spec_approved", fingerprint=parent_fingerprint)
            if parent:
                idea_id = parent["payload"]["idea_id"]
        if idea_id is None and card.idea_id and self.ledger.find("trial_counted", idea_id=card.idea_id):
            idea_id = card.idea_id
        if idea_id is None:
            idea_id = card.idea_id or new_idea_id()
        card = card.model_copy(update={"idea_id": idea_id, "parent_fingerprint": parent_fingerprint or card.parent_fingerprint})
        if config.BAR_ASSUMPTION not in card.assumptions:
            others = [a for a in card.assumptions if not _BAR_RE.search(a)]
            card = card.model_copy(update={"assumptions": [config.BAR_ASSUMPTION, *others]})
        self.ledger.append("spec_approved", {
            "session_id": session_id, "fingerprint": fp, "idea_id": idea_id,
            "parent_fingerprint": card.parent_fingerprint, "spec": card.model_dump(mode="json"),
            "approved_by": "human",
        })
        if fp not in self.ledger.lineage_fingerprints(idea_id):
            self.ledger.append("trial_counted", {"session_id": session_id, "idea_id": idea_id, "fingerprint": fp,
                                                 "trials_after": self.ledger.trials(idea_id) + 1})
        return {
            "spec": card.model_dump(mode="json"), "fingerprint": fp, "idea_id": idea_id,
            "trials": self.ledger.trials(idea_id), "contaminated": is_contaminated(self.ledger, fp),
            "rules_text": card.describe(),
        }

    def spec_for(self, fingerprint: str) -> RuleCard:
        e = self.ledger.last("spec_approved", fingerprint=fingerprint)
        if not e:
            raise KeyError("unknown fingerprint: approve the rule card first")
        return RuleCard.model_validate(e["payload"]["spec"])

    # ------------------------------------------------------------------ attacks (code)
    def run_attacks(self, session_id: str, fingerprint: str,
                    planner: Optional[Callable[[RuleCard, dict], list[dict]]] = None,
                    k: int = config.PERM_K_DEFAULT) -> dict:
        if not 1 <= k <= config.LIMITS["max_perm_k"]:
            raise self.limit("max_perm_k", f"Permutation K must be at most {config.LIMITS['max_perm_k']}.", session_id)
        spec = self.spec_for(fingerprint)
        idea_id = spec.idea_id
        trials = max(1, self.ledger.trials(idea_id))
        paths = list(self.paths)
        ev = evaluate(spec, paths)
        a1 = a1_baseline(spec, paths, ev)

        # The agent sees ONLY the A1 summary and must pre-register its alternative explanations
        plan, plan_error = [], None
        if planner is not None:
            try:
                plan = planner(spec, {"summary": a1.summary, "numbers": a1.numbers})[: config.LIMITS["max_diagnostics"]]
            except Exception as exc:  # the fixed battery still runs if the model fails
                plan_error = f"{type(exc).__name__}: {exc}"[:300]
        for i, item in enumerate(plan):
            self.ledger.append("attack_planned", {
                "session_id": session_id, "fingerprint": fingerprint, "id": f"D{i + 1}", **item,
                "note": "pre-registered before this diagnostic ran",
            })

        a2 = a2_permutation(spec, paths, ev, k=k)
        a3 = a3_wobble(spec, paths, ev)
        a4 = a4_cost_stress(spec, paths, ev)
        a5 = a5_outliers(spec, paths, ev)
        a6 = a6_trials(spec, a2, trials)
        fixed = [a1, a2, a3, a4, a5, a6]
        diags = []
        for i, item in enumerate(plan):
            try:
                res = run_diagnostic(item["tool"], item.get("params", {}), spec, paths, ev, f"D{i + 1}")
                res.hypothesis = item.get("alternative_explanation") or res.hypothesis
                res.inputs.update({k_: item.get(k_) for k_ in ("alternative_explanation", "supports_if", "refutes_if")})
                diags.append(res)
            except ValueError as exc:
                self.ledger.append("limit_hit", {"session_id": session_id, "limit": "diagnostic_params",
                                                 "message": str(exc), "tool": item.get("tool")})
        for r in fixed + diags:
            self.ledger.append("attack_run", {"session_id": session_id, "fingerprint": fingerprint, **r.to_dict()})
        gate = practice_gate(fixed)
        contaminated = is_contaminated(self.ledger, fingerprint)
        verdict = decide(gate, None, contaminated=contaminated)
        self.ledger.append("verdict", {
            "session_id": session_id, "fingerprint": fingerprint, "idea_id": idea_id, "stage": "practice",
            "gate": gate, "a1": {k_: a1.numbers[k_] for k_ in ("paths", "wins", "losses", "ties", "median_excess_bps",
                                                                 "mean_excess_bps", "sign_p", "mean_max_drawdown_bps",
                                                                 "total_trades", "median_excess_ci95_bps", "exposure_pct")},
            **verdict,
        })
        return {
            "fingerprint": fingerprint, "idea_id": idea_id, "trials": trials,
            "results": [r.to_dict() for r in fixed], "diagnostics": [r.to_dict() for r in diags],
            "plan": plan, "plan_error": plan_error, "gate": gate, "verdict": verdict,
            "contaminated": contaminated, "vault": vault_status(self.ledger, fingerprint),
        }

    # ------------------------------------------------------------------ vault (human)
    def open_vault(self, session_id: str, fingerprint: str) -> dict:
        return open_vault(self.ledger, fingerprint, session_id=session_id, vault_inputs=self._vault_inputs)

    # ------------------------------------------------------------------ results bundle for explanations
    def results_bundle(self, fingerprint: str) -> dict:
        """Everything the explainer may quote. Built from the ledger, so it is exactly what was logged."""
        spec = self.spec_for(fingerprint)
        runs = {}
        for e in self.ledger.find("attack_run", fingerprint=fingerprint):
            runs[e["payload"]["id"]] = e  # latest run per attack id wins
        attack_payloads = {k: {kk: v["payload"].get(kk) for kk in ("id", "name", "hypothesis", "numbers", "passed",
                                                                     "threshold", "summary", "kind")}
                           for k, v in runs.items()}
        final = self.ledger.last("verdict", fingerprint=fingerprint, stage="final")
        practice = self.ledger.last("verdict", fingerprint=fingerprint, stage="practice")
        vault = self.ledger.last("vault_result", fingerprint=fingerprint)
        verdict = (final or practice or {}).get("payload", {})
        return {
            "fingerprint": fingerprint, "rules": spec.describe(), "assumptions": spec.assumptions,
            "trials": self.ledger.trials(spec.idea_id),
            "attacks": attack_payloads,
            "gate": practice["payload"]["gate"] if practice else None,
            "vault": vault["payload"]["vault"] if vault else None,
            "verdict": {"label": verdict.get("label"), "stage": verdict.get("stage"), "reasons": verdict.get("reasons", [])},
            "attack_seq": {k: v["seq"] for k, v in runs.items()},
        }
