"""The attack battery (A1-A6), the agent-selectable diagnostics, and the practice gate.

Every attack is a pure function of (spec, practice paths, params, seed). No LLM is involved:
the model may only *choose* diagnostics and their parameters from DIAGNOSTICS (validated here).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import numpy as np
from pydantic import ValidationError

from . import config
from .data import PricePath
from .engine import buy_and_hold_batch, buy_and_hold_final, simulate, simulate_batch_paths
from .spec import RuleCard, compute_positions, compute_positions_batch
from .stats import aggregate, bootstrap_median_ci, median_int, sign_test_p

ALPHA = config.GATE["alpha"]


@dataclass
class AttackResult:
    id: str
    name: str
    hypothesis: str
    numbers: dict
    passed: Optional[bool]
    threshold: str
    inputs: dict
    summary: str
    chart: dict = field(default_factory=dict)
    kind: str = "fixed"  # fixed | diagnostic

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ evaluation core
@dataclass
class Evaluation:
    """Per-path results of one spec on one set of paths at one cost level."""
    rows: list[dict]
    positions: list[list[bool]]

    @property
    def excess(self) -> list[int]:
        return [r["excess_bps"] for r in self.rows]


def evaluate(spec: RuleCard, paths, fee_mult: int = 1, bps_mult: int = 1, positions=None,
             stress_benchmark: bool = True) -> Evaluation:
    """stress_benchmark=False keeps buy-and-hold at real costs while the strategy pays the multiplied
    costs (the conservative cost stress: otherwise a rule that rarely trades 'gains' when costs rise)."""
    rows, all_pos = [], []
    for idx, p in enumerate(paths):
        pos = positions[idx] if positions is not None else compute_positions(spec, p.prices)
        fee, bps = p.fee * fee_mult, p.bps * bps_mult
        sim = simulate(p.prices, pos, p.initial_cash, fee, bps)
        bh = (buy_and_hold_final(p.prices, p.initial_cash, fee, bps) if stress_benchmark
              else buy_and_hold_final(p.prices, p.initial_cash, p.fee, p.bps))
        rows.append(
            {
                "case_id": p.case_id,
                "final_cash": sim.final_cash,
                "bh_final": bh,
                "initial_cash": p.initial_cash,
                "excess_bps": (sim.final_cash - bh) * 10000 // p.initial_cash,
                "strategy_return_bps": (sim.final_cash - p.initial_cash) * 10000 // p.initial_cash,
                "bh_return_bps": (bh - p.initial_cash) * 10000 // p.initial_cash,
                "max_drawdown_bps": sim.max_drawdown_bps,
                "trades": sim.trades,
                "bars_in_position": sim.bars_in_position,
                "decisions": sim.decisions,
            }
        )
        all_pos.append(pos)
    return Evaluation(rows, all_pos)


def _pc(bps) -> str:
    """Display a basis-point figure as a signed percentage (display only; the number stays in bps)."""
    return f"{bps / 100:+.2f}%"


def _median(values) -> int:
    return median_int(values) if len(values) else 0


def _hist(values, bins: int = 20) -> dict:
    arr = np.asarray(values, dtype=float)
    if not len(arr):
        return {"type": "hist", "counts": [], "edges": []}
    lo, hi = np.percentile(arr, [1, 99]) if len(arr) > 20 else (arr.min(), arr.max())
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    counts, edges = np.histogram(np.clip(arr, lo, hi), bins=bins, range=(lo, hi))
    return {"type": "hist", "counts": counts.tolist(), "edges": [round(float(e), 1) for e in edges]}


# ------------------------------------------------------------------ A1 baseline
def a1_baseline(spec: RuleCard, paths, ev: Evaluation, seed: int = config.SEEDS["bootstrap"]) -> AttackResult:
    agg = aggregate(ev.rows)
    lo, hi = bootstrap_median_ci(ev.excess, config.BOOTSTRAP_RESAMPLES, seed)
    bars_in = sum(r["bars_in_position"] for r in ev.rows)
    decisions = sum(r["decisions"] for r in ev.rows)
    exposure_pct = round(100.0 * bars_in / decisions, 1) if decisions else 0.0
    passed = agg["median_excess_bps"] > 0 and agg["sign_p"] is not None and agg["sign_p"] < ALPHA
    numbers = {
        **agg,
        "median_excess_ci95_bps": [lo, hi],
        "exposure_pct": exposure_pct,
        "sign_p": None if agg["sign_p"] is None else round(agg["sign_p"], 4),
    }
    p_txt = "n/a" if numbers["sign_p"] is None else f"{numbers['sign_p']:.4f}"
    summary = (
        f"Over {agg['paths']} real price histories, the rule beat just buying and holding in {agg['wins']} and lost in "
        f"{agg['losses']}. Typical result: {_pc(agg['median_excess_bps'])} vs holding (likely range {_pc(lo)} to {_pc(hi)}). "
        f"Luck score p = {p_txt} (below 0.05 means it is unlikely to be a coin flip). {agg['total_trades']} trades; "
        f"money invested {exposure_pct}% of the time."
    )
    return AttackResult(
        id="A1",
        name="Did it beat just holding?",
        hypothesis="It beats simply buying and holding, after real fees, more often than a coin flip would.",
        numbers=numbers,
        passed=passed,
        threshold=f"Pass: typical result above 0% and luck score below {ALPHA}",
        inputs={"paths": len(paths), "bootstrap_resamples": config.BOOTSTRAP_RESAMPLES, "seed": seed,
                "fingerprint": spec.fingerprint},
        summary=summary,
        chart={**_hist(ev.excess), "label": "result vs holding, one bar per price history", "marker": agg["median_excess_bps"]},
    )


# ------------------------------------------------------------------ A2 shuffled-returns (timing) test
def shuffled_surrogates(prices, k: int, rng: np.random.Generator) -> np.ndarray:
    """K copies of a path rebuilt from its own one-bar log returns in random order.

    Same start price, same end price (up to integer rounding), same set of moves and volatility,
    but no information in the ORDER of moves. Under the null "the rule's timing carries no
    information", the real path is exchangeable with these surrogates.
    """
    p = np.asarray(prices, dtype=np.float64)
    r = np.diff(np.log(p))
    order = np.argsort(rng.random((k, len(r))), axis=1)
    logp = np.log(p[0]) + np.concatenate([np.zeros((k, 1)), np.cumsum(r[order], axis=1)], axis=1)
    return np.maximum(1, np.rint(np.exp(logp))).astype(np.int64)


def a2_permutation(spec: RuleCard, paths, ev: Evaluation, k: int = config.PERM_K_DEFAULT,
                   seed: int = config.SEEDS["permutation"]) -> AttackResult:
    """Shuffled-returns test. (Replaces the in-path random-entry permutation: see docs/DECISIONS.md D1.)"""
    if not 1 <= k <= config.LIMITS["max_perm_k"]:
        raise ValueError(f"permutation K must be 1..{config.LIMITS['max_perm_k']}")
    rng = np.random.default_rng(seed)
    total = np.zeros(k, dtype=np.float64)
    for p in paths:
        surrogate = shuffled_surrogates(p.prices, k, rng)
        pos = compute_positions_batch(spec, surrogate)
        finals = simulate_batch_paths(surrogate, pos, p.initial_cash, p.fee, p.bps)
        bh = buy_and_hold_batch(surrogate, p.initial_cash, p.fee, p.bps)
        total += (finals - bh) * 10000 // p.initial_cash
    perm_means = total / len(paths)
    observed = float(np.mean(ev.excess))
    exceed = int(np.sum(perm_means >= observed))
    p_perm = (1 + exceed) / (1 + k)
    passed = p_perm < ALPHA
    numbers = {
        "observed_mean_excess_bps": round(observed, 1),
        "perm_mean_excess_median_bps": round(float(np.median(perm_means)), 1),
        "perm_mean_excess_p95_bps": round(float(np.percentile(perm_means, 95)), 1),
        "perm_at_or_above_observed": exceed,
        "K": k,
        "p_perm": round(p_perm, 4),
        "observed_percentile": round(100.0 * float(np.mean(perm_means < observed)), 1),
    }
    summary = (
        f"We scrambled the order of each price history's moves {k} times (same ups and downs, no pattern left to find) "
        f"and reran your rule. The scrambled markets did at least as well in {exceed} of {k} cases "
        f"(luck score p = {p_perm:.4f}). Your average: {_pc(observed)} vs holding; scrambled: "
        f"{_pc(numbers['perm_mean_excess_median_bps'])}."
    )
    return AttackResult(
        id="A2",
        name="Luck check",
        hypothesis="It wins because of real timing, not luck.",
        numbers=numbers,
        passed=passed,
        threshold=f"Pass: luck score below {ALPHA}",
        inputs={"K": k, "seed": seed, "paths": len(paths), "fingerprint": spec.fingerprint,
                "null": "one-bar log returns shuffled within each path"},
        summary=summary,
        chart={**_hist(perm_means.tolist()), "label": "scrambled markets; the dark line is your rule", "marker": round(observed, 1)},
    )


# ------------------------------------------------------------------ A3 wobble
def _numeric_params(spec: RuleCard) -> list[tuple[str, tuple, bool]]:
    """(label, path into rules dict, is_int). Zero-valued parameters are skipped (scaling 0 is 0)."""
    rules = spec.rules_dict()
    out = []
    for section, key in (("entry", "all"), ("exit", "any")):
        for i, c in enumerate(rules[section][key]):
            tag = f"{section}[{i}].{c['feature']}"
            for name in ("lookback", "window", "fast", "slow"):
                if c.get(name):
                    out.append((f"{tag}.{name}", (section, key, i, name), True))
            if c["value"] != 0:
                out.append((f"{tag}.value", (section, key, i, "value"), c["feature"] == "down_streak"))
    for name in ("hold_bars", "take_profit", "stop_loss"):
        v = rules["exit"].get(name)
        if v:
            out.append((f"exit.{name}", ("exit", name), name == "hold_bars"))
    if rules["cooldown_bars"]:
        out.append(("cooldown_bars", ("cooldown_bars",), True))
    return out


def _get(rules: dict, path: tuple):
    node = rules
    for part in path:
        node = node[part]
    return node


def _set(rules: dict, path: tuple, value) -> None:
    node = rules
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


def _scaled(value, step: float, is_int: bool):
    v = value * (1 + step)
    return max(1, int(round(v))) if is_int else round(v, 6)


def _variant(spec: RuleCard, changes: list[tuple[tuple, object]]) -> Optional[RuleCard]:
    rules = spec.rules_dict()
    for path, val in changes:
        _set(rules, path, val)
    try:
        return RuleCard.model_validate({**spec.model_dump(mode="json"), **rules})
    except ValidationError:
        return None


def a3_wobble(spec: RuleCard, paths, ev: Evaluation) -> AttackResult:
    base_median = _median(ev.excess)
    params = _numeric_params(spec)
    rules = spec.rules_dict()
    seen = {spec.fingerprint: base_median}
    oat: dict[str, dict] = {}
    importance = {}

    def med_for(card: RuleCard) -> int:
        fp = card.fingerprint
        if fp not in seen:
            seen[fp] = _median(evaluate(card, paths).excess)
        return seen[fp]

    neighbours: list[dict] = []
    for label, path, is_int in params:
        base_val = _get(rules, path)
        row = {}
        for step in config.WOBBLE_STEPS:
            new = _scaled(base_val, step, is_int)
            if new == base_val:
                continue
            card = _variant(spec, [(path, new)])
            if card is None:
                continue
            m = med_for(card)
            row[f"{step:+.0%}"] = {"value": new, "median_excess_bps": m}
            neighbours.append({"fingerprint": card.fingerprint, "median_excess_bps": m, "change": f"{label}={new}"})
        oat[label] = row
        if row:
            importance[label] = max(abs(v["median_excess_bps"] - base_median) for v in row.values())

    joint = None
    top = sorted(importance, key=lambda k: -importance[k])[:2]
    if len(top) == 2:
        (l1, p1, i1), (l2, p2, i2) = [next(x for x in params if x[0] == t) for t in top]
        grid = []
        for s1 in config.WOBBLE_JOINT_STEPS:
            row = []
            for s2 in config.WOBBLE_JOINT_STEPS:
                if s1 == 0 and s2 == 0:
                    row.append({"median_excess_bps": base_median, "is_user_spec": True})
                    continue
                v1, v2 = _scaled(_get(rules, p1), s1, i1), _scaled(_get(rules, p2), s2, i2)
                card = _variant(spec, [(p1, v1), (p2, v2)])
                if card is None:
                    row.append(None)
                    continue
                m = med_for(card)
                row.append({"median_excess_bps": m, l1: v1, l2: v2})
                neighbours.append({"fingerprint": card.fingerprint, "median_excess_bps": m, "change": f"{l1}={v1}, {l2}={v2}"})
            grid.append(row)
        joint = {"params": [l1, l2], "steps": list(config.WOBBLE_JOINT_STEPS), "grid": grid}

    uniq = {n["fingerprint"]: n for n in neighbours if n["fingerprint"] != spec.fingerprint}
    meds = [n["median_excess_bps"] for n in uniq.values()]
    share = (sum(m > 0 for m in meds) / len(meds)) if meds else 0.0
    rank = 1 + sum(m > base_median for m in meds)
    passed = bool(meds) and share >= config.GATE["wobble_min_share"]
    numbers = {
        "neighbours": len(meds),
        "share_positive_pct": round(100 * share, 1),
        "user_spec_median_excess_bps": base_median,
        "user_spec_rank": rank,
        "rank_out_of": len(meds) + 1,
        "knife_edge": not passed,
        "best_neighbour_median_bps": max(meds) if meds else None,
        "worst_neighbour_median_bps": min(meds) if meds else None,
    }
    summary = (
        f"We nudged each number in your rule up and down by up to 30% ({len(meds)} variations). "
        f"{numbers['share_positive_pct']}% of them still beat holding. Yours ranks {rank} of {len(meds) + 1}."
        + (" Fragile: it only works at these exact settings." if not passed else "")
    )
    return AttackResult(
        id="A3",
        name="Fragility check",
        hypothesis="It still works if the numbers are slightly different.",
        numbers=numbers,
        passed=passed,
        threshold=f"Pass: at least {config.GATE['wobble_min_share']:.0%} of variations still beat holding (Skeptic never swaps in a better one)",
        inputs={"steps": list(config.WOBBLE_STEPS), "joint_steps": list(config.WOBBLE_JOINT_STEPS),
                "params": [p[0] for p in params], "fingerprint": spec.fingerprint},
        summary=summary,
        chart={"type": "wobble", "oat": oat, "joint": joint, "base": base_median},
    )


# ------------------------------------------------------------------ A4 cost stress
def _cost_row(spec, paths, ev, mult: int) -> dict:
    stressed = evaluate(spec, paths, fee_mult=mult, bps_mult=mult, positions=ev.positions, stress_benchmark=False)
    agg = aggregate(stressed.rows)
    return {"multiplier": mult, "median_excess_bps": agg["median_excess_bps"], "wins": agg["wins"],
            "losses": agg["losses"], "sign_p": None if agg["sign_p"] is None else round(agg["sign_p"], 4)}


def a4_cost_stress(spec: RuleCard, paths, ev: Evaluation) -> AttackResult:
    base = aggregate(ev.rows)
    rows = [{"multiplier": 1, "median_excess_bps": base["median_excess_bps"], "wins": base["wins"],
             "losses": base["losses"], "sign_p": None if base["sign_p"] is None else round(base["sign_p"], 4)}]
    rows += [_cost_row(spec, paths, ev, m) for m in config.COST_MULTIPLIERS]
    gate_m = config.GATE["cost_gate_multiplier"]
    at_gate = next(r for r in rows if r["multiplier"] == gate_m)
    passed = at_gate["median_excess_bps"] > 0
    numbers = {f"median_excess_x{r['multiplier']}_bps": r["median_excess_bps"] for r in rows}
    numbers["table"] = rows
    summary = (
        f"Paying double fees, the typical result would be {_pc(at_gate['median_excess_bps'])} vs holding; triple fees, "
        f"{_pc(rows[-1]['median_excess_bps'])} (at normal fees: {_pc(rows[0]['median_excess_bps'])})."
    )
    return AttackResult(
        id="A4",
        name="Higher fees check",
        hypothesis="It still works if trading costs more.",
        numbers=numbers,
        passed=passed,
        threshold=f"Pass: still above 0% when paying {gate_m}x fees (holding keeps normal fees)",
        inputs={"multipliers": [1, *config.COST_MULTIPLIERS], "fingerprint": spec.fingerprint},
        summary=summary,
        chart={"type": "bars", "labels": [f"x{r['multiplier']}" for r in rows], "values": [r["median_excess_bps"] for r in rows],
               "label": "typical result at normal, 2x and 3x fees"},
    )


# ------------------------------------------------------------------ A5 outliers
def _drop_top(excess: list[int], pct: float) -> tuple[list[int], int]:
    drop = max(1, math.ceil(len(excess) * pct / 100)) if excess else 0
    kept = sorted(excess)[: len(excess) - drop]
    return kept, drop


def a5_outliers(spec: RuleCard, paths, ev: Evaluation, pct: float = config.GATE["outlier_drop_pct"],
                id_: str = "A5", kind: str = "fixed") -> AttackResult:
    excess = ev.excess
    kept, dropped = _drop_top(excess, pct)
    before_med, before_mean = _median(excess), (sum(excess) // len(excess) if excess else 0)
    after_med = _median(kept)
    after_mean = sum(kept) // len(kept) if kept else 0
    passed = after_med > 0
    numbers = {"dropped_paths": dropped, "pct": pct, "median_before_bps": before_med, "mean_before_bps": before_mean,
               "median_after_bps": after_med, "mean_after_bps": after_mean,
               "mean_sign_flipped": (before_mean > 0) != (after_mean > 0)}
    summary = (
        f"Without the best {dropped} price histories (top {pct:g}%), the typical result goes from {_pc(before_med)} to "
        f"{_pc(after_med)}, and the average from {_pc(before_mean)} to {_pc(after_mean)}."
    )
    return AttackResult(
        id=id_,
        name="Lucky-streak check" if kind == "fixed" else f"Without the best {pct:g}%",
        hypothesis="It isn't carried by a few lucky price histories.",
        numbers=numbers,
        passed=passed,
        threshold=f"Pass: still above 0% without the best {pct:g}%",
        inputs={"pct": pct, "fingerprint": spec.fingerprint},
        summary=summary,
        chart={"type": "bars", "labels": ["median before", "median after", "mean before", "mean after"],
               "values": [before_med, after_med, before_mean, after_mean], "label": "typical and average, before and after"},
        kind=kind,
    )


# ------------------------------------------------------------------ A6 too many tries
def a6_trials(spec: RuleCard, a2: AttackResult, trials: int) -> AttackResult:
    trials = max(1, int(trials))
    p_perm = a2.numbers["p_perm"]
    p_adj = min(1.0, p_perm * trials)
    passed = p_adj < ALPHA
    numbers = {"trials": trials, "p_perm": p_perm, "p_adj": round(p_adj, 4), "bar": round(ALPHA / trials, 5)}
    summary = (
        f"You've tested {trials} version{'s' if trials != 1 else ''} of this idea. Every extra try makes a lucky hit "
        f"more likely, so the bar is now p < {numbers['bar']}. Your luck score after adjusting: {numbers['p_adj']:.4f}."
    )
    return AttackResult(
        id="A6",
        name="Too many tries",
        hypothesis="It isn't just the best of many attempts.",
        numbers=numbers,
        passed=passed,
        threshold=f"Pass: luck score × number of tries below {ALPHA}",
        inputs={"trials": trials, "fingerprint": spec.fingerprint},
        summary=summary,
        chart={},
    )


# ------------------------------------------------------------------ diagnostics menu (agent-selectable)
def d_regime_split(spec, paths, ev, by: str = "path_trend", buckets: int = 3) -> AttackResult:
    if by not in ("path_trend", "path_volatility"):
        raise ValueError("by must be path_trend or path_volatility")
    buckets = int(buckets)
    if not 2 <= buckets <= 5:
        raise ValueError("buckets must be 2..5")
    if by == "path_trend":
        key = [p.prices[-1] / p.prices[0] - 1 for p in paths]
    else:
        key = [float(np.std(np.diff(np.log(np.asarray(p.prices, dtype=float))))) for p in paths]
    order = np.argsort(key, kind="stable")
    groups = np.array_split(order, buckets)
    table = []
    if buckets == 3:
        names = ["falling", "flat", "rising"] if by == "path_trend" else ["calm", "normal", "wild"]
    else:
        names = [f"group {i + 1}" for i in range(buckets)]
    for name, g in zip(names, groups):
        rows = [ev.rows[i] for i in g]
        agg = aggregate(rows)
        table.append({"bucket": name, "paths": len(rows), "median_excess_bps": agg["median_excess_bps"],
                      "wins": agg["wins"], "losses": agg["losses"],
                      "sign_p": None if agg["sign_p"] is None else round(agg["sign_p"], 4),
                      "key_range": [round(float(key[g[0]]), 4), round(float(key[g[-1]]), 4)]})
    positive = sum(t["median_excess_bps"] > 0 for t in table)
    passed = positive == len(table)
    label = "direction" if by == "path_trend" else "how wild it was"
    summary = (f"Split into {buckets} groups by the market's {label}: typical result " +
               ", ".join(f"{t['bucket']} {_pc(t['median_excess_bps'])}" for t in table) +
               f". Beat holding in {positive} of {buckets} groups.")
    return AttackResult(
        id="", name="Rising, flat and falling markets" if by == "path_trend" else "Calm and wild markets",
        hypothesis="It works in more than one kind of market.",
        numbers={"by": by, "buckets": buckets, "positive_buckets": positive, "table": table}, passed=passed,
        threshold="Pass: beat holding in every group", inputs={"by": by, "buckets": buckets},
        summary=summary, kind="diagnostic",
        chart={"type": "bars", "labels": [t["bucket"] for t in table], "values": [t["median_excess_bps"] for t in table],
               "label": "typical result in each kind of market"},
    )


def d_subsample_folds(spec, paths, ev, k: int = 5, seed: int = config.SEEDS["folds"]) -> AttackResult:
    k = int(k)
    if not 2 <= k <= 10:
        raise ValueError("k must be 2..10")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(paths))
    folds = np.array_split(order, k)
    meds = [_median([ev.rows[i]["excess_bps"] for i in f]) for f in folds]
    positive = sum(m > 0 for m in meds)
    passed = positive == k
    summary = (f"We split the price histories into {k} random groups: it beat holding in {positive} of {k} (" +
               ", ".join(_pc(m) for m in meds) + ").")
    return AttackResult(
        id="", name="Consistency check", hypothesis="It works consistently, not just in part of the data.",
        numbers={"k": k, "fold_medians_bps": meds, "positive_folds": positive}, passed=passed,
        threshold="Pass: beat holding in every group", inputs={"k": k, "seed": seed}, summary=summary, kind="diagnostic",
        chart={"type": "bars", "labels": [f"fold {i + 1}" for i in range(k)], "values": meds, "label": "typical result in each group"},
    )


def d_exposure_check(spec, paths, ev) -> AttackResult:
    bars_in = sum(r["bars_in_position"] for r in ev.rows)
    decisions = sum(r["decisions"] for r in ev.rows)
    exposure = bars_in / decisions if decisions else 0.0
    s = np.asarray([r["strategy_return_bps"] for r in ev.rows], dtype=float)
    b = np.asarray([r["bh_return_bps"] for r in ev.rows], dtype=float)
    corr = float(np.corrcoef(s, b)[0, 1]) if len(s) > 2 and s.std() > 0 and b.std() > 0 else 0.0
    disguised = exposure >= 0.7 and corr >= 0.9
    numbers = {"exposure_pct": round(100 * exposure, 1), "return_correlation_with_bh": round(corr, 3),
               "median_excess_bps": _median(ev.excess), "buy_and_hold_in_disguise": disguised}
    summary = (f"Money invested {numbers['exposure_pct']}% of the time; its results move with plain holding at a "
               f"correlation of {numbers['return_correlation_with_bh']}." + (" It's mostly just holding in disguise." if disguised else ""))
    return AttackResult(
        id="", name="Just holding in disguise?", hypothesis="It's not just buying and holding with extra steps.",
        numbers=numbers, passed=not disguised, threshold="Pass: not (invested 70%+ of the time and moving with holding at 0.9+)",
        inputs={}, summary=summary, kind="diagnostic",
        chart={},
    )


def d_holding_sweep(spec, paths, ev, values=None) -> AttackResult:
    values = [int(v) for v in (values or [6, 12, 24, 48, 96])][:8]
    if any(not 1 <= v <= config.LIMITS["max_hold_bars"] for v in values):
        raise ValueError(f"holding values must be 1..{config.LIMITS['max_hold_bars']}")
    table = []
    for v in values:
        card = _variant(spec, [(("exit", "hold_bars"), v)])
        if card is None:
            continue
        table.append({"hold_bars": v, "median_excess_bps": _median(evaluate(card, paths).excess)})
    share = sum(t["median_excess_bps"] > 0 for t in table) / len(table) if table else 0.0
    passed = share >= config.GATE["wobble_min_share"]
    summary = "Typical result by holding time: " + ", ".join(f"{t['hold_bars']}h {_pc(t['median_excess_bps'])}" for t in table) + "."
    return AttackResult(
        id="", name="Holding-time check", hypothesis="It doesn't depend on one exact holding time.",
        numbers={"table": table, "share_positive_pct": round(100 * share, 1)}, passed=passed,
        threshold=f"Pass: at least {config.GATE['wobble_min_share']:.0%} of holding times beat holding",
        inputs={"values": values}, summary=summary, kind="diagnostic",
        chart={"type": "bars", "labels": [str(t["hold_bars"]) for t in table], "values": [t["median_excess_bps"] for t in table],
               "label": "typical result by holding time"},
    )


def d_cost_stress(spec, paths, ev, multiplier: int = 2) -> AttackResult:
    m = int(multiplier)
    if not 1 <= m <= 10:
        raise ValueError("multiplier must be 1..10")
    row = _cost_row(spec, paths, ev, m)
    return AttackResult(
        id="", name=f"Fees x{m} check", hypothesis="It survives higher trading costs.",
        numbers=row, passed=row["median_excess_bps"] > 0, threshold=f"Pass: above 0% at {m}x fees",
        inputs={"multiplier": m}, summary=f"Paying {m}x fees, the typical result is {_pc(row['median_excess_bps'])} vs holding.",
        kind="diagnostic", chart={"type": "bars", "labels": [f"x{m}"], "values": [row["median_excess_bps"]], "label": "typical result"},
    )


def d_outlier_drop(spec, paths, ev, pct: float = 10) -> AttackResult:
    pct = float(pct)
    if not 1 <= pct <= 25:
        raise ValueError("pct must be 1..25")
    return a5_outliers(spec, paths, ev, pct=pct, id_="", kind="diagnostic")


DIAGNOSTICS: dict[str, Callable] = {
    "regime_split": d_regime_split,
    "subsample_folds": d_subsample_folds,
    "exposure_check": d_exposure_check,
    "holding_sweep": d_holding_sweep,
    "cost_stress": d_cost_stress,
    "outlier_drop": d_outlier_drop,
}
DIAGNOSTIC_PARAMS = {
    "regime_split": {"by": ["path_trend", "path_volatility"], "buckets": "int 2..5"},
    "subsample_folds": {"k": "int 2..10"},
    "exposure_check": {},
    "holding_sweep": {"values": "list of 1..8 ints, each 1..240"},
    "cost_stress": {"multiplier": "int 1..10"},
    "outlier_drop": {"pct": "number 1..25"},
}


def run_diagnostic(tool: str, params: dict, spec: RuleCard, paths, ev: Evaluation, id_: str) -> AttackResult:
    if tool not in DIAGNOSTICS:
        raise ValueError(f"unknown diagnostic {tool!r}")
    allowed = set(DIAGNOSTIC_PARAMS[tool])
    params = {k: v for k, v in (params or {}).items() if k in allowed}
    res = DIAGNOSTICS[tool](spec, paths, ev, **params)
    res.id = id_
    res.inputs = {**res.inputs, "tool": tool, "fingerprint": spec.fingerprint}
    return res


# ------------------------------------------------------------------ battery + gate
def run_battery(spec: RuleCard, paths, trials: int = 1, k: int = config.PERM_K_DEFAULT) -> dict:
    paths = list(paths)
    ev = evaluate(spec, paths)
    a1 = a1_baseline(spec, paths, ev)
    a2 = a2_permutation(spec, paths, ev, k=k)
    a3 = a3_wobble(spec, paths, ev)
    a4 = a4_cost_stress(spec, paths, ev)
    a5 = a5_outliers(spec, paths, ev)
    a6 = a6_trials(spec, a2, trials)
    results = [a1, a2, a3, a4, a5, a6]
    return {"evaluation": ev, "results": results, "gate": practice_gate(results)}


def practice_gate(results: list[AttackResult]) -> dict:
    by = {r.id: r for r in results}
    a1 = by["A1"]
    checks = []
    trades = a1.numbers["total_trades"]
    checks.append({"id": "trades", "passed": trades >= config.GATE["min_trades"],
                   "text": f"Trades: {trades} (needs at least {config.GATE['min_trades']} to judge)."})
    p1 = a1.numbers["sign_p"]
    med1 = a1.numbers["median_excess_bps"]
    p_txt = "n/a" if p1 is None else f"{p1:.4f}"
    if a1.passed:
        a1_text = f"A1: beat holding, typical {_pc(med1)}, luck score {p_txt} (below {ALPHA})."
    else:
        parts = []
        if med1 <= 0:
            parts.append(f"typical result {_pc(med1)} vs holding (needs to be above 0%)")
        if p1 is None or p1 >= ALPHA:
            parts.append(f"luck score {p_txt} (needs below {ALPHA}: "
                         f"{a1.numbers['wins']} wins vs {a1.numbers['losses']} losses could be a coin flip)")
        a1_text = "A1: " + "; ".join(parts) + "."
    checks.append({"id": "A1", "passed": bool(a1.passed), "text": a1_text})
    a6 = by["A6"]
    checks.append({"id": "A6", "passed": bool(a6.passed),
                   "text": f"A2/A6 luck check: luck score {a6.numbers['p_adj']:.4f} after {a6.numbers['trials']} "
                           f"tr{'ies' if a6.numbers['trials'] != 1 else 'y'} (needs below {ALPHA})."})
    a4 = by["A4"]
    gm = config.GATE["cost_gate_multiplier"]
    checks.append({"id": "A4", "passed": bool(a4.passed),
                   "text": f"A4 higher fees: typical result at {gm}x fees is {_pc(a4.numbers[f'median_excess_x{gm}_bps'])} (needs above 0%)."})
    a3 = by["A3"]
    checks.append({"id": "A3", "passed": bool(a3.passed),
                   "text": f"A3 fragility: {a3.numbers['share_positive_pct']}% of {a3.numbers['neighbours']} variations beat "
                           f"holding (needs at least {config.GATE['wobble_min_share']:.0%})."})
    a5 = by["A5"]
    checks.append({"id": "A5", "passed": bool(a5.passed),
                   "text": f"A5 lucky streak: without the best {a5.numbers['dropped_paths']} price histories the typical result is "
                           f"{_pc(a5.numbers['median_after_bps'])} (needs above 0%)."})
    failing = [c for c in checks if not c["passed"]]
    if not checks[0]["passed"]:
        status = "INCONCLUSIVE"
        headline = "Too few trades to judge."
    elif failing:
        status = "REJECTED"
        headline = f"Failed {len(failing)} of {len(checks)} checks."
    else:
        status = "ELIGIBLE"
        headline = "Passed every check: the final exam is unlocked (one attempt)."
    return {"status": status, "vault_eligible": status == "ELIGIBLE", "headline": headline,
            "checks": checks, "failing": [c["text"] for c in failing], "thresholds": dict(config.GATE)}
