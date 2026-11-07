"""End-to-end flow from the terminal (milestone M5 check). Live Gemini calls.

    .venv\Scripts\python.exe -m skeptic.cli "BTC bounces back after a big drop" [--auto] [--vault]

--auto answers each clarifying question with its first option (for scripted runs).
--vault opens the vault if the idea is eligible (in the app this is a human click).
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys

from .agent import Agent
from .ledger import Ledger
from .pipeline import Skeptic


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hunch")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--vault", action="store_true")
    ap.add_argument("--k", type=int, default=200)
    args = ap.parse_args(argv)
    session = "cli_" + secrets.token_hex(3)
    ledger = Ledger()
    sk, agent = Skeptic(ledger), Agent(ledger)
    ledger.append("hunch_submitted", {"session_id": session, "text": args.hunch})

    out = agent.translate_hunch(session, args.hunch)
    rounds = 0
    while "questions" in out:
        rounds += 1
        answers = {}
        for q in out["questions"]:
            print(f"\n? {q['text']}")
            for i, o in enumerate(q["options"], 1):
                print(f"   {i}. {o}")
            if args.auto or not sys.stdin.isatty():
                pick = q["options"][0] if q["options"] else "use a sensible default"
                print(f"   -> {pick}")
            else:
                raw = input("   answer (number or text): ").strip()
                pick = q["options"][int(raw) - 1] if raw.isdigit() and 0 < int(raw) <= len(q["options"]) else raw
            answers[q["text"]] = pick
        ledger.append("questions_asked", {"session_id": session, "questions": out["questions"], "answers": answers})
        out = agent.translate_hunch(session, args.hunch, answers=answers, previous_id=out["interaction_id"],
                                    force_spec=rounds >= 2)
    ledger.append("spec_proposed", {"session_id": session, "spec": out["spec"], "interaction_id": out["interaction_id"]})
    approved = sk.approve_spec(session, out["spec"])  # in the app: a human clicks Approve
    print("\nRULE CARD", approved["fingerprint"][:12], "| idea", approved["idea_id"], "| trials", approved["trials"])
    for line in approved["rules_text"]:
        print("  ", line)
    for a in approved["spec"]["assumptions"]:
        print("   assumption:", a)

    res = sk.run_attacks(session, approved["fingerprint"],
                         planner=lambda spec, a1: agent.plan_diagnostics(session, spec, a1), k=args.k)
    print()
    for r in res["results"] + res["diagnostics"]:
        print(f"[{r['id']}] {'PASS' if r['passed'] else 'FAIL'} {r['name']}: {r['summary']}")
        if r["kind"] == "diagnostic":
            print(f"      pre-registered: {r['hypothesis']}")
    print("\nGATE:", res["gate"]["headline"])
    if args.vault and res["vault"]["can_open"]:
        v = sk.open_vault(session, approved["fingerprint"])
        print("VAULT:", json.dumps(v["vault"]))
    bundle = sk.results_bundle(approved["fingerprint"])
    ex = agent.explain_verdict(session, bundle, approved["fingerprint"])
    print(f"\nVERDICT: {bundle['verdict']['label']}\n{ex['text']}")
    if ex["removed_count"]:
        print(f"({ex['removed_count']} claim removed by number guard)")
    print("\nLLM interaction ids:", [e["payload"].get("interaction_id") for e in ledger.find("llm_call", session_id=session)])
    print("Ledger:", ledger.verify_chain())
    return 0


if __name__ == "__main__":
    sys.exit(main())
