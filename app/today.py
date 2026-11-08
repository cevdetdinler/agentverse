"""Ideas from today's real markets, for the empty hunch box.

Reads the public 24-hour summary for a few large coins from Binance's free market-data service (no key,
no account) and turns today's actual moves into testable trading ideas, in plain words, with plain code
(no model call). This is ONLY suggestion text for the person typing: it is never used by a backtest, an
attack, the vault or adapter.py, and it fetches no price history (see docs/DECISIONS.md D8).
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable, Optional

COINS = {"BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "SOLUSDT": "Solana", "XRPUSDT": "XRP",
         "DOGEUSDT": "Dogecoin", "BNBUSDT": "BNB"}
TICKER_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
CACHE_SECONDS = 300
MAX_IDEAS = 6

_cache: dict = {"at": 0.0, "data": None}
_lock = threading.Lock()


def _http_get(url: str, timeout: float = 2.5) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Skeptic/1.0 (hackathon demo)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        return resp.read()


def fetch_tickers(getter: Callable[[str], bytes] = _http_get) -> list[dict]:
    symbols = json.dumps(list(COINS), separators=(",", ":"))
    url = f"{TICKER_URL}?{urllib.parse.urlencode({'symbols': symbols})}"
    rows = json.loads(getter(url).decode("utf-8"))
    return [r for r in rows if r.get("symbol") in COINS]


def _num(x) -> Optional[float]:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _price(x: float) -> str:
    return f"${x:,.0f}" if x >= 100 else f"${x:,.2f}" if x >= 1 else f"${x:,.4f}"


def _candidates(coin: str, change: float, last: float, high: float, low: float) -> list[dict]:
    """Ideas for one coin, most fitting first. Every hunch is expressible as Skeptic rules."""
    size = abs(change)
    step = max(2, int(size))  # a round threshold at or just below today's move
    where = (last - low) / (high - low) if high > low else 0.5
    below_high = (1 - last / high) * 100
    out = []
    if change <= -2:
        out.append(("dip", size, f"down {size:.1f}% in the last 24 hours",
                    f"Buy {coin} after it falls {step}% or more over 24 hours, and sell 24 hours later"))
    elif change >= 2:
        out.append(("rally", size, f"up {size:.1f}% in the last 24 hours",
                    f"Buy {coin} after it rises {step}% or more over 24 hours, and hold for 24 hours"))
    if where >= 0.9 and high > low:
        out.append(("near_high", 1.5 + size / 10, "trading near its 24-hour high",
                    f"Buy {coin} when it breaks above its 24-hour high, hold for 12 hours with a 3% stop-loss"))
    elif where <= 0.1 and below_high >= 1.5:
        d = max(2, int(below_high))
        out.append(("near_low", 1.5 + below_high / 10, f"near its 24-hour low, {below_high:.1f}% below today’s high",
                    f"Buy {coin} when it is {d}% or more below its 24-hour high, and sell after 48 hours or at +5%"))
    if size < 1:
        out.append(("calm", 1 - size, f"barely moved today ({change:+.1f}%)",
                    f"Buy {coin} when the last 24 hours have been unusually calm (hourly moves under 0.5%), and hold for 24 hours"))
    # what-if ideas that fit any day: they ask "what would I do if it moved from here?"
    out.append(("what_if_dip", 0.5, f"{change:+.1f}% today",
                f"Buy {coin} if it drops 3% or more within 24 hours, and sell 24 hours later"))
    out.append(("rsi", 0.4, f"{change:+.1f}% today",
                f"Buy {coin} when the 14-hour RSI falls below 30, and sell when it gets back above 50"))
    out.append(("trend", 0.3, f"{change:+.1f}% today",
                f"Hold {coin} only while its price is above its 50-hour average"))
    return [{"kind": k, "score": s, "fact": f"{coin} {_price(last)}, {fact}", "hunch": h, "coin": coin}
            for k, s, fact, h in out]


def ideas_from_tickers(rows: list[dict]) -> list[dict]:
    """Pure function: 24h ticker rows -> varied, plain-language, testable ideas (biggest moves first).

    Variety rules: at most 2 ideas per coin and at most 2 of the same kind, so a quiet day doesn't produce six
    copies of the same suggestion."""
    per_coin = []
    for r in rows:
        coin = COINS.get(r.get("symbol"))
        change, last, high, low = (_num(r.get(k)) for k in ("priceChangePercent", "lastPrice", "highPrice", "lowPrice"))
        if not coin or None in (change, last, high, low) or high <= 0 or last <= 0 or high < low:
            continue
        per_coin.append((abs(change), _candidates(coin, change, last, high, low)))
    per_coin.sort(key=lambda t: -t[0])
    out, seen = [], set()
    kinds: dict[str, int] = {}
    coins: dict[str, int] = {}
    for _ in range(3):  # round-robin over coins: best remaining idea per coin each round
        for _size, cands in per_coin:
            for c in sorted(cands, key=lambda c: -c["score"]):
                if c["hunch"] in seen or kinds.get(c["kind"], 0) >= 2 or coins.get(c["coin"], 0) >= 2:
                    continue
                seen.add(c["hunch"])
                kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
                coins[c["coin"]] = coins.get(c["coin"], 0) + 1
                out.append({k: c[k] for k in ("coin", "kind", "fact", "hunch")})
                break
            if len(out) >= MAX_IDEAS:
                return out
    return out


def today(getter: Callable[[str], bytes] = _http_get, now: Optional[float] = None) -> dict:
    """Cached for 5 minutes. Never raises: if the live service is unreachable, returns no ideas."""
    now = time.time() if now is None else now
    with _lock:
        if _cache["data"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]
    try:
        data = {"ok": True, "source": "Binance public 24-hour summary (live)", "fetched_at": int(now),
                "ideas": ideas_from_tickers(fetch_tickers(getter))}
    except Exception as exc:  # offline at the venue, rate-limited, etc.: the box still works without it
        data = {"ok": False, "source": "unavailable", "error": type(exc).__name__, "ideas": [], "fetched_at": int(now)}
    with _lock:
        _cache.update({"at": now if data["ok"] else now - CACHE_SECONDS + 30, "data": data})  # retry in 30 s if it failed
    return data
