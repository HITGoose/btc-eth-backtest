import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from itertools import groupby
from math import sqrt
from statistics import median

from audit_gate_october import SEPTEMBER
from backtest_squeeze_short import HOUR
from combined_crypto_portfolio import WORK, close_enough
from compare_gate_strategies_by_year import OUTPUTS, add_readable_times, gate_run, summarize_gate_books
from extended_crypto_portfolio import local
from fit_gate_entry_overlay import (
    BASELINE, CURRENT_ENTRY_POLICY, LIVE_SEED, LIVE_WINDOW, OCTOBER_WINDOW, SEED,
    matches_live, price_books, run_exact, stacked_signals,
)
from fit_squeeze_ladder_bot import build
from gate_annual_market import MARKET_CACHE, PRICE_FILES, WINDOWS
from gate_october_regime_entries import DATA_END, market_schedules
from gate_public_data import save_json
from replay_gate_annual import PATH_ORDERS
from replay_gate_bot import PATHS
from replay_gate_regime_october import replay_with_refinement


POLICY = replace(CURRENT_ENTRY_POLICY, pause_transition=True)
PRIOR_REPORT = OUTPUTS / "BTC_ETH_Gate_regime_window_sensitivity_fixed_3x.json"
RESULT = OUTPUTS / "BTC_ETH_Gate_fast_window_sensitivity_fixed_3x.json"
METRICS = ("return_pct", "mdd_15m_pct", "mdd_1m_pct", "opens", "closed_trades", "wins", "losses", "hard_stops",
           "pnl_by_asset_usdt", "pnl_by_regime_usdt", "fills_by_regime", "execution_event_minutes", "quote_resolution_fallbacks")


def candidate_pairs():
    pairs = {}
    for slow, slow_threshold in ((120, 0.10), (72, 0.10 * sqrt(120 / 72))):
        for fast in (24, 12, 6):
            slow_setting = (slow, slow_threshold)
            pairs[f"{fast}h_{slow}h_fixed"] = ((fast, 0.20), slow_setting)
            if fast < 24:
                pairs[f"{fast}h_{slow}h_scaled"] = ((fast, 0.20 * sqrt(24 / fast)), slow_setting)
    return pairs


def prepare(files, legs, name, pair, *, policy=POLICY, use_entry_crosses=False):
    prepared = {}
    for asset, path in files.items():
        leg = legs[asset]
        schedules, context = market_schedules(asset, leg, price_file=WORK / path, include_gate_confirmation=True,
                                             regime_thresholds=pair, use_entry_crosses=use_entry_crosses)
        base = schedules[BASELINE]
        eligible = stacked_signals(base, context, policy)
        assert eligible.items() <= base.items()
        prepared[asset] = leg, {name: eligible}, context
    return prepared


def transition_coverage(prepared, start, end):
    runs = []
    for _, _, context in prepared.values():
        labels = (context[t]["regime"] for t in range(start, end, HOUR))
        runs.extend(sum(1 for _ in run) for state, run in groupby(labels) if state == "transition")
    total_hours = (end - start) // HOUR * len(prepared)
    return {"time_pct": 100 * sum(runs) / total_hours, "median_hours": median(runs) if runs else 0,
            "max_hours": max(runs, default=0)}


def check_reference(prior, year, name, order, results):
    if year == 2019 and name == "24h_120h_fixed":
        expected = prior["cases"]["24h_120h"]["annual"]["2019"]["executions"][order]
    elif year == 2026 and name == "24h_72h_fixed":
        expected = prior["slow_threshold_scale_check"]["cases"]["72"]["scaled"]["replays"][order]
    else:
        return
    close_enough(results["return_pct"], expected["return_pct"])
    assert results["opens"] == expected["opens"]


def annual_cases(cases, pairs, prior, pool):
    market = json.loads((MARKET_CACHE / "prepared_market.json").read_text(encoding="utf-8"))
    for year in (2019, 2026):
        start, end = WINDOWS[year]
        warm_start = start if year == 2019 else start - 30 * 24 * HOUR
        legs = {a: build(path, warm_start, end) for a, path in PRICE_FILES.items()}
        for name, pair in pairs.items():
            prepared = prepare(PRICE_FILES, legs, name, pair)
            coverage = transition_coverage(prepared, start, end)
            executions = {}
            for order in PATH_ORDERS if year == 2026 else PATH_ORDERS[:1]:
                q = gate_run(year, name, order, market, prepared, pool, use_cached_prints=False)
                assert not any(q["quote_resolution_fallbacks"].values())
                check_reference(prior, year, name, order, q)
                executions[order] = {k: q[k] for k in METRICS}
            cases[name]["annual"][year] = {"window_local": [local(start), local(end)], "transition_coverage": coverage,
                                            "executions": executions}
            print(year, name, f"transition {coverage['time_pct']:.2f}% max {coverage['max_hours']}h",
                  [(round(r["return_pct"], 2), round(r["mdd_15m_pct"], 2), r["opens"]) for r in executions.values()], flush=True)


def recent_cases(cases, pairs, prior, pool):
    legs = {a: build(path, SEPTEMBER, DATA_END) for a, path in PATHS.items()}
    prepared = {name: prepare(PATHS, legs, name, pair) for name, pair in pairs.items()}
    books = dict(zip(PATHS, pool.map(price_books, PATHS), strict=True))
    live = {a: b[1] for a, b in books.items()}
    for name in pairs:
        stats = run_exact(prepared[name], live, LIVE_WINDOW, LIVE_SEED, pool, mode=name)
        assert not any(stats["quote_resolution_fallbacks"].values())
        matches = matches_live(stats, prepared[name], name)
        if name in ("24h_120h_fixed", "24h_72h_fixed"):
            assert matches["matching_entries_price_and_second"] == 5
        cases[name]["november_exact"] = {"statistics": stats, "comparison": matches}
        print("NOV", name, matches["matching_entries_price_and_second"], matches["other_simulated_entries"], flush=True)

    oct_books = {a: (legs[a], {name: p[a][1][name] for name, p in prepared.items()}, None, b[0]) for a, b in books.items()}
    raw, refinement = replay_with_refinement(oct_books, pairs)
    for name, p in prepared.items():
        stats = summarize_gate_books({a: raw[a][name] for a in raw}, {a: t[2] for a, t in p.items()}, *OCTOBER_WINDOW, SEED)
        if name == "24h_120h_fixed":
            close_enough(stats["return_pct"], prior["cases"]["24h_120h"]["october_exact"]["stats"]["return_pct"])
        cases[name]["october"] = stats
        print("OCT", name, stats["opens"], round(stats["return_pct"], 2), round(stats["mdd_15m_pct"], 2),
              stats["wins"], stats["losses"], {a: len(v) for a, v in stats["quote_resolution_fallbacks"].items()}, flush=True)
    return refinement


def main():
    prior = json.loads(PRIOR_REPORT.read_text(encoding="utf-8"))
    pairs = candidate_pairs()
    cases = {name: {"er_windows_and_thresholds": pair, "annual": {}} for name, pair in pairs.items()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        annual_cases(cases, pairs, prior, pool)
        refinement = recent_cases(cases, pairs, prior, pool)
    doc = {"nominal_leverage": 3.0, "starting_usdt_per_asset": 500, "policy": asdict(POLICY), "cases": cases,
           "fast_threshold_scaling": "0.20 * sqrt(24 / fast_window_hours) for the scaled cases",
           "annual_execution": "2019 December prints and 2026 uniform Gate 10s OHLC, no cached trade minutes in the 2026 annual comparisons.",
           "october_window_local": [local(t) for t in OCTOBER_WINDOW], "october_tape_refinement": refinement,
           "november_window_local": [local(t) for t in LIVE_WINDOW]}
    add_readable_times(doc)
    save_json(RESULT, doc)


if __name__ == "__main__":
    main()
