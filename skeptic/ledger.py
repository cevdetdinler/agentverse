"""Append-only, hash-chained audit log (JSONL).

entry = {"seq", "ts", "type", "payload", "prev_hash", "hash"}
hash  = sha256(prev_hash + canonical(entry without "hash"))

Editing, deleting or reordering any line breaks the chain, and verify_chain() reports the first bad seq.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from . import config

GENESIS = "0" * 64
ENTRY_TYPES = {
    "hunch_submitted", "llm_call", "spec_proposed", "spec_approved", "attack_planned", "attack_run",
    "trial_counted", "vault_precommit", "vault_result", "vault_blocked", "verdict",
    "number_guard_violation", "suggestion_shown", "limit_hit", "questions_asked", "ingest", "explanation",
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def _hash(prev_hash: str, body: dict) -> str:
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or config.LEDGER_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entries: list[dict] = self._read_file()

    # -------------------------------------------------------------- io
    def _read_file(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        out.append({"_corrupt": line})
        return out

    def append(self, type_: str, payload: dict) -> dict:
        if type_ not in ENTRY_TYPES:
            raise ValueError(f"unknown ledger entry type {type_!r}")
        with self._lock:
            last = self._entries[-1] if self._entries else None
            prev = last.get("hash", GENESIS) if last else GENESIS
            body = {
                "seq": (last.get("seq", len(self._entries) - 1) + 1) if last else 0,
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "type": type_,
                "payload": json.loads(_canonical(payload)),
                "prev_hash": prev,
            }
            entry = {**body, "hash": _hash(prev, body)}
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(_canonical(entry) + "\n")
                fh.flush()
            self._entries.append(entry)
            return entry

    # -------------------------------------------------------------- verification
    def verify_chain(self) -> dict:
        """Re-reads the file from disk so hand edits are caught."""
        entries = self._read_file()
        prev = GENESIS
        for i, e in enumerate(entries):
            if "_corrupt" in e:
                return {"ok": False, "entries": len(entries), "first_bad_seq": i, "reason": "unparseable line"}
            body = {k: e.get(k) for k in ("seq", "ts", "type", "payload", "prev_hash")}
            if e.get("seq") != i:
                return {"ok": False, "entries": len(entries), "first_bad_seq": i, "reason": "sequence gap or reorder"}
            if e.get("prev_hash") != prev:
                return {"ok": False, "entries": len(entries), "first_bad_seq": i, "reason": "prev_hash does not link"}
            if _hash(prev, body) != e.get("hash"):
                return {"ok": False, "entries": len(entries), "first_bad_seq": i, "reason": "entry content was altered"}
            prev = e["hash"]
        return {"ok": True, "entries": len(entries), "first_bad_seq": None, "head": prev}

    # -------------------------------------------------------------- queries
    def entries(self, type_: Optional[str] = None) -> list[dict]:
        return [e for e in self._entries if type_ is None or e.get("type") == type_]

    def find(self, type_: str, **match) -> list[dict]:
        return [e for e in self.entries(type_) if all(e["payload"].get(k) == v for k, v in match.items())]

    def last(self, type_: str, **match) -> Optional[dict]:
        found = self.find(type_, **match)
        return found[-1] if found else None

    def trials(self, idea_id: str) -> int:
        return len({e["payload"]["fingerprint"] for e in self.find("trial_counted", idea_id=idea_id)})

    def lineage_fingerprints(self, idea_id: str) -> list[str]:
        seen = []
        for e in self.find("trial_counted", idea_id=idea_id):
            fp = e["payload"]["fingerprint"]
            if fp not in seen:
                seen.append(fp)
        return seen

    def tail(self, n: int = 200) -> list[dict]:
        return self._entries[-n:]

    def iter_payloads(self, types: Iterable[str]) -> Iterable[dict]:
        types = set(types)
        for e in self._entries:
            if e.get("type") in types:
                yield e
