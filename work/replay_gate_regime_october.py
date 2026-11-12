import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import fsum

from audit_gate_october import END, OCTOBER, SEPTEMBER, archived_months
from combined_crypto_portfolio import BAR, WORK, close_enough, ms
from extended_crypto_portfolio import local
from fit_squeeze_ladder_bot import build, tick_time
from gate_october_regime_entries import DATA_END, RULES, market_schedules
from gate_public_data import save_json, trades
from replay_formal_bot_trades import FILLS
from replay_gate_bot import PATHS, GateMinutes
from replay_gate_october_seconds import replay_asset


OUTPUTS = WORK.parent / "outputs"
BASELINE_REPORT = OUTPUTS / "BTC_ETH_Gate_v13_October_2026_seconds.json"


def prepare(asset):
    leg = build(PATHS[asset], SEPTEMBER, DATA_END)
    schedules, context = market_schedules(asset, leg)
    market = GateMinutes(asset, archived_months(asset), download_missing=False)
    return leg, schedules, context, market


def run_modes(asset, prepared, modes):
    leg, schedules, _, market = prepared
    return {mode: replay_asset(asset, leg=leg, signals=schedules[mode], market=market, print_progress=False)
            for mode in modes}


def fill_cache(task):
    asset, minute = task
    try:
        trades(f"{asset}_USDT", minute, minute + 60)
    except (ValueError, OSError) as error:
        return str(error)
    return None


def replay_with_refinement(prepared, modes):
    tried = set()
    failures = {}
    progress = []
    for iteration in range(8):
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {asset: pool.submit(run_modes, asset, data, modes) for asset, data in prepared.items()}
            results = {asset: job.result() for asset, job in jobs.items()}
        missing = {(asset, minute) for asset, by_mode in results.items() for row in by_mode.values()
                   for minute in row.get("missing_trade_minutes", [])}
        pending = sorted(missing - tried)
        print(f"Pass {iteration + 1}: {len(missing)} unresolved trade minutes, {len(pending)} new", flush=True)
        if not pending or iteration == 7:
            break
        tried.update(pending)
        with ThreadPoolExecutor(max_workers=6) as pool:
            errors = list(pool.map(fill_cache, pending))
        failures.update({f"{asset} {tick_time(minute)}": error for (asset, minute), error in zip(pending, errors) if error})
        progress.append({"requested": len(pending), "downloaded": sum(e is None for e in errors)})
    return results, {"rounds": progress, "download_errors": failures,
                     "remaining_missing_minutes": [(a, tick_time(t)) for a, t in sorted(missing)]}


def describe_trade(asset, row, context):
    signal = row["signal_ms"] // BAR * BAR
    swing_key = "active_top_legs" if row["side"] == "SHORT" else "active_bottom_legs"
    return {"asset": asset, "signal_local": local(signal), "opened_local": local(row["opened_ms"]),
            "closed_local": local(row["closed_ms"]), "regime": context[signal]["regime"],
            "side": row["side"], "same_direction_divergence_legs": context[signal][swing_key],
            "rung": row["rung"], "reason": row["reason"],
            "entry": row["entry"], "exit": row["exit"], "net_usdt": row["net"]}


def drawdown(marks):
    peak = 1000.0
    deepest = 0.0
    for value in marks:
        peak = max(peak, value)
        deepest = max(deepest, 100 * (1 - value / peak))
    return deepest


def describe_mode(mode, prepared, results):
    mark = [fsum(pair) for pair in zip(*(results[a][mode]["marks"] for a in prepared), strict=True)]
    assets = {}
    for a, (_, schedules, context, _) in prepared.items():
        data = results[a][mode]
        closed = [describe_trade(a, row, context) for row in data["closed"]]
        group = defaultdict(list)
        for row in closed:
            group[row["regime"]].append(row)
        assets[a] = {
            "opens": data["opens"], "closed": len(closed), "net_marked_usdt": data["marks"][-1] - 500,
            "signal_count_by_regime": dict(Counter(context[t]["regime"] for t in schedules[mode] if OCTOBER <= t < END)),
            "closed_by_regime": {r: {"trades": len(rows), "wins": sum(x["net_usdt"] > 0 for x in rows),
                                    "hard_stops": sum(x["reason"] == "hard_stop" for x in rows),
                                    "net_usdt": fsum(x["net_usdt"] for x in rows)} for r, rows in group.items()},
            "journal": closed, "open_position_at_month_end": data["open_position_at_month_end"],
            "verified_trade_minutes": data["verified_minutes_with_trade_prints"],
            "approximated_minutes": data["approximated_minutes"], "tape_close_discrepancies": data["tape_close_discrepancies"],
        }
    closed = [trade for row in assets.values() for trade in row["journal"]]
    live = []
    for fill in FILLS:
        t = ms(fill.signal_time)
        _, schedules, context, _ = prepared[fill.asset]
        live.append({"asset": fill.asset, "time_local": fill.signal_time, "entry": fill.entry,
                     "signal_time_inferred": fill.signal_inferred, **context[t],
                     "matches_observed_short_signal_at_this_time": schedules[mode].get(t) == -1})
    return {
        "description": RULES[mode], "opens": {a: r["opens"] for a, r in assets.items()},
        "return_pct": 100 * (mark[-1] / 1000 - 1), "mdd_pct_at_minute_closes": drawdown(mark),
        "wins": sum(row["net_usdt"] > 0 for row in closed), "losses": sum(row["net_usdt"] < 0 for row in closed),
        "hard_stops": sum(row["reason"] == "hard_stop" for row in closed),
        "end_usdt": mark[-1], "assets": assets, "known_november_signals": live,
        "november_signal_matches": sum(r["matches_observed_short_signal_at_this_time"] for r in live),
    }


def entry_key(row):
    return row["signal_local"], row["side"]


def compare_against_baseline(baseline, mode, prepared):
    comparisons = {}
    for a, (_, schedules, _, _) in prepared.items():
        original = {entry_key(row): row for row in baseline["assets"][a]["journal"]}
        new = {entry_key(row): row for row in mode["assets"][a]["journal"]}
        removed = [{**original[k], "same_side_signal_still_present":
                    schedules[mode["mode"]].get(ms(k[0])) == (1 if k[1] == "LONG" else -1)}
                   for k in sorted(original.keys() - new.keys())]
        comparisons[a] = {"common_closed_trade_signals": len(original.keys() & new.keys()),
                          "removed_closed_trade_signals": len(removed), "new_closed_trade_signals": len(new.keys() - original.keys()),
                          "removed_original_winners": sum(r["net_usdt"] > 0 for r in removed),
                          "removed_original_losers": sum(r["net_usdt"] < 0 for r in removed),
                          "removed_original_trades": removed}
    return comparisons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", choices=tuple(name for name in RULES if name != "baseline"),
                        help="Run only the chosen case(s), always retaining the common October baseline.")
    args = parser.parse_args()
    modes = ("baseline", *dict.fromkeys(args.case)) if args.case else tuple(RULES)
    with ThreadPoolExecutor(max_workers=2) as pool:
        symbols = ("BTC", "ETH")
        prepared = dict(zip(symbols, pool.map(prepare, symbols), strict=True))
    print("October signal counts:", {a: {mode: sum(OCTOBER <= t < END for t in by_mode[mode]) for mode in modes}
                                      for a, (_, by_mode, _, _) in prepared.items()}, flush=True)
    raw, refinement = replay_with_refinement(prepared, modes)
    cases = {mode: {"mode": mode, **describe_mode(mode, prepared, raw)} for mode in modes}
    frozen = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    base = cases["baseline"]
    assert base["opens"] == frozen["month"]["opens"]
    close_enough(base["return_pct"], frozen["month"]["return_pct"])
    close_enough(base["mdd_pct_at_minute_closes"], frozen["month"]["mdd_pct_at_minute_closes"])
    for a, variants in raw.items():
        assert variants["baseline"]["closed"] == frozen["assets"][a]["closed"]
    for mode in modes[1:]:
        cases[mode]["entry_comparison_with_baseline"] = compare_against_baseline(base, cases[mode], prepared)

    doc = {"window_utc8": [local(OCTOBER), local(END)], "target_from_slide": frozen["target"],
           "fixed_execution": {k: v for k, v in frozen["inputs"].items() if k != "signals"},
           "baseline_signal_parameters": frozen["inputs"]["signals"],
           "classification": "Use only completed hourly closes. Signed ER over 24h and 120h must both meet 0.20 and 0.10 in the same direction for a trend. Both below threshold means range. Other combinations are transition.",
           "entry_notes": "The three regimes use distinct signal schedules. Range divergence compares confirmed price swings with MACD(12,26,9) histogram extremes within each leg. Two closed candles on each side, adjacent swings within 32 candles, active for up to 32 candles unless broken. Same direction MA5/MA20 and histogram confirm the reversal. A pattern is used on its first eligible close. In trend the breakout level is a confirmed 1h pivot known at the start of the signal candle; the retest is within 32 candles and the confirmation within four. Confirmed real November signals are checked at their reported signal timestamps only.",
           "refinement": refinement, "cases": cases}
    suffix = "_selected" if args.case else ""
    save_json(OUTPUTS / f"BTC_ETH_Gate_v13_October_2026_regime_divergence{suffix}.json", doc)
    for name, row in cases.items():
        print(name, row["opens"], row["wins"], row["losses"], round(row["return_pct"], 2),
              round(row["mdd_pct_at_minute_closes"], 2), "Nov", row["november_signal_matches"], flush=True)


if __name__ == "__main__":
    main()
