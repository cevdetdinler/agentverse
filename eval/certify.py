"""Freeze a rule card as results/certified/<fingerprint>.json (the file adapter.py runs)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skeptic.spec import RuleCard  # noqa: E402

CERT_DIR = ROOT / "results" / "certified"


def freeze(card: RuleCard) -> Path:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    out = CERT_DIR / f"{card.fingerprint}.json"
    out.write_text(json.dumps(card.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    args = ap.parse_args(argv)
    card = RuleCard.model_validate_json(args.spec.read_text(encoding="utf-8"))
    print(freeze(card).relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
