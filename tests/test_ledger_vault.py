import json

import pytest

from eval.synthetic import synthetic_paths
from skeptic.ledger import Ledger
from skeptic.pipeline import LimitError, Skeptic
from skeptic.vault import VaultError, vault_status
from skeptic.verdict import decide

STRONG = {"kind": "dip", "lookback": 12, "threshold": 0.03, "hold": 12, "drift": 0.006}
DIP = {
    "name": "dip",
    "entry": {"all": [{"feature": "return", "lookback": 12, "op": "<=", "value": -0.03}]},
    "exit": {"hold_bars": 12},
}


def write_inputs(path, paths):
    with path.open("w", encoding="utf-8") as fh:
        for p in paths:
            fh.write(json.dumps({"case_id": p.case_id, "task": "markets", "input": {
                "prices_pence": list(p.prices), "dates": ["2000-01-01"] * len(p.prices),
                "initial_cash_pence": p.initial_cash, "fee_pence": p.fee, "slippage_bps": p.bps}}) + "\n")


@pytest.fixture
def sk(tmp_path):
    vault_file = tmp_path / "inputs.jsonl"
    write_inputs(vault_file, synthetic_paths(seed=99, count=120, effect=STRONG))
    return Skeptic(Ledger(tmp_path / "ledger.jsonl"),
                   practice_paths=synthetic_paths(seed=98, count=150, effect=STRONG), vault_inputs=vault_file)


# ---------------------------------------------------------------- ledger
def test_chain_verifies_and_detects_tampering(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    for i in range(5):
        led.append("hunch_submitted", {"text": f"hunch {i}", "n": i})
    assert led.verify_chain()["ok"]
    lines = (tmp_path / "l.jsonl").read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[2])
    tampered["payload"]["n"] = 999
    lines[2] = json.dumps(tampered)
    (tmp_path / "l.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = Ledger(tmp_path / "l.jsonl").verify_chain()
    assert not v["ok"] and v["first_bad_seq"] == 2


def test_chain_detects_deleted_line(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    for i in range(4):
        led.append("limit_hit", {"i": i})
    lines = (tmp_path / "l.jsonl").read_text(encoding="utf-8").splitlines()
    del lines[1]
    (tmp_path / "l.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not Ledger(tmp_path / "l.jsonl").verify_chain()["ok"]


def test_ledger_rejects_unknown_type(tmp_path):
    with pytest.raises(ValueError):
        Ledger(tmp_path / "l.jsonl").append("approve_everything", {})


def test_chain_survives_reload(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append("limit_hit", {"a": 1})
    led2 = Ledger(tmp_path / "l.jsonl")
    led2.append("limit_hit", {"a": 2})
    assert led2.verify_chain() == {**led2.verify_chain(), "ok": True, "entries": 2}


# ---------------------------------------------------------------- trials / lineage
def test_trial_counting_and_lineage(sk):
    a = sk.approve_spec("s", DIP)
    assert a["trials"] == 1
    again = sk.approve_spec("s", DIP)  # same rules: no new trial, same idea
    assert again["trials"] == 1 and again["idea_id"] == a["idea_id"]
    edited = dict(DIP, exit={"hold_bars": 24})
    b = sk.approve_spec("s", edited, parent_fingerprint=a["fingerprint"])
    assert b["idea_id"] == a["idea_id"] and b["trials"] == 2
    fresh = sk.approve_spec("s2", dict(DIP, exit={"hold_bars": 6}))
    assert fresh["idea_id"] != a["idea_id"] and fresh["trials"] == 1


def test_invalid_spec_logs_limit(sk):
    with pytest.raises(LimitError):
        sk.approve_spec("s", {"entry": {"all": []}, "exit": {}})
    assert sk.ledger.entries("limit_hit")


# ---------------------------------------------------------------- vault
def test_vault_full_flow(sk):
    a = sk.approve_spec("s", DIP)
    fp = a["fingerprint"]
    with pytest.raises(VaultError):  # attacks not run yet
        sk.open_vault("s", fp)
    out = sk.run_attacks("s", fp, k=100)
    assert out["gate"]["status"] == "ELIGIBLE", out["gate"]["failing"]
    assert vault_status(sk.ledger, fp)["can_open"]

    res = sk.open_vault("s", fp)
    assert not res["replayed"] and res["verdict"]["label"] == "SURVIVED"
    types = [e["type"] for e in sk.ledger.entries()]
    assert types.index("vault_precommit") < types.index("vault_result")

    # re-open: stored result, nothing rerun
    n_results = len(sk.ledger.entries("vault_result"))
    again = sk.open_vault("s", fp)
    assert again["replayed"] and again["vault"] == res["vault"]
    assert len(sk.ledger.entries("vault_result")) == n_results

    # edit one parameter after seeing the vault -> blocked, logged, contaminated
    b = sk.approve_spec("s", dict(DIP, exit={"hold_bars": 13}), parent_fingerprint=fp)
    assert b["contaminated"]
    sk.run_attacks("s", b["fingerprint"], k=50)
    with pytest.raises(VaultError) as err:
        sk.open_vault("s", b["fingerprint"])
    assert err.value.code == "vault_blocked"
    assert sk.ledger.find("vault_blocked", fingerprint=b["fingerprint"])
    assert sk.ledger.verify_chain()["ok"]


def test_ineligible_spec_cannot_open(tmp_path):
    vault_file = tmp_path / "inputs.jsonl"
    write_inputs(vault_file, synthetic_paths(seed=1, count=30))
    sk = Skeptic(Ledger(tmp_path / "l.jsonl"), practice_paths=synthetic_paths(seed=2, count=80), vault_inputs=vault_file)
    a = sk.approve_spec("s", DIP)
    out = sk.run_attacks("s", a["fingerprint"], k=50)
    assert not out["gate"]["vault_eligible"]
    with pytest.raises(VaultError) as err:
        sk.open_vault("s", a["fingerprint"])
    assert err.value.code == "not_eligible"
    assert not sk.ledger.entries("vault_precommit")


def test_contaminated_can_never_survive():
    gate = {"status": "ELIGIBLE", "failing": [], "vault_eligible": True}
    good = {"median_excess_bps": 120, "sign_p": 0.001}
    assert decide(gate, good)["label"] == "SURVIVED"
    assert decide(gate, good, contaminated=True)["label"] == "INCONCLUSIVE"
    assert decide(gate, {"median_excess_bps": 0, "sign_p": 0.001})["label"] == "REJECTED"
    assert decide(gate, {"median_excess_bps": 30, "sign_p": 0.2})["label"] == "INCONCLUSIVE"
    assert decide({"status": "REJECTED", "failing": ["x"]}, good)["label"] == "REJECTED"


def test_planner_is_preregistered_before_results(sk):
    a = sk.approve_spec("s", DIP)
    seen = {}

    def planner(spec, a1):
        seen.update(a1)
        return [{"tool": "regime_split", "params": {"by": "path_trend"}, "alternative_explanation": "only in downtrends",
                 "supports_if": "only the lowest bucket is positive", "refutes_if": "all buckets positive"}]

    out = sk.run_attacks("s", a["fingerprint"], planner=planner, k=50)
    assert set(seen) == {"summary", "numbers"}  # the planner saw A1 only
    seqs = {e["type"]: e["seq"] for e in sk.ledger.entries() if e["type"] in ("attack_planned",)}
    first_run = min(e["seq"] for e in sk.ledger.entries("attack_run"))
    assert seqs["attack_planned"] < first_run
    assert out["diagnostics"][0]["id"] == "D1"


def test_planner_failure_does_not_block_battery(sk):
    a = sk.approve_spec("s", DIP)

    def broken(spec, a1):
        raise TimeoutError("model slow")

    out = sk.run_attacks("s", a["fingerprint"], planner=broken, k=50)
    assert out["plan_error"] and len(out["results"]) == 6
