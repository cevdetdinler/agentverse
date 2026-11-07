"""E4: translation accuracy (SELF-ASSESSMENT). Live Gemini calls; gold cards in eval/translation_gold.json.

    .venv\\Scripts\\python.exe eval\\run_e4.py [--workers 4]

Unambiguous hunches: field-level exact match of the proposed rule card vs gold (strict, and op-lenient where
"<" == "<=" and ">" == ">="). Ambiguous hunches: share where the model asked a clarifying question.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skeptic import config  # noqa: E402
from skeptic.agent import Agent  # noqa: E402
from skeptic.ledger import Ledger  # noqa: E402
from skeptic.stats import wilson_ci  # noqa: E402

GOLD = ROOT / "eval" / "translation_gold.json"
OUT = ROOT / "results" / "e4"
LENIENT = {"<": "<", "<=": "<", ">": ">", ">=": ">", "crosses_above": "crosses_above", "crosses_below": "crosses_below"}


def _cond_key(c: dict, lenient: bool) -> tuple:
    params = tuple((k, c.get(k)) for k in ("lookback", "window", "fast", "slow") if c.get(k) is not None)
    op = LENIENT[c["op"]] if lenient else c["op"]
    return (c["feature"], op, round(float(c["value"]), 6), params)


def _match_conds(gold: list, got: list, lenient: bool) -> tuple[int, int]:
    g = [_cond_key(c, lenient) for c in gold]
    m = [_cond_key(c, lenient) for c in got]
    hit = 0
    for k in g:
        if k in m:
            m.remove(k)
            hit += 1
    return hit, len(g) + len(m)  # fields = gold conditions + unmatched extra conditions the model added


def score(gold: dict, spec: dict, lenient: bool) -> dict:
    fields, hits = 0, 0
    h, n = _match_conds(gold["entry"]["all"], spec["entry"]["all"], lenient)
    hits, fields = hits + h, fields + n
    h, n = _match_conds(gold["exit"].get("any") or [], spec["exit"].get("any") or [], lenient)
    hits, fields = hits + h, fields + n
    for k in ("hold_bars", "take_profit", "stop_loss"):
        a, b = gold["exit"].get(k), spec["exit"].get(k)
        if a is None and b is None:
            continue
        fields += 1
        hits += a is not None and b is not None and abs(float(a) - float(b)) < 1e-9
    a, b = gold.get("cooldown_bars", 0) or 0, spec.get("cooldown_bars", 0) or 0
    if a or b:
        fields += 1
        hits += a == b
    return {"fields": fields, "hits": hits, "exact": hits == fields}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    agent = Agent(Ledger(config.LOG_DIR / "e4_ledger.jsonl"))
    OUT.mkdir(parents=True, exist_ok=True)

    def run(item):
        t0 = time.time()
        try:
            out = agent.translate_hunch(f"e4_{item['id']}", item["hunch"])
            return {**item, "result": out, "seconds": round(time.time() - t0, 1)}
        except Exception as exc:
            return {**item, "error": f"{type(exc).__name__}: {exc}", "seconds": round(time.time() - t0, 1)}

    items = data["unambiguous"] + data["ambiguous"]
    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(run, items))
    unamb = [r for r in results if r["id"].startswith("G")]
    amb = [r for r in results if r["id"].startswith("Q")]
    rows = []
    for r in unamb:
        res = r.get("result") or {}
        if "spec" in res:
            s_strict, s_len = score(r["gold"], res["spec"], False), score(r["gold"], res["spec"], True)
            rows.append({"id": r["id"], "hunch": r["hunch"], "outcome": "spec", "strict": s_strict, "lenient": s_len,
                         "spec": {k: res["spec"][k] for k in ("entry", "exit", "cooldown_bars")}, "interaction_id": res.get("interaction_id")})
        else:
            rows.append({"id": r["id"], "hunch": r["hunch"], "outcome": "questions" if "questions" in res else "error",
                         "detail": res.get("questions") or r.get("error")})
    specs = [r for r in rows if r["outcome"] == "spec"]
    f_strict = sum(r["strict"]["hits"] for r in specs), sum(r["strict"]["fields"] for r in specs)
    f_len = sum(r["lenient"]["hits"] for r in specs), sum(r["lenient"]["fields"] for r in specs)
    exact_strict = sum(r["strict"]["exact"] for r in specs)
    exact_len = sum(r["lenient"]["exact"] for r in specs)
    asked_amb = sum("questions" in (r.get("result") or {}) for r in amb)
    asked_unamb = sum(r["outcome"] == "questions" for r in rows)
    errors = sum(r["outcome"] == "error" for r in rows) + sum("error" in r for r in amb)

    def ci(k, n):
        lo, hi = wilson_ci(k, n)
        return f"{k}/{n} = {100 * k / n:.0f}% (95% CI {100 * lo:.0f}–{100 * hi:.0f}%)" if n else "n/a"

    summary = {"model": config.MODEL_IDS["reason"], "label": "SELF-ASSESSMENT", "unambiguous": len(unamb), "ambiguous": len(amb),
               "spec_returned": len(specs), "asked_on_unambiguous": asked_unamb, "errors": errors,
               "field_accuracy_strict": f_strict, "field_accuracy_op_lenient": f_len,
               "card_exact_strict": exact_strict, "card_exact_op_lenient": exact_len,
               "asked_on_ambiguous": asked_amb, "rows": rows,
               "ambiguous_rows": [{"id": r["id"], "hunch": r["hunch"],
                                   "asked": "questions" in (r.get("result") or {}),
                                   "questions": (r.get("result") or {}).get("questions")} for r in amb]}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    lines = [
        "# E4: translation accuracy (SELF-ASSESSMENT)",
        "",
        f"Model `{config.MODEL_IDS['reason']}` (live). Gold rule cards drafted before the run (`eval/translation_gold.json`);",
        "a teammate should review the gold set. Thresholds and parameters must match exactly (no tolerance).",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Fully specified hunches that got a rule card (no questions) | {ci(len(specs), len(unamb))} |",
        f"| Field-level exact match (strict ops) | {ci(*f_strict)} |",
        f"| Field-level exact match (`<` ≡ `<=`, `>` ≡ `>=`) | {ci(*f_len)} |",
        f"| Whole card exactly right (strict) | {ci(exact_strict, len(specs))} |",
        f"| Whole card exactly right (op-lenient) | {ci(exact_len, len(specs))} |",
        f"| Ambiguous hunches where the model asked instead of guessing | {ci(asked_amb, len(amb))} |",
        "",
        "## Misses (strict)",
        "",
    ]
    for r in rows:
        if r["outcome"] != "spec":
            lines.append(f"- {r['id']} {r['hunch']}: **{r['outcome']}**")
        elif not r["strict"]["exact"]:
            lines.append(f"- {r['id']} {r['hunch']}: {r['strict']['hits']}/{r['strict']['fields']} fields · got `{json.dumps(r['spec'])}`")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
