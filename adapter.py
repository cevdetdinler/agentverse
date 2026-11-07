"""JSONL adapter: runs a frozen, human-approved rule card through the walk-forward runner protocol.

    <venv python> adapter.py --spec results/certified/<fingerprint>.json

No LLM calls, no file reads beyond the spec: deterministic, fast and free. Each request carries only
the observed price history; we recompute the target position on that prefix and convert it to an
action with the same rule as skeptic.engine.simulate. stdout carries response lines only; logs go to
stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skeptic.spec import RuleCard, compute_positions, positions_to_action


def log(*parts) -> None:
    print("[skeptic-adapter]", *parts, file=sys.stderr, flush=True)


def load_frozen_spec(path: Path) -> RuleCard:
    card = RuleCard.model_validate_json(Path(path).read_text(encoding="utf-8"))
    stem = Path(path).stem
    fp = card.fingerprint
    if not (len(stem) >= 12 and fp.startswith(stem)):
        raise SystemExit(f"spec fingerprint {fp[:12]} does not match file name {stem!r}; refusing to run")
    return card


def decide(card: RuleCard, request: dict) -> dict:
    if request.get("task") != "market_step":
        return {"error": "unsupported_task"}
    inp = request["input"]
    prices = [int(h["price_pence"]) for h in inp["history"]]
    want_in = compute_positions(card, prices)[-1]
    return {"action": positions_to_action(want_in, int(inp["shares"]))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", type=Path, required=True)
    args = ap.parse_args(argv)
    card = load_frozen_spec(args.spec)
    log("loaded spec", card.fingerprint[:12], "-", card.name)
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request: dict = {}
        try:
            request = json.loads(line)
            output = decide(card, request)
        except Exception as exc:  # never crash mid-run; report it on stderr
            log("error:", repr(exc))
            output = {"error": "adapter_error"}
        if not isinstance(request, dict):
            request = {}
        out.write(json.dumps({"request_id": request.get("request_id"), "output": output}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
