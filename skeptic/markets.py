"""The two markets the app can test on. Each has its own ledger, practice data and vault."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from . import config
from .agent import Agent
from .ledger import Ledger
from .pipeline import Skeptic
from .synthetic import synthetic_paths

MARKETS = {
    "real": {"label": "Real market", "source": "Binance Vision price windows (anonymised, half return-inverted) via the kit's fetch"},
    "synthetic": {"label": "Synthetic market", "source": "Our own random-walk generator (skeptic/synthetic.py) with a planted "
                  "dip-then-rebound pattern; seeds in skeptic/config.py SYNTHETIC_MARKET"},
}


@dataclass
class Market:
    name: str
    ledger: Ledger
    skeptic: Skeptic
    agent: Agent
    info: dict = field(default_factory=dict)


@lru_cache(maxsize=1)
def _synthetic_data():
    m = config.SYNTHETIC_MARKET
    practice = synthetic_paths(m["practice_seed"], m["practice_paths"], effect=m["effect"], prefix="sp")
    vault = synthetic_paths(m["vault_seed"], m["vault_paths"], effect=m["effect"], prefix="sv")
    return tuple(practice), tuple(vault)


def build(name: str, ledger_path=None) -> Market:
    if name == "real":
        ledger = Ledger(ledger_path or config.LEDGER_PATH)
        sk = Skeptic(ledger)
    elif name == "synthetic":
        practice, vault = _synthetic_data()
        ledger = Ledger(ledger_path or config.SYNTHETIC_LEDGER_PATH)
        sk = Skeptic(ledger, practice_paths=practice, vault_inputs=vault)
    else:
        raise KeyError(f"unknown market {name!r}")
    return Market(name, ledger, sk, Agent(ledger), MARKETS[name])
