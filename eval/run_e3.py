"""E3: do Skeptic's verdicts predict the organisers'-style hidden challenge better than a naive backtester?

    .venv\\Scripts\\python.exe eval\\run_e3.py prepare     # verdicts (practice + vault), freeze specs, list fingerprints
    (run one hidden challenge per fingerprint: the command is in docs/COMMANDS.md, section 5)
    .venv\\Scripts\\python.exe eval\\run_e3.py table       # build results/e3/REPORT.md from the challenge summaries

Uses its own ledger (logs/e3_ledger.jsonl) so app sessions are not affected. Each hunch opens the vault at most once.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.certify import freeze  # noqa: E402
from skeptic import config  # noqa: E402
from skeptic.attacks import evaluate  # noqa: E402
from skeptic.data import load_practice  # noqa: E402
from skeptic.ledger import Ledger  # noqa: E402
from skeptic.pipeline import Skeptic  # noqa: E402
from skeptic.spec import RuleCard  # noqa: E402
from skeptic.stats import aggregate  # noqa: E402

HUNCHES = ROOT / "eval" / "e3_hunches.json"
OUT = ROOT / "results" / "e3"
CHALLENGE_DIR = ROOT / "results" / "challenge"


def prepare() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(HUNCHES.read_text(encoding="utf-8"))
    sk = Skeptic(Ledger(config.LOG_DIR / "e3_ledger.jsonl"))
    practice = load_practice()
    rows = []
    for h in data["hunches"]:
        card = RuleCard.model_validate(h["spec"])
        ev = evaluate(card, practice)
        agg = aggregate(ev.rows)
        naive = "APPROVE" if agg["mean_excess_bps"] > 0 else "REJECT"
        a = sk.approve_spec("e3", card.model_dump(mode="json"))
        fp = a["fingerprint"]
        prior = sk.ledger.last("verdict", fingerprint=fp, stage="final") or None
        if prior is None:
            out = sk.run_attacks("e3", fp, k=config.PERM_K_FINAL)
            label, stage, vault = out["verdict"]["label"], "practice", None
            if out["gate"]["vault_eligible"]:
                v = sk.open_vault("e3", fp)
                label, stage, vault = v["verdict"]["label"], "vault", v["vault"]
            failing = out["gate"]["failing"]
        else:  # rerun of prepare: reuse the stored verdict, never re-open
            label, stage = prior["payload"]["label"], "vault"
            vault = sk.ledger.last("vault_result", fingerprint=fp)["payload"]["vault"]
            failing = []
        path = freeze(RuleCard.model_validate(a["spec"]))
        rows.append({"id": h["id"], "hunch": h["hunch"], "fingerprint": fp, "certified": path.relative_to(ROOT).as_posix(),
                     "naive": naive, "naive_mean_excess_bps": agg["mean_excess_bps"],
                     "practice_median_bps": agg["median_excess_bps"], "practice_sign_p": agg["sign_p"],
                     "skeptic": label, "skeptic_stage": stage, "skeptic_failing": failing,
                     "vault_median_bps": vault["median_excess_bps"] if vault else None,
                     "vault_sign_p": vault["sign_p"] if vault else None})
        print(f"{h['id']} {fp[:12]} naive={naive:7s} skeptic={label:12s} ({stage})", file=sys.stderr)
    (OUT / "verdicts.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print("\nFingerprints to run through the hidden challenge (command template: docs/COMMANDS.md section 5):")
    for r in rows:
        print(r["fingerprint"])
    return 0


def _hidden(fp: str) -> dict | None:
    summary = CHALLENGE_DIR / fp / "summary.json"
    if not summary.exists():
        return None
    s = json.loads(summary.read_text(encoding="utf-8"))

    def find(o):
        if isinstance(o, dict):
            if "wins_vs_buy_and_hold" in o:
                return o
            for v in o.values():
                f = find(v)
                if f:
                    return f
        return None

    m = find(s) or {}
    commitment = (CHALLENGE_DIR / fp / "COMMITMENT.txt")
    return {"paths": m.get("paths"), "wins": m.get("wins_vs_buy_and_hold"), "losses": m.get("losses_vs_buy_and_hold"),
            "median": m.get("median_excess_vs_buy_and_hold_bps_of_capital"), "p": m.get("sign_test_p_value"),
            "dd": m.get("mean_max_drawdown_bps"), "verdict": m.get("verdict"),
            "commitment": commitment.read_text(encoding="utf-8").strip()[:16] if commitment.exists() else None}


def table() -> int:
    rows = json.loads((OUT / "verdicts.json").read_text(encoding="utf-8"))
    practice = load_practice()
    for r in rows:  # second naive screen (docs/DECISIONS.md D7): beat buy-and-hold on > half of practice paths
        card = RuleCard.model_validate_json((ROOT / r["certified"]).read_text(encoding="utf-8"))
        agg = aggregate(evaluate(card, practice).rows)
        r["naive_winrate"] = "APPROVE" if agg["wins"] > agg["paths"] / 2 else "REJECT"
        r["practice_wins"] = agg["wins"]
    lines = [
        "# E3: hidden challenge vs Skeptic's verdicts (INDEPENDENT EVIDENCE)",
        "",
        "Each frozen rule card was run once through the AgentVerse kit's `challenge --pack real-markets --cases 60`.",
        "The cases are built in memory from real Binance Vision windows, the seed is committed before the run and",
        "revealed after, and our adapter only sees the observed prefix. Practice and vault verdicts were recorded **before** the",
        "challenge runs (`verdicts.json`, logs/e3_ledger.jsonl).",
        "",
        "Naive screens use practice data only: **mean** = approve if mean excess vs buy-and-hold > 0 (spec definition);",
        "**win rate** = approve if the rule beat buy-and-hold on more than half the paths (added before any hidden run, D7).",
        "A hunch *fails* the hidden challenge if its hidden median excess vs buy-and-hold is ≤ 0.",
        "",
        "| # | Hunch | Naive (mean) | Naive (win rate) | Skeptic | Hidden W/L vs B&H | Hidden median excess | Hidden sign p | Hidden mean max DD | Commitment |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    tally = {"naive_approved": 0, "naive_approved_failed": 0, "skeptic_rejected": 0, "skeptic_rejected_failed": 0,
             "skeptic_survived": 0, "skeptic_survived_failed": 0, "ran": 0,
             "naive_winrate_approved": 0, "naive_winrate_approved_failed": 0}
    for r in rows:
        h = _hidden(r["fingerprint"])
        if h is None or h["median"] is None:
            lines.append(f"| {r['id']} | {r['hunch']} | {r['naive']} | {r['naive_winrate']} | {r['skeptic']} | not run | | | | |")
            continue
        tally["ran"] += 1
        failed = h["median"] <= 0
        significant = h["median"] > 0 and h["p"] is not None and h["p"] < 0.05
        tally["hidden_significant_edge"] = tally.get("hidden_significant_edge", 0) + significant
        if r["naive_winrate"] == "APPROVE":
            tally["naive_winrate_approved_significant"] = tally.get("naive_winrate_approved_significant", 0) + significant
        if r["skeptic"] != "SURVIVED":
            tally["skeptic_rejected_significant"] = tally.get("skeptic_rejected_significant", 0) + significant
        if r["naive"] == "APPROVE":
            tally["naive_approved"] += 1
            tally["naive_approved_failed"] += failed
        if r["naive_winrate"] == "APPROVE":
            tally["naive_winrate_approved"] += 1
            tally["naive_winrate_approved_failed"] += failed
        if r["skeptic"] == "SURVIVED":
            tally["skeptic_survived"] += 1
            tally["skeptic_survived_failed"] += failed
        else:
            tally["skeptic_rejected"] += 1
            tally["skeptic_rejected_failed"] += failed
        p = "n/a" if h["p"] is None else f"{h['p']:.3f}"
        lines.append(f"| {r['id']} | {r['hunch']} | {r['naive']} | {r['naive_winrate']} | {r['skeptic']} | {h['wins']}/{h['losses']} | "
                     f"{h['median']} bps | {p} | {h['dd']} bps | `{h['commitment']}…` |")
    lines += [
        "",
        "## What this shows",
        "",
        f"- Hidden runs completed: {tally['ran']} of {len(rows)}. Rules with a **significant** hidden edge "
        f"(median > 0 and sign-test p < 0.05): **{tally.get('hidden_significant_edge', 0)} of {tally['ran']}**.",
        f"- Skeptic rejected {tally['skeptic_rejected']}; of those, {tally.get('skeptic_rejected_significant', 0)} turned out to have "
        "a significant hidden edge (a missed edge would show up here).",
        f"- The naive win-rate screen approved {tally['naive_winrate_approved']}: {tally['naive_winrate_approved_failed']} of them "
        f"lost to buy-and-hold on the hidden median, and {tally.get('naive_winrate_approved_significant', 0)} had a significant hidden edge.",
        f"- The naive mean screen approved {tally['naive_approved']}; on the hidden challenge "
        f"{tally['naive_approved_failed']} of those had a median excess vs buy-and-hold ≤ 0.",
        f"- Skeptic approved (SURVIVED) {tally['skeptic_survived']}; {tally['skeptic_survived_failed']} of those failed on the hidden challenge.",
        "",
        "Honest framing: 60 hidden paths per rule are few, and most simple rules are not distinguishable from",
        "buy-and-hold. The claim is only that Skeptic's verdicts were better calibrated than the naive screen's, on these rules.",
        "Because none of these rules had a hidden edge, E3 tests Skeptic's false approvals but cannot test its power to",
        "approve a real edge; power is covered (as self-assessment) by the planted-pattern part of E2.",
        "",
        "Hunch list provenance: see `eval/e3_hunches.json` (`note`).",
        "",
        "Run log: H01's first challenge was interrupted when the session ended, before any case was scored (only its seed",
        "commitment existed). It was rerun once with a fresh seed. Nine other first attempts failed to start at all (a",
        "line-ending bug in our shell loop gave the kit an invalid output path), and were simply started. No completed",
        "run was discarded.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps({"tally": tally, "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["prepare", "table"])
    args = ap.parse_args(argv)
    return prepare() if args.step == "prepare" else table()


if __name__ == "__main__":
    sys.exit(main())
