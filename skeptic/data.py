"""Practice data loader. Reads `inputs.jsonl` files only, never an answer key.

The holdout ("vault") is deliberately NOT reachable from here: only skeptic/vault.py knows where it
lives, and tests/test_vault_isolation.py enforces that by scanning the codebase.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import config

PRACTICE_INPUTS = config.DATA_DIR / "practice" / "inputs.jsonl"


@dataclass(frozen=True)
class PricePath:
    case_id: str
    prices: tuple[int, ...]
    initial_cash: int
    fee: int
    bps: int

    def with_costs(self, fee_mult: int = 1, bps_mult: int = 1) -> "PricePath":
        return PricePath(self.case_id, self.prices, self.initial_cash, self.fee * fee_mult, self.bps * bps_mult)


def parse_rows(lines) -> list[PricePath]:
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("task") != "markets":
            continue
        inp = row["input"]
        prices = tuple(int(p) for p in inp["prices_pence"])
        if len(prices) < 2 or any(p <= 0 for p in prices):
            raise ValueError(f"bad price path in case {row.get('case_id')}")
        out.append(
            PricePath(
                case_id=str(row["case_id"]),
                prices=prices,
                initial_cash=int(inp["initial_cash_pence"]),
                fee=int(inp["fee_pence"]),
                bps=int(inp["slippage_bps"]),
            )
        )
    return out


def load_inputs_file(path: Path) -> list[PricePath]:
    path = Path(path)
    if path.name != "inputs.jsonl":
        raise ValueError("only inputs.jsonl files may be loaded")
    if "vault" in {part.lower() for part in path.resolve().parts}:
        raise PermissionError("the vault is only readable through skeptic.vault")
    with path.open(encoding="utf-8") as fh:
        return parse_rows(fh)


@lru_cache(maxsize=1)
def load_practice() -> tuple[PricePath, ...]:
    if not PRACTICE_INPUTS.exists():
        raise FileNotFoundError(
            f"Practice data missing at {PRACTICE_INPUTS}. Fetch it first: see docs/COMMANDS.md"
        )
    return tuple(load_inputs_file(PRACTICE_INPUTS))
