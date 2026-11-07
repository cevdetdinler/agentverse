# Commands

Every command that touches the AgentVerse kit lives here, in Markdown, never in a script.
(The kit's provenance scan reads `.py/.js/.sh/...` files only.)

Conventions:

- The kit sits at `agentverse/` inside this project folder and is gitignored. Quote the path if your copy is called `agentverse 2`.
- `py -3` runs the kit (Python 3.9+ standard library only).
- Our code needs Python 3.11+ and the packages in `requirements.txt`. We use a virtual environment, so the **adapter command is the venv interpreter**: `.venv\Scripts\python.exe` on Windows (`.venv/bin/python` on macOS/Linux). On Windows, pass it with backslashes, because the runner starts it without a shell.

## 0. Setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # then paste your Gemini API key into .env
.venv\Scripts\python.exe -m pytest
```

## 1. Fetch data (Binance Vision, CC BY-NC-SA 4.0; never committed)

Seeds are fixed so anyone can rebuild exactly the same files.

| Layer | Seed | Paths |
|---|---|---|
| Practice | `20261107` | 300 |
| Vault | `91802611` | 150 |

```powershell
py -3 "agentverse/finance/bench.py" fetch --cases 300 --seed 20261107 --output data/practice --cache data/_cache
py -3 "agentverse/finance/bench.py" fetch --cases 150 --seed 91802611 --output data/vault --cache data/_cache
```

Our loaders read `inputs.jsonl` only. Nothing in `skeptic/`, `app/` or `eval/` opens an answer file.

## 2. Run the app

```powershell
.venv\Scripts\python.exe -m uvicorn app.server:app --port 8000
```

Then open http://127.0.0.1:8000.

## 3. E1: engine parity with the official runner

Freeze the fixed parity spec, run the kit's runner on all 300 practice paths with our adapter, then compare every case.

```powershell
.venv\Scripts\python.exe eval\certify.py eval\specs\parity_dip.json
py -3 "agentverse/finance/bench.py" run --dataset data/practice --output results/parity/run --limit 300 --max-seconds 900 --adapter .venv\Scripts\python.exe adapter.py --spec results/certified/ddd568044b10291e55386012d0c34c489fd19bf8314b63ac2b252682bc999c14.json
.venv\Scripts\python.exe eval\compare_parity.py results\parity\run\case-results.jsonl data\practice\inputs.jsonl --spec results\certified\ddd568044b10291e55386012d0c34c489fd19bf8314b63ac2b252682bc999c14.json --runner-summary results\parity\run\summary.json --out results\parity\parity_summary.json
```

Pass condition: `identical == cases_compared` and `aggregate_stats_identical: true`. These are **practice** numbers, used only to prove the engine is correct. They are never results.

## 4. Self-serve hidden challenge (smoke test)

```powershell
py -3 "agentverse/finance/bench.py" challenge --pack real-markets --cases 6 --project . --output results/challenge/smoke --adapter .venv\Scripts\python.exe adapter.py --spec results/certified/<fingerprint>.json
```

Check `REPORT.md` for provenance warnings (there must be none).

## 5. E3: certified hunches on the hidden challenge

`eval\run_e3.py` takes each pre-written hunch spec in `eval/e3_hunches.json`. For each one it records the naive verdict and Skeptic's verdict (practice + vault), freezes the spec to `results/certified/<fp>.json` and prints the challenge command. Run each printed command:

```powershell
.venv\Scripts\python.exe eval\run_e3.py prepare
py -3 "agentverse/finance/bench.py" challenge --pack real-markets --cases 60 --project . --output results/challenge/<fp> --adapter .venv\Scripts\python.exe adapter.py --spec results/certified/<fp>.json
.venv\Scripts\python.exe eval\run_e3.py table
```

Everything after `--adapter` is the adapter command. Options must come before it.

## 6. Judges' run (organiser-sealed)

```powershell
py -3 "agentverse/finance/bench.py" challenge --seed-prompt --team "Skeptic" --pack real-markets --cases 60 --project . --output judging/skeptic --adapter .venv\Scripts\python.exe adapter.py --spec results/certified/<fingerprint>.json
```

## 7. Optional live forward test (E5)

This is a demo of honest operation. It is not proof of an edge.

```powershell
py -3 "agentverse/finance/bench.py" live --symbol BTCUSDT --interval 1m --steps 30 --output results/live/<fp> --adapter .venv\Scripts\python.exe adapter.py --spec results/certified/<fp>.json
```

## 8. Before pushing

Use the kit's `review-and-push` skill. It runs a secret scan and the preflight checks.
