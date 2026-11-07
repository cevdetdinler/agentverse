"""Number guard: every number in the model's explanation must come from the tool outputs.

We collect every number in the results bundle (numeric fields, plus numbers inside the
code-generated summary strings and rule text), then check each number in the model's text against
them, allowing only formatting differences:
  - rounding to the precision shown in the text (e.g. 0.27263 -> "0.27" or "0.273")
  - unit conversions that preserve the value: bps <-> % (59 bps = 0.59%), fraction <-> % (0.05 = 5%),
    pence -> pounds (12345 p = £123.45)
Small structural counts 0..10 ("3 groups", "2 of 6 checks") are always allowed.

Known limitation: matching is by value, not by meaning. A number that coincides with an unrelated tool
output at the shown precision passes (e.g. "12%" when some p-value is 0.1189). The guard stops invented
numbers; it does not prove each number is attached to the right label. The cited attack IDs and the
trace drawer let a human check that.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

_CITATION = re.compile(r"\[(?:A|D)\d+\]")
_NUM = re.compile(r"(?<![\w.])([-−–]?)\s?(£)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(%|bps|bp|p\b)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(\"'])")
ALWAYS_OK = set(range(0, 11))


@dataclass
class GuardResult:
    ok: bool
    text: str
    violations: list[str] = field(default_factory=list)
    removed_sentences: list[str] = field(default_factory=list)


def _walk_numbers(obj, out: set[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(obj):
            out.add(float(obj))
        return
    if isinstance(obj, str):
        for tok in extract(obj):
            out.add(tok["value"])
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, out)


def allowed_numbers(bundle) -> set[float]:
    vals: set[float] = set()
    _walk_numbers(bundle, vals)
    return vals


def extract(text: str) -> list[dict]:
    text = _CITATION.sub(" ", text)
    out = []
    for m in _NUM.finditer(text):
        sign, pound, whole, frac, unit = m.groups()
        # skip things like "A1", "x2" glued to letters (handled by the lookbehind) and years in ids
        raw = whole.replace(",", "") + (frac or "")
        value = float(raw)
        if sign:
            value = -value
        decimals = len(frac) - 1 if frac else 0
        out.append({"raw": m.group(0).strip(), "value": value, "decimals": decimals,
                    "unit": "£" if pound else (unit or ""), "span": m.span()})
    return out


_DOWN_WORDS = re.compile(r"(fell|fall|falls|drop|drops|dropped|down|lost|lose|loses|loss|below|minus|negative|declin\w*|shr[iu]nk\w*|lower)\W+(?:\w+\W+){0,3}$", re.I)


def _matches(tok: dict, allowed: set[float], context: str = "") -> bool:
    """True if the number equals an allowed value at the shown precision (sign-aware)."""
    x, d = tok["value"], tok["decimals"]
    if d == 0 and abs(x) in ALWAYS_OK:
        return True
    tol = 0.5 * 10 ** (-d) + 1e-9
    # A positive number may stand for a negative value only when the words say so ("fell by 2.3%").
    magnitude_ok = x > 0 and bool(_DOWN_WORDS.search(context))
    for v in allowed:
        for cand in (v, v / 100.0, v * 100.0):
            if abs(cand - x) <= tol:
                return True
            if magnitude_ok and abs(-cand - x) <= tol:
                return True
    return False


def _bad_tokens(text: str, allowed: set[float]) -> list[str]:
    clean = _CITATION.sub(" ", text)
    bad = []
    for t in extract(text):
        start = t["span"][0]
        if not _matches(t, allowed, clean[max(0, start - 40):start]):
            bad.append(t["raw"])
    return bad


def check(text: str, bundle) -> list[str]:
    return _bad_tokens(text, allowed_numbers(bundle))


def guard(text: str, bundle) -> GuardResult:
    bad = check(text, bundle)
    return GuardResult(ok=not bad, text=text, violations=bad)


def strip_violations(text: str, bundle) -> GuardResult:
    allowed = allowed_numbers(bundle)
    kept, removed, bad_all = [], [], []
    for sentence in _SENTENCE.split(text.strip()):
        bad = _bad_tokens(sentence, allowed)
        if bad:
            removed.append(sentence)
            bad_all += bad
        else:
            kept.append(sentence)
    return GuardResult(ok=not bad_all, text=" ".join(kept), violations=bad_all, removed_sentences=removed)
