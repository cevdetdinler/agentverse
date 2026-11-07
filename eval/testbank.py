"""E2: known-answer test bank (SELF-ASSESSMENT: we wrote the generator and the checker).

Groups
  null_guaranteed  50 random rule cards on synthetic random walks with no effect        -> should not approve
  null_presumed    30 random rule cards on real practice data (+ real vault)            -> should mostly not approve
  planted          30 rule cards targeting a planted timing effect, at several strengths -> power curve
  p_hacked         20 cases: best of 50 variants chosen in-sample on null data,
                   tested once with the honest trial count and once with trials hidden (=1)

Approve = Skeptic's final verdict is SURVIVED (practice gate passed AND one-shot vault passed).
Naive backtester = approve if the practice mean excess vs buy-and-hold is > 0.

    .venv\\Scripts\\python.exe eval\\testbank.py [--quick] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.synthetic import random_spec, synthetic_paths  # noqa: E402
from skeptic import config  # noqa: E402
from skeptic.attacks import evaluate  # noqa: E402
from skeptic.ledger import Ledger  # noqa: E402
from skeptic.pipeline import Skeptic  # noqa: E402
from skeptic.spec import RuleCard  # noqa: E402
from skeptic.stats import median_int, wilson_ci  # noqa: E402

OUT = ROOT / "results" / "testbank"
PRACTICE_N, VAULT_N = 300, 150
ORACLE_N = 3000  # ground truth for planted rules: median excess on 3,000 fresh paths from the same generator
PLANT = {"lookback": 24, "threshold": 0.04, "hold": 24}
STRENGTHS = [0.001, 0.002, 0.003, 0.004, 0.006]


def _write_inputs(path: Path, paths) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for p in paths:
            fh.write(json.dumps({"case_id": p.case_id, "task": "markets", "input": {
                "prices_pence": list(p.prices), "dates": ["2000-01-01"] * len(p.prices),
                "initial_cash_pence": p.initial_cash, "fee_pence": p.fee, "slippage_bps": p.bps}}) + "\n")


def naive_approves(spec: RuleCard, practice) -> tuple[bool, int]:
    ex = evaluate(spec, practice).excess
    mean = sum(ex) // len(ex)
    return mean > 0, mean


def skeptic_verdict(spec: RuleCard, practice, vault_paths=None, trials: int = 1, k: int = config.PERM_K_FINAL) -> dict:
    """Run the real pipeline in a throwaway ledger. vault_paths=None -> the real vault via skeptic.vault."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        vault_file = None
        if vault_paths is not None:
            vault_file = tmp / "inputs.jsonl"
            _write_inputs(vault_file, vault_paths)
        sk = Skeptic(Ledger(tmp / "ledger.jsonl"), practice_paths=list(practice), vault_inputs=vault_file)
        a = sk.approve_spec("eval", spec.model_dump(mode="json"))
        for i in range(1, trials):  # register hidden/honest extra trials in the same lineage
            sk.ledger.append("trial_counted", {"session_id": "eval", "idea_id": a["idea_id"],
                                               "fingerprint": f"variant_{i}", "trials_after": i + 1})
        out = sk.run_attacks("eval", a["fingerprint"], k=k)
        label, stage, vault = out["verdict"]["label"], "practice", None
        if out["gate"]["vault_eligible"]:
            v = sk.open_vault("eval", a["fingerprint"])
            label, stage, vault = v["verdict"]["label"], "vault", v["vault"]
        return {"label": label, "stage": stage, "gate": out["gate"]["status"],
                "failing": [c.split(":")[0] for c in out["gate"]["failing"]],
                "a1_median": out["results"][0]["numbers"]["median_excess_bps"],
                "trades": out["results"][0]["numbers"]["total_trades"],
                "p_adj": out["results"][5]["numbers"]["p_adj"],
                "vault_median": vault["median_excess_bps"] if vault else None,
                "vault_p": vault["sign_p"] if vault else None}


def _planted_spec(kind: str, rng: random.Random) -> RuleCard:
    """A rule close to (not identical with) the planted mechanism. Truth is still checked by the oracle."""
    L = rng.choice([20, 24, 28])
    x = rng.choice([0.035, 0.04, 0.045])
    H = rng.choice([18, 24])
    op, val = ("<=", -x) if kind == "dip" else (">=", x)
    return RuleCard.model_validate({"name": f"planted {kind}", "entry": {"all": [
        {"feature": "return", "lookback": L, "op": op, "value": val}]}, "exit": {"hold_bars": H}})


# ------------------------------------------------------------------ one case (runs in a worker)
def run_case(case: dict) -> dict:
    t0 = time.time()
    g, seed = case["group"], case["seed"]
    rng = random.Random(seed)
    rec = {"group": g, "seed": seed, "case": case.get("name")}
    if g == "null_guaranteed":
        spec = random_spec(rng)
        practice = synthetic_paths(seed * 7 + 1, PRACTICE_N, prefix="np")
        vault = synthetic_paths(seed * 7 + 2, VAULT_N, prefix="nv")
        rec["truth"] = "no_edge"
    elif g == "null_presumed":
        from skeptic.data import load_practice
        spec = random_spec(rng)
        practice, vault = load_practice(), None
        rec["truth"] = "presumed_no_edge"
    elif g == "planted":
        d, kind = case["strength"], case["kind"]
        effect = {"kind": kind, **PLANT, "drift": d}
        spec = _planted_spec(kind, rng)
        practice = synthetic_paths(seed * 7 + 1, PRACTICE_N, effect=effect, prefix="pp")
        vault = synthetic_paths(seed * 7 + 2, VAULT_N, effect=effect, prefix="pv")
        oracle = synthetic_paths(seed * 7 + 3, ORACLE_N, effect=effect, prefix="po")
        rec["oracle_median_excess"] = median_int(evaluate(spec, oracle).excess)
        rec.update({"truth": "edge" if rec["oracle_median_excess"] > 0 else "no_edge_for_this_rule",
                    "strength": d, "kind": kind})
    elif g == "p_hacked":
        practice = synthetic_paths(seed * 7 + 1, PRACTICE_N, prefix="hp")
        vault = synthetic_paths(seed * 7 + 2, VAULT_N, prefix="hv")
        best, best_med = None, None
        for _ in range(50):  # the trader's private search: keep the best in-sample median
            cand = random_spec(rng)
            ex = evaluate(cand, practice).excess
            med = median_int(ex)
            if sum(r > 0 or r < 0 for r in ex) and (best_med is None or med > best_med):
                best, best_med = cand, med
        spec = best
        rec.update({"truth": "no_edge", "selected_in_sample_median": best_med})
    else:
        raise ValueError(g)
    rec["spec"] = spec.rules_dict()
    rec["naive_approve"], rec["naive_mean_excess"] = naive_approves(spec, practice)
    if g == "p_hacked":
        honest = skeptic_verdict(spec, practice, vault, trials=50)
        hidden = skeptic_verdict(spec, practice, vault, trials=1)
        rec["skeptic_honest"], rec["skeptic_hidden"] = honest, hidden
        rec["skeptic_approve_honest"] = honest["label"] == "SURVIVED"
        rec["skeptic_approve_hidden"] = hidden["label"] == "SURVIVED"
        rec["hidden_passed_practice"] = hidden["gate"] == "ELIGIBLE"
    else:
        v = skeptic_verdict(spec, practice, vault)
        rec["skeptic"] = v
        rec["skeptic_approve"] = v["label"] == "SURVIVED"
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def build_cases(quick: bool) -> list[dict]:
    scale = 0.2 if quick else 1.0
    n = lambda x: max(2, int(round(x * scale)))  # noqa: E731
    cases = [{"group": "null_guaranteed", "seed": 1000 + i} for i in range(n(50))]
    cases += [{"group": "null_presumed", "seed": 2000 + i} for i in range(n(30))]
    i = 0
    per = max(2, n(6))
    for d in STRENGTHS:
        for j in range(per):
            cases.append({"group": "planted", "seed": 3000 + i, "strength": d, "kind": "dip" if j % 2 == 0 else "momentum"})
            i += 1
    cases += [{"group": "p_hacked", "seed": 4000 + i} for i in range(n(20))]
    return cases


def rate(xs: list[bool]) -> dict:
    k, n = sum(xs), len(xs)
    lo, hi = wilson_ci(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "wilson95": [round(lo, 3), round(hi, 3)]}


def summarise(recs: list[dict]) -> dict:
    by = lambda g: [r for r in recs if r["group"] == g]  # noqa: E731
    s = {"approve_rule": "Skeptic approves = final verdict SURVIVED; naive approves = practice mean excess > 0",
         "label": "SELF-ASSESSMENT (our own synthetic generator and checker)", "groups": {}}
    for g in ("null_guaranteed", "null_presumed"):
        rs = by(g)
        s["groups"][g] = {"false_approval_skeptic": rate([r["skeptic_approve"] for r in rs]),
                          "false_approval_naive": rate([r["naive_approve"] for r in rs]),
                          "skeptic_labels": _count([r["skeptic"]["label"] for r in rs])}
    rs = [r for r in by("planted") if r["truth"] == "edge"]
    s["groups"]["planted_excluded"] = {"n": len(by("planted")) - len(rs),
                                       "reason": "oracle median excess <= 0 on 3,000 fresh paths: this rule does not exploit the effect"}
    curve = []
    for d in sorted({r["strength"] for r in rs}):
        sub = [r for r in rs if r["strength"] == d]
        curve.append({"strength_drift_per_bar": d, "true_approval_skeptic": rate([r["skeptic_approve"] for r in sub]),
                      "true_approval_naive": rate([r["naive_approve"] for r in sub]),
                      "skeptic_labels": _count([r["skeptic"]["label"] for r in sub])})
    s["groups"]["planted"] = {"true_approval_skeptic_all": rate([r["skeptic_approve"] for r in rs]),
                              "true_approval_naive_all": rate([r["naive_approve"] for r in rs]),
                              "power_curve": curve}
    rs = by("p_hacked")
    s["groups"]["p_hacked"] = {
        "false_approval_naive": rate([r["naive_approve"] for r in rs]),
        "false_approval_skeptic_honest_trials": rate([r["skeptic_approve_honest"] for r in rs]),
        "false_approval_skeptic_hidden_trials": rate([r["skeptic_approve_hidden"] for r in rs]),
        "passed_practice_with_hidden_trials": rate([r["hidden_passed_practice"] for r in rs]),
    }
    return s


def _count(labels):
    out = {}
    for l in labels:
        out[l] = out.get(l, 0) + 1
    return out


def _fmt(r: dict) -> str:
    return f"{r['k']}/{r['n']} = {100 * r['rate']:.0f}% (95% CI {100 * r['wilson95'][0]:.0f}–{100 * r['wilson95'][1]:.0f}%)"


def _pct(r: dict) -> str:
    return f"{r['k']}/{r['n']}"


def report(s: dict, meta: dict) -> str:
    g = s["groups"]
    lines = [
        "# E2 known-answer test bank: SELF-ASSESSMENT",
        "",
        "> Our own synthetic generator (`eval/synthetic.py`) and our own checker. This is **not** independent",
        "> evidence. It checks that Skeptic's verdicts behave as designed when the right answer is known.",
        "",
        f"Generated {meta['finished']} · {meta['cases']} cases · permutation K = {meta['k']} · "
        f"{PRACTICE_N} practice + {VAULT_N} vault paths per synthetic case · seeds in `cases.jsonl`.",
        "",
        "**Approve** means Skeptic's final verdict is SURVIVED (it passed every practice check *and* the one-shot vault).",
        "**Naive backtester** means approve if the practice mean excess vs buy-and-hold is > 0, which is what a typical",
        "retail backtest screen implies.",
        "",
        "## False approvals (lower is better)",
        "",
        "| Group | Truth | Naive backtester | Skeptic |",
        "|---|---|---|---|",
        f"| Null, guaranteed (random rules, random walks) | no edge | {_fmt(g['null_guaranteed']['false_approval_naive'])} | {_fmt(g['null_guaranteed']['false_approval_skeptic'])} |",
        f"| Null, presumed (random rules, real practice data) | presumed none | {_fmt(g['null_presumed']['false_approval_naive'])} | {_fmt(g['null_presumed']['false_approval_skeptic'])} |",
        f"| P-hacked, honest trial count (best of 50) | no edge | {_fmt(g['p_hacked']['false_approval_naive'])} | {_fmt(g['p_hacked']['false_approval_skeptic_honest_trials'])} |",
        f"| P-hacked, tries hidden (trials = 1) | no edge | same | {_fmt(g['p_hacked']['false_approval_skeptic_hidden_trials'])} |",
        "",
        f"With tries hidden, {_fmt(g['p_hacked']['passed_practice_with_hidden_trials'])} of p-hacked rules still passed the practice "
        "gate, so they were caught (or not) only by the vault.",
        "",
        "## Power on planted effects (higher is better)",
        "",
        "Planted timing effect: after a 24-bar move of 4% (down for *dip*, up for *momentum*), the price drifts +d per bar",
        "for 24 bars, then gives it back over the next 24 bars, so buy-and-hold gains nothing from the effect on average.",
        "Test rules use nearby but not identical parameters (lookback 12/24/36, threshold 3–5%, hold 12/24/36).",
        "",
        "| drift d per bar | Naive approves | Skeptic approves | Skeptic verdicts |",
        "|---|---|---|---|",
    ]
    for c in g["planted"]["power_curve"]:
        lines.append(f"| {c['strength_drift_per_bar']} | {_fmt(c['true_approval_naive'])} | {_fmt(c['true_approval_skeptic'])} | "
                     + ", ".join(f"{k} {v}" for k, v in sorted(c["skeptic_labels"].items())) + " |")
    lines += [
        "",
        "## Reading this honestly",
        "",
        f"- On no-edge rules the naive screen approved {_pct(g['null_guaranteed']['false_approval_naive'])} (random walks), "
        f"{_pct(g['null_presumed']['false_approval_naive'])} (real data) and {_pct(g['p_hacked']['false_approval_naive'])} (p-hacked); "
        f"Skeptic approved {_pct(g['null_guaranteed']['false_approval_skeptic'])}, {_pct(g['null_presumed']['false_approval_skeptic'])} "
        f"and {_pct(g['p_hacked']['false_approval_skeptic_hidden_trials'])} (even with the tries hidden).",
        f"- Planted rules whose oracle median excess (3,000 fresh paths) was not positive are excluded from the power table "
        f"({g['planted_excluded']['n']} excluded): a planted effect does not mean every nearby rule profits from it.",
        "- Skeptic trades power for safety: at weak strengths it says REJECTED or INCONCLUSIVE. With 6 rules per strength the",
        "  confidence intervals are wide; read the trend, not single cells.",
        "- Synthetic random walks are not markets. None of these rates says anything about real-world profitability.",
        "",
        "Reproduce: `.venv\\Scripts\\python.exe eval\\testbank.py` (seeds are fixed in `build_cases`).",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    cases = build_cases(args.quick)
    out = OUT if not args.quick else OUT / "quick"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    recs = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_case, c): c for c in cases}
        for i, f in enumerate(as_completed(futs), 1):
            rec = f.result()
            recs.append(rec)
            print(f"[{i}/{len(cases)}] {rec['group']} seed={rec['seed']} {rec['seconds']}s", file=sys.stderr, flush=True)
    recs.sort(key=lambda r: (r["group"], r["seed"]))
    with (out / "cases.jsonl").open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    s = summarise(recs)
    meta = {"finished": time.strftime("%Y-%m-%d %H:%M"), "cases": len(recs), "k": config.PERM_K_FINAL,
            "seconds": round(time.time() - t0)}
    s["meta"] = meta
    (out / "summary.json").write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    (out / "REPORT.md").write_text(report(s, meta), encoding="utf-8")
    print(json.dumps(s, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
