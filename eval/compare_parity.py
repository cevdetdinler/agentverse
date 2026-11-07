"""E1 engine parity: compare the official runner's per-case final cash with our engine.

    python eval/compare_parity.py <runner case-results.jsonl> <dataset inputs.jsonl> --spec <frozen spec.json>

Reads the runner's output file and the dataset's inputs file only (no answer key, no kit import).
Exit code 0 only if every case is identical to the penny.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skeptic.data import parse_rows  # noqa: E402
from skeptic.engine import buy_and_hold_final, simulate  # noqa: E402
from skeptic.stats import aggregate  # noqa: E402
from skeptic.spec import RuleCard, compute_positions  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runner_results", type=Path)
    ap.add_argument("inputs", type=Path)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--runner-summary", type=Path, default=None, help="optional runner summary.json to compare aggregate stats")
    ap.add_argument("--out", type=Path, default=None, help="optional JSON summary path")
    args = ap.parse_args(argv)

    card = RuleCard.model_validate_json(args.spec.read_text(encoding="utf-8"))
    with args.inputs.open(encoding="utf-8") as fh:
        paths = {p.case_id: p for p in parse_rows(fh)}
    compared, mismatches, rows = 0, [], []
    with args.runner_results.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("case_id") not in paths or "final_cash_pence" not in (row.get("output") or {}):
                continue
            p = paths[row["case_id"]]
            ours = simulate(p.prices, compute_positions(card, p.prices), p.initial_cash, p.fee, p.bps)
            theirs = row["output"]
            compared += 1
            rows.append({"final_cash": ours.final_cash, "initial_cash": p.initial_cash,
                         "bh_final": buy_and_hold_final(p.prices, p.initial_cash, p.fee, p.bps),
                         "max_drawdown_bps": ours.max_drawdown_bps, "trades": ours.trades})
            if ours.final_cash != theirs["final_cash_pence"] or ours.max_drawdown_bps != theirs["max_drawdown_bps"]:
                mismatches.append({"case_id": p.case_id, "ours": ours.final_cash, "runner": theirs["final_cash_pence"],
                                   "ours_dd": ours.max_drawdown_bps, "runner_dd": theirs["max_drawdown_bps"]})
    summary = {"spec_fingerprint": card.fingerprint, "cases_compared": compared,
               "identical": compared - len(mismatches), "mismatches": mismatches[:20],
               "checked_fields": ["final_cash_pence", "max_drawdown_bps"]}
    stats_ok = True
    if args.runner_summary and rows:
        theirs = _find_market_stats(json.loads(args.runner_summary.read_text(encoding="utf-8")))
        ours_agg = aggregate(rows)
        pairs = {
            "wins_vs_buy_and_hold": ours_agg["wins"],
            "losses_vs_buy_and_hold": ours_agg["losses"],
            "ties": ours_agg["ties"],
            "median_excess_vs_buy_and_hold_bps_of_capital": ours_agg["median_excess_bps"],
            "mean_max_drawdown_bps": ours_agg["mean_max_drawdown_bps"],
            "sign_test_p_value": ours_agg["sign_p"],
        }
        diffs = {k: {"ours": v, "runner": theirs.get(k)} for k, v in pairs.items() if theirs.get(k) != v}
        stats_ok = not diffs
        summary["aggregate_stats_identical"] = stats_ok
        summary["aggregate_stats"] = pairs
        summary["aggregate_diffs"] = diffs
    print(json.dumps(summary, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if compared and not mismatches and stats_ok else 1


def _find_market_stats(obj):
    """Locate the dict holding the runner's market statistics, wherever it sits in summary.json."""
    if isinstance(obj, dict):
        if "wins_vs_buy_and_hold" in obj:
            return obj
        for v in obj.values():
            found = _find_market_stats(v)
            if found:
                return found
    return {}


if __name__ == "__main__":
    sys.exit(main())
