import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from math import isclose

from audit_gate_october import END, OCTOBER, SEPTEMBER, archived_months
from backtest_squeeze_short import TREND_THRESHOLDS
from combined_crypto_portfolio import BAR, WORK, close_enough, ms
from compare_gate_strategies_by_year import (
    ASSETS, BOT_SEED, OUTPUTS, add_readable_times, entry_comparison, gate_run, summarize_gate_books,
)
from extended_crypto_portfolio import local
from fit_squeeze_ladder_bot import build
from gate_annual_market import EARLIEST_START, MARKET_CACHE, PRICE_FILES, WINDOWS
from gate_october_regime_entries import DATA_END, DIRECTIONS, market_schedules
from gate_public_data import candles, save_json
from replay_formal_bot_trades import FILLS
from replay_gate_annual import PATH_ORDERS
from replay_gate_bot import ENTRY, PATHS, GateMinutes, gate_quotes, short_ladder
from replay_gate_october_seconds import POLL_PHASE_SECONDS, replay_asset
from replay_gate_regime_october import replay_with_refinement


BASELINE = "baseline"
SIX_LINES = "six_lines"
STRICT_STACK = "strict_stack"
OVERLAY = "regime_overlay"
BOOSTED = "regime_overlay_with_divergence_sizing"
PREVIOUS_INDEPENDENT = "previous_independent"
OCTOBER_WINDOW = (OCTOBER, END)
LIVE_WINDOW = (ms("2026-11-09T00:00:00+08:00"), DATA_END)
SEED = dict.fromkeys(ASSETS, BOT_SEED / 2)
LIVE_SEED = {a: next(f.prior_sleeve_balance for f in FILLS if f.asset == a) for a in ASSETS}
DIVERGENCE_SIZE_MULTIPLIER = 1.25
PRIOR = OUTPUTS / "BTC_ETH_Gate_regime_annual_trade_comparison_2019_2026.json"


@dataclass(frozen=True)
class RegimeOverlay:
    range_squeeze_pct: float
    range_entry_bandwidth_pct: float | None
    trend_level_distance_pct: float = 2.0
    pause_transition: bool = False


CURRENT_ENTRY_POLICY = RegimeOverlay(0.25, 0.50)


def stacked_signals(original, context, policy, *, min_aligned_lines=6):
    result = {}
    for stamp, side in original.items():
        state = context[stamp]["regime"]
        gate = context[stamp]["gate_confirmation"]
        if gate["aligned_lines"] < min_aligned_lines:
            continue
        if state == "range":
            width_cap = policy.range_entry_bandwidth_pct
            eligible = (gate["minimum_bandwidth_pct"] <= policy.range_squeeze_pct and
                        (width_cap is None or gate["entry_bandwidth_pct"] <= width_cap))
        elif state == "transition":
            eligible = not policy.pause_transition
        elif DIRECTIONS.get(state) == side:
            distance = gate["distance_to_confirmed_hourly_level_pct"]
            near_level = distance is not None and distance <= policy.trend_level_distance_pct
            eligible = (gate["short_term_alignment"] and
                        (near_level or gate["directional_volume_breakout"] or gate["confirmed_retest"]))
        else:
            eligible = False
        if eligible:
            result[stamp] = side
    return result


def divergence_sizes(schedule, context):
    return {stamp: DIVERGENCE_SIZE_MULTIPLIER for stamp in schedule
            if context[stamp]["regime"] == "range" and context[stamp]["gate_confirmation"]["confirmed_divergence_legs"] >= 2}


def price_books(asset):
    quote = gate_quotes(asset)["last"]
    start, end = (v // 1000 for v in LIVE_WINDOW)
    quote.update(candles(asset + "_USDT", start - 60, min(quote), "1m"))
    quote.update(candles(asset + "_USDT", max(quote) + 60, end, "1m"))
    return GateMinutes(asset, archived_months(asset), download_missing=False), GateMinutes(asset, quote)


def run_exact(prepared, books, window, seeds, pool, *, mode, sizes=None, poll_seconds=5, poll_phase=POLL_PHASE_SECONDS):
    start, end = window
    sizes = {} if sizes is None else sizes
    jobs = {a: pool.submit(replay_asset, a, leg=prepared[a][0], signals=prepared[a][1][mode], market=books[a], print_progress=False,
                           start=start, end=end, starting_cash=seeds[a], size_multipliers=sizes.get(a),
                           poll_seconds=poll_seconds, poll_phase=poll_phase) for a in ASSETS}
    results = {a: job.result() for a, job in jobs.items()}
    return summarize_gate_books(results, {a: prepared[a][2] for a in ASSETS}, start, end, seeds)


def matches_live(result, prepared, mode):
    rows = []
    for fill in sorted(FILLS, key=lambda f: f.opened):
        stamp = ms(fill.signal_time)
        schedule, context = prepared[fill.asset][1:]
        match = next((row for row in result["trades"] if row["asset"] == fill.asset and row["side"] == "SHORT"
                      and row["entry"] == fill.entry and row["opened_ms"] // 1000 == ms(fill.opened) // 1000), None)
        rows.append({"recorded": asdict(fill), "signal_at_notification": schedule[mode].get(stamp) == -1,
                     "regime_at_notification": context[stamp]["regime"], "conditions_at_notification": context[stamp].get("gate_confirmation"),
                     "matched_simulated_trade": match,
                     "same_quantity": bool(match and isclose(match["opening_notional_usdt"] / match["entry"], fill.quantity)),
                     "close_trigger_seconds_from_record": (match["closed_ms"] - ms(fill.closed)) / 1000 if match else None})
    matched = sum(r["matched_simulated_trade"] is not None for r in rows)
    return {"matching_entries_price_and_second": matched, "observed_signal_slots_eligible": sum(r["signal_at_notification"] for r in rows),
            "other_simulated_entries": len(result["trades"]) - matched, "comparison": rows}


def fit_score(case, target):
    oct_stats, live = case["october"], case["live_entry_comparison"]
    approximations = any(oct_stats["quote_resolution_fallbacks"].values()) or any(case["live"]["quote_resolution_fallbacks"].values())
    return (approximations, -live["matching_entries_price_and_second"], live["other_simulated_entries"],
            sum(abs(oct_stats["opens"][a] - target["opens"][a]) for a in ASSETS),
            abs(oct_stats["wins"] - target["wins"]) + abs(oct_stats["losses"] - target["losses"]),
            abs(oct_stats["return_pct"] - target["return_pct"]))


def replay_case(prepared, october_books, live_books, pool, mode, *, sizes=None, poll_seconds=5, poll_phase=POLL_PHASE_SECONDS,
                october=None):
    timing = {"poll_seconds": poll_seconds, "poll_phase": poll_phase}
    if october is None:
        october = run_exact(prepared, october_books, OCTOBER_WINDOW, SEED, pool, mode=mode, sizes=sizes, **timing)
    live = run_exact(prepared, live_books, LIVE_WINDOW, LIVE_SEED, pool, mode=mode, sizes=sizes, **timing)
    live_comparison = matches_live(live, prepared, mode)
    print(mode, timing, "Oct", october["opens"], (october["wins"], october["losses"]), round(october["return_pct"], 2),
          "Nov", live_comparison["matching_entries_price_and_second"], "other", live_comparison["other_simulated_entries"], flush=True)
    return {"october": october, "live": live, "live_entry_comparison": live_comparison}


def recorded_ladder_checks(live_books):
    old = json.loads((OUTPUTS / "BTC_ETH_Gate_live_v13_audit.json").read_text(encoding="utf-8"))
    entries = {(r["fill"]["asset"], r["fill"]["entry"]): r["entry_same_second_same_price"] for r in old["fills"]}
    periods = {}
    for period in (3, 4, 5):
        periods[str(period)] = phases = {}
        for phase in range(period):
            rows = {}
            for f in FILLS:
                prints = entries[f.asset, f.entry]
                first = next(iter(prints["same_lot_prints_local"]), prints["first_local"] or f.opened)
                rows[f.key] = short_ladder(f, live_books[f.asset], phase=phase, filled_at=ms(first) / 1000, poll_seconds=period)
            matches = [f.key for f in FILLS if (row := rows[f.key]) and row["rung"] == (f.rung or 1)
                       and abs(row["seconds_after_recorded_close"]) <= 2]
            phases[str(phase)] = {"matches": matches, "triggers": rows}
    return periods


def prepare_schedules(asset, start, end, path, policies, *, regime_thresholds=TREND_THRESHOLDS):
    leg = build(path, start, end)
    old, context = market_schedules(asset, leg, price_file=WORK / path, include_gate_confirmation=True,
                                    regime_thresholds=regime_thresholds)
    base = old[BASELINE]
    schedules = {BASELINE: base, PREVIOUS_INDEPENDENT: old["range_double_trend_retest"],
                 SIX_LINES: {t: side for t, side in base.items() if context[t]["gate_confirmation"]["aligned_lines"] >= 6},
                 STRICT_STACK: {t: side for t, side in base.items() if old["range_double_trend_retest"].get(t) == side}}
    schedules.update({name: stacked_signals(base, context, p) for name, p in policies.items()})
    for name in schedules.keys() - {PREVIOUS_INDEPENDENT}:
        assert schedules[name].items() <= base.items(), name
    return leg, schedules, context


def annual_tests(policy, previous, pool):
    market = json.loads((MARKET_CACHE / "prepared_market.json").read_text(encoding="utf-8"))
    prepared = {a: prepare_schedules(a, EARLIEST_START, END, path, {OVERLAY: policy}) for a, path in PRICE_FILES.items()}
    sizes = {a: divergence_sizes(s[OVERLAY], c) for a, (_, s, c) in prepared.items()}
    annual = {}
    for year, (start, end) in WINDOWS.items():
        old = previous["annual"][str(year)]
        prior_independent = old["gate_models"]["range_double_trend_retest"]["adverse_first"]
        original = old["our_original_same_gate"]
        results = {order: gate_run(year, OVERLAY, order, market, prepared, pool, size_multipliers=sizes) for order in PATH_ORDERS}
        base = gate_run(year, BASELINE, PATH_ORDERS[0], market, prepared, pool)
        plain = gate_run(year, OVERLAY, PATH_ORDERS[0], market, prepared, pool)
        adjusted = results[PATH_ORDERS[0]]
        count_outside_base = sum(prepared[r["asset"]][1][BASELINE].get(r["signal_ms"]) != (1 if r["side"] == "LONG" else -1)
                                 for r in prior_independent["trades"])
        assert all(prepared[r["asset"]][1][BASELINE][r["signal_ms"]] == (1 if r["side"] == "LONG" else -1)
                   for result in results.values() for r in result["trades"])
        boosted = [r for r in adjusted["trades"] if r["signal_ms"] in sizes[r["asset"]]]
        original_totals = {k: v for k, v in original.items() if k != "trades"}
        annual[year] = {"window_local": [local(start), local(end)], "stacked": results, "gate_base_same_prices": base,
                        "stacked_without_sizing_overlay": {k: v for k, v in plain.items() if k != "trades"},
                        "our_original_same_gate_from_prior_run": original_totals,
                        "stacked_vs_our_original": entry_comparison(adjusted, original),
                        "stacked_vs_gate_base": entry_comparison(adjusted, base),
                        "sized_divergence_entries": len(boosted), "previous_independent_fills": len(prior_independent["trades"]),
                        "previous_independent_fills_outside_core_signal": count_outside_base}
        print(year, "stack", adjusted["opens"], round(adjusted["return_pct"], 2), "base", base["opens"], round(base["return_pct"], 2),
              "old outside core", count_outside_base, flush=True)
    return annual


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recent-only", action="store_true")
    args = parser.parse_args()
    policies = {f"range_{t}_width_{m}": RegimeOverlay(t, m, pause_transition=True)
                for t in (0.15, 0.20, 0.25) for m in (0.25, 0.375, 0.50, None)}
    policies["one_pct_level"] = RegimeOverlay(0.25, 0.50, 1.0, pause_transition=True)
    policies["three_pct_level"] = RegimeOverlay(0.25, 0.50, 3.0, pause_transition=True)
    previous = json.loads(PRIOR.read_text(encoding="utf-8"))
    expected = json.loads((OUTPUTS / "BTC_ETH_Gate_v13_October_2026_seconds.json").read_text(encoding="utf-8"))
    prepared = {a: prepare_schedules(a, SEPTEMBER, DATA_END, path, policies) for a, path in PATHS.items()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        sources = dict(zip(ASSETS, pool.map(price_books, ASSETS), strict=True))
        october_books = {a: books[0] for a, books in sources.items()}
        live_books = {a: books[1] for a, books in sources.items()}
        modes = (BASELINE, PREVIOUS_INDEPENDENT, SIX_LINES, STRICT_STACK, *policies)
        october_tapes, refinement = replay_with_refinement({a: (*prepared[a], october_books[a]) for a in ASSETS}, modes)
        contexts = {a: prepared[a][2] for a in ASSETS}
        cases = {name: replay_case(prepared, october_books, live_books, pool, name, october=summarize_gate_books(
            {a: october_tapes[a][name] for a in ASSETS}, contexts, *OCTOBER_WINDOW, SEED)) for name in modes}
        close_enough(cases[BASELINE]["october"]["return_pct"], expected["month"]["return_pct"])
        assert cases[BASELINE]["october"]["opens"] == expected["month"]["opens"]
        selected_name = min(policies, key=lambda name: fit_score(cases[name], expected["target"]))
        selected = policies[selected_name]
        print("Selected", selected_name, asdict(selected), flush=True)
        for _, schedules, _ in prepared.values():
            schedules[BOOSTED] = schedules[selected_name]
        sizes = {a: divergence_sizes(s[BOOSTED], c) for a, (_, s, c) in prepared.items()}
        periods = recorded_ladder_checks(live_books)
        for book in october_books.values():
            book.download_missing = True
        timing_cases = {f"{period}s_phase{phase}": replay_case(prepared, october_books, live_books, pool, BOOSTED, sizes=sizes,
                                                               poll_seconds=period, poll_phase=phase)
                        for period, phase in ((3, 0), (4, 1), (4, 2), (5, 2), (5, 4))}
        annual = None if args.recent_only else annual_tests(selected, previous, pool)
    doc = {"october_window_local": [local(t) for t in OCTOBER_WINDOW], "november_replay_window_local": [local(t) for t in LIVE_WINDOW],
           "october_screenshot_target": expected["target"], "november_starting_cash_usdt": LIVE_SEED,
           "baseline_signal": ENTRY.key, "core_eligibility": "Every stacked entry must have the original six-MA compression/expansion and same-side MACD signal.",
           "trend_confirmation": "Six aligned lines. Confirmed direction plus aligned MA5/MA20 and MACD; within tested distance of the hourly level, or directional 8h breakout on 1.5x past-20 median volume, or confirmed retest.",
           "range_confirmation": "Six aligned lines plus the tested 24h minimum and current bandwidth limits; same-side confirmed divergence only scales size.",
           "transition": "Wait for a range or confirmed trend.", "divergence_size_multiplier_assumption": DIVERGENCE_SIZE_MULTIPLIER,
           "selection": "Minimize missing public-tape entry matches and other simulated November fills, then October count discrepancy per asset, then win/loss discrepancy and return discrepancy. Exclude fallback timing when exact data is available.",
           "selected_name": selected_name, "selected_policy": asdict(selected), "tested_policies": {k: asdict(v) for k, v in policies.items()},
           "exact_recent_comparison": cases, "october_tape_refinement": refinement, "recorded_fills_exit_poll_checks": periods,
           "exact_tape_poll_sensitivity": timing_cases, "annual": annual,
           "annual_execution": "5s polling on modeled Gate 10s OHLC paths, except verified recent prints and the December 2019 trade archive. OHLC order cases are sensitivities. Starting from 500 USDT per asset each year.",
           "annual_previous_original_trade_journal": str(PRIOR)}
    add_readable_times(doc)
    save_json(OUTPUTS / "BTC_ETH_Gate_v13_stacked_entry_replay.json", doc)


if __name__ == "__main__":
    main()
