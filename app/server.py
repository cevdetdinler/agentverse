"""Skeptic web API + static UI.

    .venv\\Scripts\\python.exe -m uvicorn app.server:app --port 8000

Two markets, each with its own ledger, practice data, vault and Gemini call budget:
  real       Binance Vision windows fetched with the kit (default)
  synthetic  our own generator with a planted pattern (labelled "Synthetic market" in the UI)
"""
from __future__ import annotations

import hashlib
import json
import secrets
import tempfile
import threading
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.today import today
from skeptic import config
from skeptic.agent import AgentCallError, AgentLimitError
from skeptic.data import PRACTICE_INPUTS
from skeptic.markets import MARKETS, Market, build
from skeptic.pipeline import LimitError
from skeptic.spec import RuleCard
from skeptic.vault import VaultError, vault_status

STATIC = Path(__file__).resolve().parent / "static"
MarketName = Literal["real", "synthetic"]

app = FastAPI(title="Skeptic", version="1.1")
_markets: dict[str, Market] = {}
_markets_lock = threading.Lock()
_sessions: dict[tuple[str, str], dict] = {}
_sessions_lock = threading.Lock()

FUNCTION_FOR = {
    "A1": "skeptic.attacks.a1_baseline", "A2": "skeptic.attacks.a2_permutation", "A3": "skeptic.attacks.a3_wobble",
    "A4": "skeptic.attacks.a4_cost_stress", "A5": "skeptic.attacks.a5_outliers", "A6": "skeptic.attacks.a6_trials",
}


def M(name: str = "real") -> Market:
    if name not in MARKETS:
        raise KeyError(f"unknown market {name!r}")
    with _markets_lock:
        if name not in _markets:
            _markets[name] = build(name)
        return _markets[name]


def _session(market: str, sid: str) -> dict:
    with _sessions_lock:
        return _sessions.setdefault((market, sid), {"rounds": 0, "previous_id": None, "hunch": None, "answers": {}})


def _file_sha(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


PRACTICE_SHA = _file_sha(PRACTICE_INPUTS)
STARTUP_CHAIN = M("real").ledger.verify_chain()


def _data_step(market: str, paths) -> dict:
    if market == "real":
        return {"step": "raw data", "detail": "data/practice/inputs.jsonl (Binance Vision windows via the kit's fetch)",
                "sha256": PRACTICE_SHA, "paths": paths}
    m = config.SYNTHETIC_MARKET
    return {"step": "raw data", "detail": f"Synthetic market: {MARKETS['synthetic']['source']}",
            "sha256": f"seed {m['practice_seed']} · planted {m['effect']}", "paths": paths}


# ------------------------------------------------------------------ errors
@app.exception_handler(LimitError)
def _limit(_: Request, exc: LimitError):
    return JSONResponse(status_code=422, content={"error": exc.message, "limit": exc.limit})


@app.exception_handler(AgentLimitError)
def _agent_limit(_: Request, exc: AgentLimitError):
    return JSONResponse(status_code=429, content={"error": exc.message, "limit": exc.limit})


@app.exception_handler(AgentCallError)
def _agent_call(_: Request, exc: AgentCallError):
    return JSONResponse(status_code=502, content={"error": f"Gemini call failed: {exc}. The maths still works; try again."})


@app.exception_handler(VaultError)
def _vault(_: Request, exc: VaultError):
    return JSONResponse(status_code=409, content={"error": exc.message, "code": exc.code, **exc.payload})


@app.exception_handler(KeyError)
def _key(_: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"error": str(exc).strip("'\"")})


# ------------------------------------------------------------------ models
class HunchIn(BaseModel):
    session_id: str = Field(min_length=4, max_length=64)
    hunch: Optional[str] = None
    answers: Optional[dict[str, str]] = None
    market: MarketName = "real"


class ApproveIn(BaseModel):
    session_id: str
    spec: dict
    parent_fingerprint: Optional[str] = None
    market: MarketName = "real"


class FpIn(BaseModel):
    session_id: str
    fingerprint: str = Field(min_length=64, max_length=64)
    k: int = config.PERM_K_DEFAULT
    market: MarketName = "real"


# ------------------------------------------------------------------ hunch -> questions or rule card
@app.post("/api/hunch")
def post_hunch(body: HunchIn):
    m = M(body.market)
    s = _session(body.market, body.session_id)
    if body.hunch is not None:
        text = body.hunch.strip()
        if not text:
            raise LimitError("hunch_empty", "Type a hunch first.")
        if len(text) > config.LIMITS["hunch_chars"]:
            raise m.skeptic.limit("hunch_chars", f"Hunches are limited to {config.LIMITS['hunch_chars']} characters.",
                                  body.session_id, length=len(text))
        s.update({"hunch": text, "rounds": 0, "previous_id": None, "answers": {}})
        m.ledger.append("hunch_submitted", {"session_id": body.session_id, "text": text})
        out = m.agent.translate_hunch(body.session_id, text)
    else:
        if not s.get("hunch") or not body.answers:
            raise LimitError("no_hunch", "Start with a hunch.")
        s["rounds"] += 1
        s["answers"].update(body.answers)
        out = m.agent.translate_hunch(body.session_id, s["hunch"], answers=body.answers, previous_id=s["previous_id"],
                                      force_spec=s["rounds"] >= 2)
    s["previous_id"] = out["interaction_id"]
    if "questions" in out:
        m.ledger.append("questions_asked", {"session_id": body.session_id, "questions": out["questions"],
                                            "interaction_id": out["interaction_id"]})
        return {"questions": out["questions"], "interaction_id": out["interaction_id"], "model": out["model"]}
    card = RuleCard.model_validate(out["spec"])
    m.ledger.append("spec_proposed", {"session_id": body.session_id, "spec": out["spec"], "fingerprint": card.fingerprint,
                                      "interaction_id": out["interaction_id"], "answers": s["answers"]})
    return {"spec": out["spec"], "fingerprint": card.fingerprint, "rules_text": card.describe(),
            "interaction_id": out["interaction_id"], "model": out["model"]}


@app.post("/api/spec/preview")
def preview_spec(body: ApproveIn):
    """Validate an edited card and show its fingerprint without approving it."""
    try:
        card = RuleCard.model_validate(body.spec)
    except Exception as exc:  # pydantic ValidationError
        raise LimitError("spec_validation", f"Rule card rejected: {exc}") from exc
    return {"fingerprint": card.fingerprint, "rules_text": card.describe()}


@app.post("/api/spec/approve")
def approve(body: ApproveIn):
    return M(body.market).skeptic.approve_spec(body.session_id, body.spec, body.parent_fingerprint)


# ------------------------------------------------------------------ attacks
@app.post("/api/attack")
def attack(body: FpIn):
    m = M(body.market)

    def planner(spec, a1):
        return m.agent.plan_diagnostics(body.session_id, spec, a1)

    return m.skeptic.run_attacks(body.session_id, body.fingerprint, planner=planner, k=body.k)


# ------------------------------------------------------------------ vault (human click only)
@app.get("/api/vault/status")
def get_vault_status(fingerprint: str, market: MarketName = "real"):
    return vault_status(M(market).ledger, fingerprint)


@app.post("/api/vault/open")
def post_vault_open(body: FpIn):
    return M(body.market).skeptic.open_vault(body.session_id, body.fingerprint)


# ------------------------------------------------------------------ explanation + rewrite
@app.post("/api/explain")
def explain(body: FpIn):
    m = M(body.market)
    bundle = m.skeptic.results_bundle(body.fingerprint)
    if not bundle["verdict"]["label"]:
        raise LimitError("no_verdict", "Run the attacks first.")
    out = m.agent.explain_verdict(body.session_id, bundle, body.fingerprint)
    m.ledger.append("explanation", {"session_id": body.session_id, "fingerprint": body.fingerprint, "label": out["label"],
                                    "text": out["text"], "interaction_ids": out["interaction_ids"],
                                    "removed_count": out["removed_count"], "regenerated": out["regenerated"]})
    return {**out, "verdict": bundle["verdict"]}


@app.post("/api/rewrite")
def rewrite(body: FpIn):
    m = M(body.market)
    spec = m.skeptic.spec_for(body.fingerprint)
    practice = m.ledger.last("verdict", fingerprint=body.fingerprint, stage="practice")
    failures = practice["payload"]["gate"]["failing"] if practice else []
    out = m.agent.suggest_rewrite(body.session_id, spec, failures or ["(no failures recorded)"])
    card = RuleCard.model_validate(out["spec"])
    out["spec"] = card.model_copy(update={"idea_id": spec.idea_id, "parent_fingerprint": body.fingerprint}).model_dump(mode="json")
    out["fingerprint"] = card.fingerprint
    out["rules_text"] = card.describe()
    m.ledger.append("spec_proposed", {"session_id": body.session_id, "spec": out["spec"], "fingerprint": card.fingerprint,
                                      "interaction_id": out["interaction_id"], "source": "suggest_rewrite",
                                      "parent_fingerprint": body.fingerprint})
    return out


# ------------------------------------------------------------------ autocomplete + history
@app.get("/api/suggest")
def suggest(q: str, session_id: str, market: MarketName = "real"):
    m = M(market)
    q = q[: config.LIMITS["hunch_chars"]]
    if len(q.strip()) < 15:
        return {"completions": []}
    history = [e["payload"]["text"] for e in m.ledger.entries("hunch_submitted")][-12:]
    history += [f"answered: {a}" for e in m.ledger.entries("spec_proposed")[-6:]
                for a in (e["payload"].get("answers") or {}).values()]
    out = m.agent.suggest_completions(session_id, q, history)
    if out["completions"]:
        m.ledger.append("suggestion_shown", {"session_id": session_id, "prefix": q, "completions": out["completions"],
                                             "cached": out.get("cached", False), "interaction_id": out.get("interaction_id")})
    return out


@app.get("/api/history")
def history(market: MarketName = "real"):
    ledger = M(market).ledger
    hunches = [{"text": e["payload"]["text"], "ts": e["ts"], "session_id": e["payload"].get("session_id")}
               for e in ledger.entries("hunch_submitted")]
    ideas: dict[str, dict] = {}
    for e in ledger.entries("spec_approved"):
        p = e["payload"]
        idea = ideas.setdefault(p["idea_id"], {"idea_id": p["idea_id"], "hunch_text": p["spec"].get("hunch_text", ""),
                                               "specs": [], "trials": 0})
        if p["fingerprint"] not in [x["fingerprint"] for x in idea["specs"]]:
            idea["specs"].append({"fingerprint": p["fingerprint"], "name": p["spec"].get("name"), "ts": e["ts"],
                                  "rules_text": RuleCard.model_validate(p["spec"]).describe()})
    for idea_id, idea in ideas.items():
        idea["trials"] = ledger.trials(idea_id)
        for sp in idea["specs"]:
            v = ledger.last("verdict", fingerprint=sp["fingerprint"], stage="final") or \
                ledger.last("verdict", fingerprint=sp["fingerprint"], stage="practice")
            sp["verdict"] = v["payload"]["label"] if v else None
            sp["stage"] = v["payload"]["stage"] if v else None
            sp["vault"] = vault_status(ledger, sp["fingerprint"])["state"]
    return {"hunches": hunches[-100:], "ideas": sorted(ideas.values(), key=lambda i: i["specs"][-1]["ts"], reverse=True)}


@app.get("/api/today")
def today_ideas():
    """Live 'today's market' idea suggestions for the empty hunch box. Display only (docs/DECISIONS.md D8)."""
    return today()


@app.get("/api/library")
def library():
    if config.HUNCH_LIBRARY.exists():
        return json.loads(config.HUNCH_LIBRARY.read_text(encoding="utf-8"))
    return {"hunches": []}


# ------------------------------------------------------------------ ledger + trace
@app.get("/api/ledger")
def get_ledger(limit: int = 300, market: MarketName = "real"):
    ledger = M(market).ledger
    return {"entries": ledger.tail(min(max(1, limit), 2000)), "verify": ledger.verify_chain()}


@app.get("/api/ledger/verify")
def verify(market: MarketName = "real"):
    return M(market).ledger.verify_chain()


@app.get("/api/trace")
def trace(fingerprint: str, attack: str, market: MarketName = "real"):
    ledger = M(market).ledger
    run = None
    for e in ledger.find("attack_run", fingerprint=fingerprint):
        if e["payload"]["id"] == attack:
            run = e
    if not run:
        raise KeyError(f"no {attack} run for this rule card")
    approved = ledger.last("spec_approved", fingerprint=fingerprint)
    planned = None
    for e in ledger.find("attack_planned", fingerprint=fingerprint):
        if e["payload"]["id"] == attack:
            planned = e
    llm = [e for e in ledger.entries("llm_call") if e["payload"].get("session_id") == run["payload"].get("session_id")]
    tool = run["payload"]["inputs"].get("tool")
    return {
        "market": market,
        "steps": [
            _data_step(market, run["payload"]["inputs"].get("paths")),
            {"step": "rule card", "detail": f"approved by a human, ledger seq {approved['seq'] if approved else '?'}",
             "fingerprint": fingerprint},
            {"step": "pre-registration", "detail": planned["payload"]["alternative_explanation"] if planned else
             "fixed battery: hypothesis and threshold set in skeptic/config.py before any data",
             "seq": planned["seq"] if planned else None},
            {"step": "function", "detail": FUNCTION_FOR.get(attack, f"skeptic.attacks.run_diagnostic('{tool}')"),
             "inputs": run["payload"]["inputs"]},
            {"step": "output", "detail": run["payload"]["summary"], "seq": run["seq"], "hash": run["hash"],
             "numbers": run["payload"]["numbers"]},
        ],
        "llm_calls": [{"seq": e["seq"], "purpose": e["payload"].get("purpose"), "model": e["payload"].get("model"),
                       "interaction_id": e["payload"].get("interaction_id"), "ok": e["payload"].get("ok")} for e in llm][-20:],
    }


@app.get("/api/config")
def get_config(session_id: str = "", market: MarketName = "real"):
    m = M(market)
    return {"models": config.MODEL_IDS, "gate": config.GATE, "vault_pass": config.VAULT_PASS, "limits": config.LIMITS,
            "perm_k_default": config.PERM_K_DEFAULT, "chain": m.ledger.verify_chain(), "startup_chain": STARTUP_CHAIN,
            "practice_sha256": PRACTICE_SHA, "usage": m.agent.usage(session_id) if session_id else None,
            "markets": MARKETS, "market": market, "practice_paths": len(m.skeptic.paths),
            "new_session_id": "s_" + secrets.token_hex(6)}


# ------------------------------------------------------------------ stretch: media -> hunch
ALLOWED_MEDIA = {"video/mp4": "video", "video/quicktime": "video", "video/webm": "video",
                 "image/png": "image", "image/jpeg": "image", "image/webp": "image"}


@app.post("/api/ingest")
async def ingest(session_id: str = Form(...), market: str = Form("real"), file: UploadFile = File(...)):
    m = M(market)
    kind = ALLOWED_MEDIA.get(file.content_type or "")
    if not kind:
        raise LimitError("media_type", "Upload an MP4/MOV/WebM clip or a PNG/JPEG/WebP screenshot.")
    data = await file.read()
    if len(data) > config.LIMITS["max_upload_bytes"]:
        raise m.skeptic.limit("max_upload_bytes", "Uploads are limited to 20 MB.", session_id, size=len(data))
    suffix = Path(file.filename or "upload").suffix or (".mp4" if kind == "video" else ".png")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(data)
        uploaded = m.agent.upload_file(path, file.content_type)
    out = m.agent.ingest_media(session_id, uploaded["uri"], file.content_type, kind)
    m.ledger.append("ingest", {"session_id": session_id, "kind": kind, "bytes": len(data),
                               "sha256": hashlib.sha256(data).hexdigest(), "file_uri": uploaded["uri"],
                               "hunch": out["hunch"], "claims": out["claims"], "interaction_id": out["interaction_id"]})
    return out


# ------------------------------------------------------------------ static
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
