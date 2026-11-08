"""Ideas from today's real markets, for the hunch box.

Reads Binance's free public 24-hour market summary (no key, no account): last price, open, high, low and
volume for every coin traded against the dollar. Plain code (no model call) turns today's actual moves into
short trading ideas, phrased the way people say them:

  featured  5 ideas from big, familiar coins, shown when the box is empty
  all       ~1,000 ideas, three for each of the ~300-350 coins actively trading today, searchable as you type

This is ONLY suggestion text for the person typing: it is never used by a backtest, an attack, the vault or
adapter.py, and it fetches no price history (see docs/DECISIONS.md D8). If the service can't be reached, the
box falls back to the built-in examples.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable, Optional

TICKER_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
ALL_URL = f"{TICKER_URL}?type=MINI"  # every pair, compact fields (~1 MB)
COINS = {"BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "SOLUSDT": "Solana", "XRPUSDT": "XRP",
         "DOGEUSDT": "Dogecoin", "BNBUSDT": "BNB"}
# friendlier names for well-known coins; everything else uses its ticker (PEPE, SUI, ...)
NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "BNB": "BNB", "DOGE": "Dogecoin",
         "ADA": "Cardano", "TRX": "Tron", "LINK": "Chainlink", "AVAX": "Avalanche", "DOT": "Polkadot",
         "LTC": "Litecoin", "SHIB": "Shiba Inu", "TON": "Toncoin", "ATOM": "Cosmos", "UNI": "Uniswap",
         "NEAR": "NEAR", "APT": "Aptos", "ARB": "Arbitrum", "OP": "Optimism", "FIL": "Filecoin",
         "WLD": "Worldcoin", "INJ": "Injective", "SUI": "Sui", "BCH": "Bitcoin Cash", "ETC": "Ethereum Classic",
         "XLM": "Stellar", "HBAR": "Hedera", "ICP": "Internet Computer", "AAVE": "Aave"}
# not trading ideas: stablecoins, gold tokens, and leveraged tokens
NOT_COINS = {"USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDP", "EUR", "AEUR", "EURI", "PAX", "UST", "USDE", "XUSD",
             "USD1", "BFUSD", "RLUSD", "PYUSD", "GBP", "TRY", "BRL", "XAUT", "PAXG", "WBTC", "WETH", "WBETH", "BETH"}
LEVERAGED = re.compile(r"(UP|DOWN|BULL|BEAR)$")
MIN_QUOTE_VOLUME = 100_000     # dollars traded in the last 24 hours (~350 coins on a normal day)
MAX_STALE_MS = 2 * 3600 * 1000  # a pair with no trade for 2 hours is not "trading today"
CACHE_SECONDS = 300
MAX_IDEAS = 5
MAX_ALL = 1000

_cache: dict = {"at": 0.0, "data": None}
_lock = threading.Lock()


def _http_get(url: str, timeout: float = 5.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Skeptic/1.0 (hackathon demo)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        return resp.read()


def fetch_tickers(getter: Callable[[str], bytes] = _http_get) -> list[dict]:
    """The six featured coins only (small request: the fallback when the full list can't be fetched)."""
    symbols = json.dumps(list(COINS), separators=(",", ":"))
    url = f"{TICKER_URL}?{urllib.parse.urlencode({'symbols': symbols})}"
    rows = json.loads(getter(url).decode("utf-8"))
    return [r for r in rows if r.get("symbol") in COINS]


def fetch_all_tickers(getter: Callable[[str], bytes] = _http_get) -> list[dict]:
    rows = json.loads(getter(ALL_URL).decode("utf-8"))
    if not isinstance(rows, list):
        raise ValueError("unexpected response")
    return rows


def _num(x) -> Optional[float]:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _change(r: dict) -> Optional[float]:
    """24-hour change in percent: given directly in the full summary, computed from open in the compact one."""
    c = _num(r.get("priceChangePercent"))
    if c is not None:
        return c
    last, open_ = _num(r.get("lastPrice")), _num(r.get("openPrice"))
    return (last / open_ - 1) * 100 if last and open_ else None


def _price(x: float) -> str:
    return f"${x:,.0f}" if x >= 100 else f"${x:,.2f}" if x >= 1 else f"${x:,.4f}" if x >= 0.0001 else f"${x:.8f}"


# Big, familiar coins first: on a quiet day the box should talk about Bitcoin and Ethereum, not Dogecoin.
PRIORITY = {"Bitcoin": 3.0, "Ethereum": 2.5, "Solana": 2.0, "XRP": 1.5, "BNB": 1.0, "Dogecoin": 0.5}


def _candidates(coin: str, change: float, last: float, high: float, low: float) -> list[dict]:
    """Ideas for one coin, most fitting first, phrased the way people actually say them.

    Short and casual on purpose ("Bitcoin bounces back after a 4% drop in a day"): the exact thresholds, holding
    time and exit are what Skeptic's clarifying questions are for. Every idea is still testable as rules."""
    size = abs(change)
    step = max(2, int(size))  # a round number at or just below today's move
    where = (last - low) / (high - low) if high > low else 0.5
    below_high = (1 - last / high) * 100
    out = []
    if change <= -2:
        out.append(("dip", size, f"down {size:.1f}% today", f"{coin} bounces back after {_a(step)} {step}% drop in a day"))
    elif change >= 2:
        out.append(("rally", size, f"up {size:.1f}% today", f"{coin} keeps going up after {_a(step)} {step}% jump in a day"))
    if where >= 0.9 and high > low:
        out.append(("near_high", 1.5 + size / 10, "near today’s high", f"{coin} keeps climbing when it breaks its daily high"))
    elif where <= 0.1 and below_high >= 1.5:
        d = max(2, int(below_high))
        out.append(("near_low", 1.5 + below_high / 10, f"{below_high:.1f}% below today’s high",
                    f"{coin} rebounds when it’s {d}% below its daily high"))
    if size < 1:
        out.append(("calm", 1 - size, f"barely moved today ({change:+.1f}%)", f"{coin} makes a big move after a really quiet day"))
    # ideas that fit any day
    out.append(("dip_any", 0.5, f"{change:+.1f}% today", f"{coin} bounces back after any 3% dip"))
    out.append(("oversold", 0.4, f"{change:+.1f}% today", f"{coin} rebounds when it’s oversold"))
    out.append(("trend", 0.3, f"{change:+.1f}% today", f"{coin} keeps rising while it stays above its recent average"))
    return [{"kind": k, "score": sc, "fact": f"{coin} {_price(last)} · {fact}", "hunch": h, "coin": coin}
            for k, sc, fact, h in out]


def _a(n: int) -> str:
    """'a' or 'an' before a spoken number: an 8%, an 11%, an 18%, a 5%."""
    return "an" if str(n).startswith("8") or n in (11, 18) else "a"


def _evergreen(coin: str, swing: float) -> list[tuple[str, str]]:
    """Any-day ideas, sized to how much the coin actually swings (today's high-low range)."""
    k = min(15, max(3, int(round(swing))))  # a dip about the size of a normal day for this coin
    return [
        ("dip_any", f"{coin} bounces back after any {k}% dip"),
        ("oversold", f"{coin} rebounds when it’s oversold"),
        ("trend", f"{coin} keeps rising while it stays above its recent average"),
        ("red_days", f"{coin} pumps after a few red days in a row"),
        ("quiet_week", f"{coin} breaks out after a quiet week"),
        ("weekly_high", f"{coin} keeps running after it hits a new weekly high"),
        ("crash", f"{coin} recovers after {_a(min(40, 2 * k))} {min(40, 2 * k)}% crash"),
        ("cross", f"{coin} goes up when its short average crosses above its long average"),
    ]


def ideas_from_tickers(rows: list[dict]) -> list[dict]:
    """Featured ideas from the six big coins: short, varied, everyday language.

    Order: a coin with a real move today (2%+) first, then familiar coins (Bitcoin, Ethereum, ...).
    Variety: one idea per coin per round, at most 2 per coin and at most 2 of the same kind."""
    per_coin = []
    for r in rows:
        coin = COINS.get(r.get("symbol"))
        change = _change(r)
        last, high, low = (_num(r.get(k)) for k in ("lastPrice", "highPrice", "lowPrice"))
        if not coin or None in (change, last, high, low) or high <= 0 or last <= 0 or high < low:
            continue
        size = abs(change)
        rank = (size if size >= 2 else 0.0) * 2 + PRIORITY.get(coin, 0.0)
        per_coin.append((rank, _candidates(coin, change, last, high, low)))
    per_coin.sort(key=lambda t: -t[0])
    out, seen = [], set()
    kinds: dict[str, int] = {}
    coins: dict[str, int] = {}
    for _ in range(2):  # round-robin over coins: best remaining idea per coin each round
        for _rank, cands in per_coin:
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


def tradable(rows: list[dict], now_ms: float) -> list[dict]:
    """Coins actively trading against the dollar today, biggest volume first."""
    out = []
    for r in rows:
        sym = str(r.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if not base or base in NOT_COINS or "USD" in base or LEVERAGED.search(base):
            continue
        if len(base) >= 4 and base.endswith("B") and (_num(r.get("lastPrice")) or 0) >= 5:
            continue  # tokenized shares (COINB, SPCXB, ...) are not crypto; real coins like BNB are 3 letters
        last, high, low, vol = (_num(r.get(k)) for k in ("lastPrice", "highPrice", "lowPrice", "quoteVolume"))
        close_t, count = _num(r.get("closeTime")), _num(r.get("count"))
        if None in (last, high, low, vol) or last <= 0 or low <= 0 or high < low or vol < MIN_QUOTE_VOLUME:
            continue
        if close_t is not None and now_ms - close_t > MAX_STALE_MS:
            continue  # delisted or halted pair
        if count is not None and count <= 0:
            continue
        out.append(r)
    out.sort(key=lambda r: -float(r["quoteVolume"]))
    return out


def all_ideas_from_tickers(rows: list[dict], now_ms: float) -> list[dict]:
    """Three ideas for every coin trading today: today's situation first (if any), then any-day ideas.

    The any-day ideas are picked per coin (a stable hash of ticker and date) so 400 coins don't all get the same
    three sentences."""
    out, seen = [], set()
    day = time.strftime("%Y-%m-%d", time.gmtime(now_ms / 1000))
    for r in tradable(rows, now_ms):
        base = r["symbol"][:-4]
        coin = NAMES.get(base, base)
        change = _change(r)
        last, high, low = (float(r[k]) for k in ("lastPrice", "highPrice", "lowPrice"))
        if change is None:
            continue
        fact_tail = f"{change:+.1f}% today"
        situational = [c for c in _candidates(coin, change, last, high, low)
                       if c["kind"] in ("dip", "rally", "near_high", "near_low", "calm")][:1]
        picks = [(c["kind"], c["hunch"], c["fact"]) for c in situational]
        pool = _evergreen(coin, (high / low - 1) * 100)
        start = int(hashlib.sha256(f"{base}:{day}".encode()).hexdigest(), 16) % len(pool)
        for i in range(len(pool)):
            if len(picks) >= 3:
                break
            kind, hunch = pool[(start + i) % len(pool)]
            picks.append((kind, hunch, f"{coin} {_price(last)} · {fact_tail}"))
        for kind, hunch, fact in picks:
            if hunch in seen:
                continue
            seen.add(hunch)
            out.append({"coin": coin, "symbol": base, "kind": kind, "fact": fact, "hunch": hunch})
            if len(out) >= MAX_ALL:
                return out
    return out


def today(getter: Callable[[str], bytes] = _http_get, now: Optional[float] = None) -> dict:
    """Cached for 5 minutes. Never raises: full list -> six featured coins -> nothing (the box uses examples)."""
    now = time.time() if now is None else now
    with _lock:
        if _cache["data"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]
    base = {"source": "Binance public 24-hour summary (live)", "fetched_at": int(now)}
    try:
        rows = fetch_all_tickers(getter)
        featured = ideas_from_tickers([r for r in rows if r.get("symbol") in COINS])
        everything = all_ideas_from_tickers(rows, now * 1000)
        data = {"ok": True, **base, "ideas": featured, "all": everything,
                "coins": len({i["symbol"] for i in everything})}
    except Exception:
        try:  # smaller request: the six featured coins only
            data = {"ok": True, **base, "ideas": ideas_from_tickers(fetch_tickers(getter)), "all": [], "coins": 0}
        except Exception as exc:  # offline at the venue, rate-limited, etc.: the box still works without it
            data = {"ok": False, "source": "unavailable", "error": type(exc).__name__, "ideas": [], "all": [],
                    "coins": 0, "fetched_at": int(now)}
    with _lock:
        _cache.update({"at": now if data["ok"] else now - CACHE_SECONDS + 30, "data": data})  # retry in 30 s if it failed
    return data
