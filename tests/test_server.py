"""HTTP-level tests of the full flow with a FakeLLM (unit tests only) and synthetic data."""
import json
import os

import pytest

from eval.synthetic import synthetic_paths
from tests.fakes import FakeLLM

STRONG = {"kind": "dip", "lookback": 12, "threshold": 0.03, "hold": 12, "drift": 0.006}
SPEC = {"name": "dip", "entry": {"all": [{"feature": "return", "lookback": 12, "op": "<=", "value": -0.03}]},
        "exit": {"hold_bars": 12}, "assumptions": ["close-to-close"]}
PLAN = {"diagnostics": [{"tool": "regime_split", "params": {"by": "path_trend"}, "alternative_explanation": "only in downtrends",
                         "supports_if": "one bucket", "refutes_if": "all buckets"}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEPTIC_LEDGER", str(tmp_path / "ledger.jsonl"))
    import importlib

    from skeptic import config
    importlib.reload(config)
    import app.server as server
    importlib.reload(server)
    from fastapi.testclient import TestClient

    vault_file = tmp_path / "inputs.jsonl"
    with vault_file.open("w", encoding="utf-8") as fh:
        for p in synthetic_paths(seed=99, count=100, effect=STRONG):
            fh.write(json.dumps({"case_id": p.case_id, "task": "markets", "input": {
                "prices_pence": list(p.prices), "dates": [], "initial_cash_pence": p.initial_cash,
                "fee_pence": p.fee, "slippage_bps": p.bps}}) + "\n")
    server.skeptic._paths = synthetic_paths(seed=98, count=120, effect=STRONG)
    server.skeptic._vault_inputs = vault_file
    fake = FakeLLM([])
    server.agent._client = fake
    yield TestClient(server.app), server, fake
    monkeypatch.delenv("SKEPTIC_LEDGER")
    importlib.reload(config)


def test_full_flow_and_live_vault_block(client):
    c, server, fake = client
    sid = "s_test01"
    q = {"mode": "questions", "questions": [{"id": "q1", "text": "How big?", "options": ["3% over 12 bars"]}]}
    fake.replies += [json.dumps(q), json.dumps({"mode": "spec", "spec": SPEC})]
    r = c.post("/api/hunch", json={"session_id": sid, "hunch": "buy the dip"}).json()
    assert r["questions"][0]["text"] == "How big?"
    r = c.post("/api/hunch", json={"session_id": sid, "answers": {"How big?": "3% over 12 bars"}}).json()
    assert fake.calls[1]["previous"] == "fake_1"
    a = c.post("/api/spec/approve", json={"session_id": sid, "spec": r["spec"]}).json()
    fp = a["fingerprint"]
    fake.replies += [json.dumps(PLAN)]
    att = c.post("/api/attack", json={"session_id": sid, "fingerprint": fp, "k": 50}).json()
    assert att["gate"]["status"] == "ELIGIBLE", att["gate"]["failing"]
    assert att["diagnostics"][0]["id"] == "D1"
    v = c.post("/api/vault/open", json={"session_id": sid, "fingerprint": fp}).json()
    assert v["verdict"]["label"] == "SURVIVED"
    fake.replies += ["The rule passed [A1]."]
    ex = c.post("/api/explain", json={"session_id": sid, "fingerprint": fp}).json()
    assert ex["label"] == "SURVIVED" and ex["verdict"]["stage"] == "final"

    # live control: tweak one parameter after the vault, approve, try the vault -> 409 + logged
    edited = json.loads(json.dumps(a["spec"]))
    edited["exit"]["hold_bars"] = 13
    b = c.post("/api/spec/approve", json={"session_id": sid, "spec": edited, "parent_fingerprint": fp}).json()
    assert b["contaminated"] and b["trials"] == 2
    blocked = c.post("/api/vault/open", json={"session_id": sid, "fingerprint": b["fingerprint"]})
    assert blocked.status_code == 409 and "already used its vault" in blocked.json()["error"]
    log = c.get("/api/ledger").json()
    assert any(e["type"] == "vault_blocked" for e in log["entries"])
    assert log["verify"]["ok"]
    tr = c.get(f"/api/trace?fingerprint={fp}&attack=A2").json()
    assert tr["steps"][3]["detail"] == "skeptic.attacks.a2_permutation"


def test_limits_return_clear_errors(client):
    c, server, fake = client
    r = c.post("/api/hunch", json={"session_id": "s_lim01", "hunch": "x" * 1001})
    assert r.status_code == 422 and "1000" in r.json()["error"]
    bad = dict(SPEC, entry={"all": [{"feature": "return", "lookback": 500, "op": "<=", "value": -0.03}]})
    r = c.post("/api/spec/approve", json={"session_id": "s_lim01", "spec": bad})
    assert r.status_code == 422
    r = c.post("/api/attack", json={"session_id": "s_lim01", "fingerprint": "0" * 64, "k": 5000})
    assert r.status_code in (404, 422)
    kinds = [e["payload"].get("limit") for e in c.get("/api/ledger").json()["entries"] if e["type"] == "limit_hit"]
    assert "hunch_chars" in kinds and "spec_validation" in kinds


def test_gemini_failure_is_reported_not_faked(client):
    c, server, fake = client
    fake.replies += [TimeoutError("slow"), TimeoutError("slow")]
    r = c.post("/api/hunch", json={"session_id": "s_err01", "hunch": "buy the dip"})
    assert r.status_code == 502 and "Gemini call failed" in r.json()["error"]


def test_index_served(client):
    c, *_ = client
    assert "Skeptic" in c.get("/").text
    assert c.get("/static/app.js").status_code == 200
