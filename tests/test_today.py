"""'Today's markets' suggestions: display-only, varied, and never in the way when offline."""
import json
from pathlib import Path

import pytest

from app import today as T

ROOT = Path(__file__).resolve().parent.parent


def row(symbol, change, last, high, low):
    return {"symbol": symbol, "priceChangePercent": str(change), "lastPrice": str(last),
            "highPrice": str(high), "lowPrice": str(low)}


def test_moves_become_matching_ideas():
    ideas = T.ideas_from_tickers([
        row("BTCUSDT", -4.3, 95000, 100000, 94800),   # big drop, near the low
        row("SOLUSDT", 6.1, 180, 181, 168),           # big rise, near the high
        row("ETHUSDT", 0.2, 3000, 3020, 2990),        # calm
    ])
    text = " | ".join(i["hunch"] for i in ideas)
    assert "Bitcoin bounces back after a 4% drop in a day" in text
    assert "Solana keeps going up after a 6% jump in a day" in text
    assert any(i["kind"] == "calm" and i["coin"] == "Ethereum" for i in ideas)
    btc = next(i for i in ideas if i["coin"] == "Bitcoin")
    assert btc["fact"].startswith("Bitcoin $95,000") and "down 4.3%" in btc["fact"]
    assert ideas[0]["coin"] in ("Solana", "Bitcoin")  # real moves first


def test_quiet_day_is_still_varied():
    rows = [row(s, 0.1 * i, 100 + i, 101 + i, 99 + i) for i, s in enumerate(T.COINS)]
    ideas = T.ideas_from_tickers(rows)
    kinds = [i["kind"] for i in ideas]
    assert len(ideas) == T.MAX_IDEAS
    assert all(kinds.count(k) <= 2 for k in kinds)
    assert all(sum(1 for i in ideas if i["coin"] == c) <= 2 for c in {i["coin"] for i in ideas})
    assert len({i["hunch"] for i in ideas}) == len(ideas)


def test_ideas_sound_like_people_not_rules():
    rows = [row(sym, 0.1 * i, 100 + i, 101 + i, 99 + i) for i, sym in enumerate(T.COINS)]
    rows.append(row("DOGEUSDT", -1.4, 0.07, 0.072, 0.069))
    ideas = T.ideas_from_tickers(rows)
    for i in ideas:
        h = i["hunch"].lower()
        words = h.split()
        assert len(words) <= 14, h  # short, like a post
        assert "bar" not in words and "bars" not in words, h
        assert "sell" not in h and "stop-loss" not in h and "hold for" not in h, h  # exits are asked for later
    coins = [i["coin"] for i in ideas]
    assert coins[0] == "Bitcoin" and "Dogecoin" not in coins  # quiet day: familiar coins first


def test_a_real_move_beats_coin_priority():
    rows = [row("BTCUSDT", 0.1, 100, 101, 99), row("DOGEUSDT", -9.0, 0.07, 0.08, 0.069)]
    assert T.ideas_from_tickers(rows)[0]["coin"] == "Dogecoin"


def test_bad_rows_are_skipped():
    ideas = T.ideas_from_tickers([
        row("BTCUSDT", "nan", 1, 2, 1), {"symbol": "BTCUSDT"}, row("FAKEUSDT", -9, 1, 2, 1),
        row("ETHUSDT", -3, 0, 0, 0),
    ])
    assert ideas == []


def test_offline_falls_back_silently(monkeypatch):
    monkeypatch.setattr(T, "_cache", {"at": 0.0, "data": None})

    def boom(url):
        raise TimeoutError("venue wifi")

    out = T.today(getter=boom, now=1000.0)
    assert out["ok"] is False and out["ideas"] == []


def test_cache_avoids_refetching(monkeypatch):
    monkeypatch.setattr(T, "_cache", {"at": 0.0, "data": None})
    calls = []

    def fake(url):
        calls.append(url)
        assert "ticker/24hr" in url and "type=MINI" in url  # one request for every coin
        return json.dumps([mini("BTCUSDT", 96000, 90000, 96500, 89900, now_ms=1000.0 * 1000)]).encode()

    a = T.today(getter=fake, now=1000.0)
    b = T.today(getter=fake, now=1000.0 + 60)
    assert a["ok"] and a == b and len(calls) == 1
    T.today(getter=fake, now=1000.0 + T.CACHE_SECONDS + 1)
    assert len(calls) == 2


# ---------------------------------------------------------------- every coin trading today
NOW_MS = 1_800_000_000_000


def mini(symbol, open_, last, high, low, vol=5_000_000, count=1000, now_ms=NOW_MS, close_age_ms=60_000):
    """A row in the compact all-coins format (no priceChangePercent: change is computed from openPrice)."""
    return {"symbol": symbol, "openPrice": str(open_), "lastPrice": str(last), "highPrice": str(high),
            "lowPrice": str(low), "quoteVolume": str(vol), "count": count, "closeTime": now_ms - close_age_ms}


def test_only_real_coins_trading_today_are_kept():
    rows = [
        mini("BTCUSDT", 100, 96, 101, 95),
        mini("PEPEUSDT", 0.00001, 0.0000105, 0.0000106, 0.0000098),
        mini("USDCUSDT", 1, 1, 1.001, 0.999),                    # stablecoin
        mini("BTCUPUSDT", 10, 11, 12, 9),                        # leveraged token
        mini("WBTCUSDT", 100, 96, 101, 95),                      # wrapped
        mini("COINBUSDT", 130, 134, 135, 129),                   # tokenized share, not crypto
        mini("DEADUSDT", 1, 1, 1, 1, close_age_ms=5 * 86_400_000),  # delisted: no trade for days
        mini("TINYUSDT", 1, 1.1, 1.2, 0.9, vol=500),             # barely traded
        mini("ETHBTC", 0.03, 0.031, 0.032, 0.029),               # not priced in dollars
    ]
    assert [r["symbol"] for r in T.tradable(rows, NOW_MS)] == ["BTCUSDT", "PEPEUSDT"]


def test_three_ideas_per_coin_with_friendly_names_and_grammar():
    rows = [mini("BTCUSDT", 100, 96, 101, 95), mini("PEPEUSDT", 1.0, 1.01, 1.08, 1.0),
            mini("SUIUSDT", 2.0, 1.83, 2.02, 1.82)]
    ideas = T.all_ideas_from_tickers(rows, NOW_MS)
    by = {}
    for i in ideas:
        by.setdefault(i["symbol"], []).append(i)
    assert {k: len(v) for k, v in by.items()} == {"BTC": 3, "PEPE": 3, "SUI": 3}
    assert all(i["hunch"].startswith("Bitcoin ") for i in by["BTC"])  # friendly name for big coins
    assert by["BTC"][0]["hunch"] == "Bitcoin bounces back after a 4% drop in a day"  # today's real move first
    assert by["SUI"][0]["hunch"] == "Sui bounces back after an 8% drop in a day"  # 'an 8%', not 'a 8%'
    assert len({i["hunch"] for i in ideas}) == len(ideas)
    for i in ideas:
        assert "bars" not in i["hunch"] and "sell" not in i["hunch"].lower()


def test_list_is_capped(monkeypatch):
    monkeypatch.setattr(T, "MAX_ALL", 7)
    rows = [mini(f"C{n:03d}XUSDT", 1, 1.01, 1.02, 0.99) for n in range(10)]
    assert len(T.all_ideas_from_tickers(rows, NOW_MS)) == 7


def test_full_list_failure_falls_back_to_six_coins(monkeypatch):
    monkeypatch.setattr(T, "_cache", {"at": 0.0, "data": None})

    def fake(url):
        if "type=MINI" in url:
            raise TimeoutError("1 MB over venue wifi")
        return json.dumps([row("BTCUSDT", -5, 90000, 96000, 89900)]).encode()

    out = T.today(getter=fake, now=1000.0)
    assert out["ok"] and out["ideas"] and out["all"] == []


def test_live_data_never_reaches_the_maths():
    """Suggestion text only: nothing that backtests, attacks, opens the vault or runs in the judges' adapter
    may import the live-market module."""
    for path in [ROOT / "adapter.py", *sorted((ROOT / "skeptic").glob("*.py")), *sorted((ROOT / "eval").glob("*.py"))]:
        text = path.read_text(encoding="utf-8")
        for banned in ("app.today", "import today", "api/v3", "data-api.", "urlopen("):
            assert banned not in text, (path, banned)
