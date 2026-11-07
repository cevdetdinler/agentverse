"""Our repo must never trip the kit's provenance scan, and only vault.py may know where the vault is.

The flagged strings are assembled from pieces so this file itself stays clean.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".ipynb", ".sh"}
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".agents", "dist", "build", "agentverse", "data", "logs"}

_k = "fin" + "ance"
RULES = [
    re.compile(r"\b(from|import)\s+(" + "co" + "re|test" + "bed|ben" + "ch|example_" + "adapter" + r")\b"),
    re.compile(_k + r"[/\.](" + "co" + "re|test" + "bed|ben" + "ch" + ")"),
    re.compile("answers" + r"\.jsonl|" + "SEED-" + "REVEAL|" + "organiser-" + "seed"),
    re.compile("AGENTVERSE_" + "CHALLENGE|" + "agentverse-" + "v2:|" + "agentverse-" + "seal"),
    re.compile("data" + r"\.binance\.vision|" + "/api/v3/" + "klines"),
]


def scanned_files():
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if path.is_file() and path.suffix in SCANNED and not (set(rel.parts) & SKIP):
            yield path, rel


def test_no_flagged_strings_in_scanned_files():
    hits = []
    for path, rel in scanned_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for rule in RULES:
            if rule.search(text):
                hits.append((str(rel), rule.pattern))
    assert not hits, hits


def test_rules_do_catch_a_flagged_line():
    # counterexample: the same rules flag an obviously bad line
    bad = "imp" + "ort " + "ben" + "ch\nopen('" + "answers" + ".jsonl')"
    assert any(rule.search(bad) for rule in RULES)


def test_only_vault_module_knows_the_vault_path():
    pattern = re.compile(r"""["']vault["']\s*/|data[/\]vault|["']vault["']\s*,\s*["']inputs""")
    offenders = []
    for path, rel in scanned_files():
        if rel.as_posix() in ("skeptic/vault.py", "tests/test_provenance.py"):
            continue
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(rel))
    assert not offenders, offenders


def test_no_broker_or_order_code():
    pattern = re.compile(r"place_order|create_order|submit_order|ccxt|alpaca|binance\.client", re.I)
    offenders = [str(rel) for path, rel in scanned_files()
                 if rel.name != "test_provenance.py" and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))]
    assert not offenders, offenders
