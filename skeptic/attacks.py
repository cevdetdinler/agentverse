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
        f"Across {agg['paths']} practice paths: {agg['wins']} wins, {agg['losses']} losses, {agg['ties']} ties vs "
        f"buy-and-hold. Median excess {agg['median_excess_bps']} bps (95% CI {lo} to {hi}); sign-test p = {p_txt}; "
        f"{agg['total_trades']} trades; in the market {exposure_pct}% of bars."
    )
    return AttackResult(
        id="A1",
        name="Baseline backtest",
        hypothesis="The rule beats buy-and-hold after real fees and slippage more often than chance.",
        numbers=numbers,
        passed=passed,
        threshold=f"median excess > 0 and sign-test p < {ALPHA}",
        inputs={"paths": len(paths), "bootstrap_resamples": config.BOOTSTRAP_RESAMPLES, "seed": seed,
                "fingerprint": spec.fingerprint},
        summary=summary,
        chart={**_hist(ev.excess), "label": "excess vs buy-and-hold per path (bps)", "marker": agg["median_excess_bps"]},
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
        f"We rebuilt every practice path {k} times from its own price moves in random order (same start, end and "
        f"volatility, but no timing information) and reran the exact rule. The shuffled markets did at least as well "
        f"as the real ones in {exceed} of {k} cases (p_perm = {p_perm:.4f}). Real mean excess {observed:.1f} bps vs a "
        f"typical shuffled {numbers['perm_mean_excess_median_bps']} bps."
    )
    return AttackResult(
        id="A2",
        name="Shuffled-returns test",
        hypothesis="The rule profits from the ORDER of price moves (real timing information), not from luck.",
        numbers=numbers,
        passed=passed,
        threshold=f"p_perm < {ALPHA} (before the too-many-tries adjustment in A6)",
        inputs={"K": k, "seed": seed, "paths": len(paths), "fingerprint": spec.fingerprint,
                "null": "one-bar log returns shuffled within each path"},
        summary=summary,
        chart={**_hist(perm_means.tolist()), "label": "mean excess on shuffled-return markets (bps)", "marker": round(observed, 1)},
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
        f"Nudging each parameter by up to ±30% gave {len(meds)} neighbouring rules; "
        f"{numbers['share_positive_pct']}% of them still had a positive median excess. Your rule ranks "
        f"{rank} of {len(meds) + 1}." + (" Knife-edge: the result depends on the exact settings." if not passed else "")
    )
    return AttackResult(
        id="A3",
        name="Wobble (parameter sensitivity)",
        hypothesis="The edge is a broad plateau, not a lucky spike at one exact setting.",
        numbers=numbers,
        passed=passed,
        threshold=f">= {config.GATE['wobble_min_share']:.0%} of neighbours with median excess > 0 (diagnostic only: Skeptic never swaps in a better neighbour)",
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
        "If the rule paid double fees and slippage (buy-and-hold at real costs) its median excess would be "
        f"{at_gate['median_excess_bps']} bps; tripled it is {rows[-1]['median_excess_bps']} bps "
        f"(at real costs: {rows[0]['median_excess_bps']} bps)."
    )
    return AttackResult(
        id="A4",
        name="Cost stress",
        hypothesis="The edge survives if trading is more expensive than the data assumes.",
        numbers=numbers,
        passed=passed,
        threshold=f"median excess > 0 when the rule pays fees x{gate_m} and slippage x{gate_m} (buy-and-hold keeps real costs)",
        inputs={"multipliers": [1, *config.COST_MULTIPLIERS], "fingerprint": spec.fingerprint},
        summary=summary,
        chart={"type": "bars", "labels": [f"x{r['multiplier']}" for r in rows], "values": [r["median_excess_bps"] for r in rows],
               "label": "median excess (bps) by cost multiplier"},
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
        f"Dropping the best {dropped} paths (top {pct:g}%) moves the median from {before_med} to {after_med} bps "
        f"and the mean from {before_mean} to {after_mean} bps."
    )
    return AttackResult(
        id=id_,
        name="Outlier dependence" if kind == "fixed" else f"Outlier drop ({pct:g}%)",
        hypothesis="The result is not carried by a handful of lucky paths.",
        numbers=numbers,
        passed=passed,
        threshold=f"median excess stays > 0 after dropping the top {pct:g}% of paths",
        inputs={"pct": pct, "fingerprint": spec.fingerprint},
        summary=summary,
        chart={"type": "bars", "labels": ["median before", "median after", "mean before", "mean after"],
               "values": [before_med, after_med, before_mean, after_mean], "label": "bps"},
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
        f"You have tested {trials} distinct version{'s' if trials != 1 else ''} of this idea, so the bar is "
        f"p < {numbers['bar']}. Adjusted p = {numbers['p_adj']:.4f} (Bonferroni: p_perm × trials)."
    )
    return AttackResult(
        id="A6",
        name="Too many tries",
        hypothesis="The result is not just the best of many attempts.",
        numbers=numbers,
        passed=passed,
        threshold=f"p_adj = min(1, p_perm × trials) < {ALPHA}",
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
    names = ["lowest", "middle", "highest"] if buckets == 3 else [f"q{i + 1}" for i in range(buckets)]
    for name, g in zip(names, groups):
        rows = [ev.rows[i] for i in g]
        agg = aggregate(rows)
        table.append({"bucket": name, "paths": len(rows), "median_excess_bps": agg["median_excess_bps"],
                      "wins": agg["wins"], "losses": agg["losses"],
                      "sign_p": None if agg["sign_p"] is None else round(agg["sign_p"], 4),
                      "key_range": [round(float(key[g[0]]), 4), round(float(key[g[-1]]), 4)]})
    positive = sum(t["median_excess_bps"] > 0 for t in table)
    passed = positive == len(table)
    label = "trend" if by == "path_trend" else "volatility"
    summary = (f"Split by path {label} into {buckets} groups: median excess " +
               ", ".join(f"{t['bucket']} {t['median_excess_bps']} bps" for t in table) +
               f". Positive in {positive} of {buckets} groups.")
    return AttackResult(
        id="", name=f"Regime split by {label}", hypothesis="The edge is not confined to one kind of market.",
        numbers={"by": by, "buckets": buckets, "positive_buckets": positive, "table": table}, passed=passed,
        threshold="median excess > 0 in every group", inputs={"by": by, "buckets": buckets},
        summary=summary, kind="diagnostic",
        chart={"type": "bars", "labels": [t["bucket"] for t in table], "values": [t["median_excess_bps"] for t in table],
               "label": f"median excess by path {label} (bps)"},
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
    summary = f"In {k} random folds of the practice paths, the median excess was positive in {positive} of {k} (" + \
        ", ".join(f"{m}" for m in meds) + " bps)."
    return AttackResult(
        id="", name=f"Subsample folds (k={k})", hypothesis="The sign of the edge is consistent across subsets of paths.",
        numbers={"k": k, "fold_medians_bps": meds, "positive_folds": positive}, passed=passed,
        threshold="median excess > 0 in every fold", inputs={"k": k, "seed": seed}, summary=summary, kind="diagnostic",
        chart={"type": "bars", "labels": [f"fold {i + 1}" for i in range(k)], "values": meds, "label": "median excess per fold (bps)"},
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
    summary = (f"In the market {numbers['exposure_pct']}% of bars; per-path returns correlate {numbers['return_correlation_with_bh']} "
               f"with buy-and-hold." + (" This looks like buy-and-hold in disguise." if disguised else ""))
    return AttackResult(
        id="", name="Exposure check", hypothesis="The rule is not just buy-and-hold in disguise.",
        numbers=numbers, passed=not disguised, threshold="not (exposure >= 70% and correlation >= 0.9)",
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
    summary = "Median excess by holding period: " + ", ".join(f"{t['hold_bars']} bars {t['median_excess_bps']} bps" for t in table) + "."
    return AttackResult(
        id="", name="Holding-period sweep", hypothesis="The edge does not hinge on one holding period.",
        numbers={"table": table, "share_positive_pct": round(100 * share, 1)}, passed=passed,
        threshold=f">= {config.GATE['wobble_min_share']:.0%} of holding periods with median excess > 0",
        inputs={"values": values}, summary=summary, kind="diagnostic",
        chart={"type": "bars", "labels": [str(t["hold_bars"]) for t in table], "values": [t["median_excess_bps"] for t in table],
               "label": "median excess by hold_bars (bps)"},
    )


def d_cost_stress(spec, paths, ev, multiplier: int = 2) -> AttackResult:
    m = int(multiplier)
    if not 1 <= m <= 10:
        raise ValueError("multiplier must be 1..10")
    row = _cost_row(spec, paths, ev, m)
    return AttackResult(
        id="", name=f"Cost stress x{m}", hypothesis="The edge survives higher trading costs.",
        numbers=row, passed=row["median_excess_bps"] > 0, threshold=f"median excess > 0 at fees and slippage x{m}",
        inputs={"multiplier": m}, summary=f"At fees and slippage x{m} the median excess is {row['median_excess_bps']} bps.",
        kind="diagnostic", chart={"type": "bars", "labels": [f"x{m}"], "values": [row["median_excess_bps"]], "label": "bps"},
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
                   "text": f"Total trades {trades} (needs at least {config.GATE['min_trades']})."})
    p1 = a1.numbers["sign_p"]
    med1 = a1.numbers["median_excess_bps"]
    p_txt = "n/a" if p1 is None else f"{p1:.4f}"
    if a1.passed:
        a1_text = f"A1: median excess {med1} bps > 0 and sign-test p = {p_txt} < {ALPHA}."
    else:
        parts = []
        if med1 <= 0:
            parts.append(f"median excess {med1} bps (needs > 0)")
        if p1 is None or p1 >= ALPHA:
            parts.append(f"sign-test p = {p_txt} (needs < {ALPHA}: "
                         f"{a1.numbers['wins']} wins vs {a1.numbers['losses']} losses could be chance)")
        a1_text = "A1: " + "; ".join(parts) + "."
    checks.append({"id": "A1", "passed": bool(a1.passed), "text": a1_text})
    a6 = by["A6"]
    checks.append({"id": "A6", "passed": bool(a6.passed),
                   "text": f"A6: adjusted permutation p = {a6.numbers['p_adj']:.4f} after {a6.numbers['trials']} "
                           f"tr{'ies' if a6.numbers['trials'] != 1 else 'y'} (needs < {ALPHA})."})
    a4 = by["A4"]
    gm = config.GATE["cost_gate_multiplier"]
    checks.append({"id": "A4", "passed": bool(a4.passed),
                   "text": f"A4: median excess with costs x{gm} is {a4.numbers[f'median_excess_x{gm}_bps']} bps (needs > 0)."})
    a3 = by["A3"]
    checks.append({"id": "A3", "passed": bool(a3.passed),
                   "text": f"A3: {a3.numbers['share_positive_pct']}% of {a3.numbers['neighbours']} neighbouring rules were "
                           f"positive (needs at least {config.GATE['wobble_min_share']:.0%})."})
    a5 = by["A5"]
    checks.append({"id": "A5", "passed": bool(a5.passed),
                   "text": f"A5: without the best {a5.numbers['dropped_paths']} paths the median is "
                           f"{a5.numbers['median_after_bps']} bps (needs > 0)."})
    failing = [c for c in checks if not c["passed"]]
    if not checks[0]["passed"]:
        status = "INCONCLUSIVE"
        headline = "Too few trades to judge."
    elif failing:
        status = "REJECTED"
        headline = f"Failed {len(failing)} of {len(checks)} practice checks."
    else:
        status = "ELIGIBLE"
        headline = "Passed every practice check: eligible for the one-shot vault."
    return {"status": status, "vault_eligible": status == "ELIGIBLE", "headline": headline,
            "checks": checks, "failing": [c["text"] for c in failing], "thresholds": dict(config.GATE)}
