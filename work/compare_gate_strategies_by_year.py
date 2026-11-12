import argparse
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import fsum

import numpy as np

from audit_gate_october import OCTOBER, SEPTEMBER
from combined_crypto_portfolio import BAR, FEE, SLIP, WORK, close_enough, ms, read_market
from extended_crypto_portfolio import local
from fit_squeeze_ladder_bot import build
from gate_annual_market import ASSETS, EARLIEST_START, END, MARKET_CACHE, PRICE_FILES, WINDOWS
from gate_october_regime_entries import DATA_END, market_schedules
from gate_public_data import save_json
from gate_v13_targets import targets
from replay_formal_bot_trades import FILLS
from replay_gate_annual import PATH_ORDERS, replay_annual_asset
from replay_gate_bot import PATHS
from summarize_btc_eth_rsi_priority import replay_journal


OUTPUTS = WORK.parent / "outputs"
STRATEGIES = ("baseline", "range_double_trend_retest")
OWN_SEED = 500.0
BOT_SEED = 1000.0
HOUR = 3_600_000
NOVEMBER = ms("2026-11-01T00:00:00+08:00")


def utc(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).isoformat()


def drawdown(prices, seed):
    values = np.r_[seed, prices]
    return float(100 * np.max(1 - values / np.maximum.accumulate(values)))


def stats_from_trades(trades):
    closed = [t for t in trades if t["exit_reason"] != "window_mark"]
    marked = fsum(t["net_usdt"] for t in trades)
    return {"opens": {a: sum(r["asset"] == a for r in trades) for a in ASSETS}, "closed_trades": len(closed),
            "wins": sum(r["net_usdt"] > 0 for r in closed), "losses": sum(r["net_usdt"] < 0 for r in closed),
            "fills_by_side": dict(Counter(r["side"] for r in trades)),
            "fills_by_regime": dict(Counter(r["regime_at_signal"] for r in trades if r["regime_at_signal"])),
            "pnl_by_regime_usdt": {tag: fsum(r["net_usdt"] for r in trades if r["regime_at_signal"] == tag)
                                   for tag in ("up", "down", "range", "transition")},
            "pnl_by_side_usdt": {side: fsum(r["net_usdt"] for r in trades if r["side"] == side) for side in ("LONG", "SHORT")},
            "pnl_by_asset_usdt": {a: fsum(r["net_usdt"] for r in trades if r["asset"] == a) for a in ASSETS},
            "hard_stops": sum(r["exit_reason"] in ("hard_stop", "stop", "stop_gap") for r in closed), "net_marked_usdt": marked}


def standard_bot_trade(asset, row, context):
    signal = row["signal_ms"] // BAR * BAR
    return {"asset": asset, "signal_ms": signal, "opened_ms": row["opened_ms"], "closed_ms": row["closed_ms"],
            "regime_at_signal": context[signal]["regime"], "side": row["side"], "entry": row["entry"], "exit": row["exit"],
            "net_usdt": row["net"], "opening_notional_usdt": row["notional"], "exit_reason": row["reason"], "rung": row["rung"]}


def summarize_gate_books(results, contexts, start, end, starting_cash):
    seed = fsum(starting_cash.values())
    marks = np.add(results["BTC"]["marks"], results["ETH"]["marks"])
    assert len(marks) * 60_000 == end - start
    trades = []
    for a, result in results.items():
        context = contexts[a]
        rows = [standard_bot_trade(a, r, context) for r in result["closed"]]
        if order_at_end := result["open_position_at_month_end"]:
            signal = order_at_end["time"] // BAR * BAR
            net = result["marks"][-1] - starting_cash[a] - fsum(r["net_usdt"] for r in rows)
            rows.append({"asset": a, "signal_ms": signal, "opened_ms": result["open_position_time_ms"], "closed_ms": end,
                         "regime_at_signal": context[signal]["regime"], "side": "LONG" if order_at_end["side"] == 1 else "SHORT",
                         "entry": order_at_end["price"], "exit": result["window_mark_price"], "net_usdt": net,
                         "opening_notional_usdt": order_at_end["price"] * order_at_end["qty"], "exit_reason": "window_mark"})
        assert result["opens"] == len(rows)
        trades.extend(rows)
    stats = stats_from_trades(trades)
    close_enough(stats["net_marked_usdt"], float(marks[-1]) - seed)
    return {**stats, "ending_usdt": float(marks[-1]), "return_pct": float(100 * (marks[-1] / seed - 1)),
            "mdd_15m_pct": drawdown(marks[14::15], seed), "mdd_1m_pct": drawdown(marks, seed),
            "execution_event_minutes": {a: row.get("execution_event_minutes", {"verified_trade_minutes": row.get("verified_minutes_with_trade_prints", 0)})
                                        for a, row in results.items()},
            "quote_resolution_fallbacks": {a: row["approximated_minutes"] for a, row in results.items()},
            "failed_cached_tape_cross_checks": {a: row.get("cached_print_errors", {}) for a, row in results.items()},
            "trades": sorted(trades, key=lambda r: (r["opened_ms"], r["asset"]))}


def gate_run(year, mode, order, market, prepared, pool, *, window=None, use_cached_prints=True, size_multipliers=None):
    start, end = WINDOWS[year] if window is None else window
    sizes = {} if size_multipliers is None else size_multipliers
    tasks = {a: pool.submit(replay_annual_asset, a, year, prepared[a][0], prepared[a][1][mode], market[a]["years"][str(year)],
                            order, window=window, use_cached_prints=use_cached_prints, size_multipliers=sizes.get(a)) for a in ASSETS}
    results = {a: job.result() for a, job in tasks.items()}
    return summarize_gate_books(results, {a: prepared[a][2] for a in ASSETS}, start, end, dict.fromkeys(ASSETS, BOT_SEED / 2))


def our_strategy(name, start, end, price_files, markets, context=None):
    prefix = f"gate_annual_our_original_{name}"
    args = ["node", str(WORK / "btc_eth_side_review.mjs"), str(price_files["BTC"]), str(WORK / prefix),
            utc(start), utc(end), "gate", "btc_eth_shared_control", str(OWN_SEED), str(price_files["ETH"]), utc(start)]
    subprocess.run(args, cwd=WORK.parent, check=True, stdout=subprocess.DEVNULL)
    report, ledger, _, _ = replay_journal(prefix, markets, {"BTC": "BTC", "ETH": "ETH"}, OWN_SEED, start, end,
                                         capture_equity=True)
    marks = report["equity_marks_at_15m_close"]
    trades = []
    for asset, rows in ledger.items():
        for r in rows:
            t, opened, closed = (ms(r[k]) for k in ("signal", "opened", "closed"))
            exit_price, net = float(r["exit"]), float(r["net"])
            reason = r["reason"]
            if reason == "end_of_data" and closed == end:
                side = 1 if r["side"] == "LONG" else -1
                reference = exit_price / (1 - side * SLIP)
                cost = float(r["qty"]) * (exit_price * FEE + reference * SLIP)
                marks[-1] += cost
                net += cost
                exit_price, reason = reference, "window_mark"
            trades.append({"asset": asset, "signal_ms": t, "opened_ms": opened, "closed_ms": closed, "side": r["side"],
                           "entry": float(r["first_entry"]), "exit": exit_price, "net_usdt": net,
                           "opening_notional_usdt": float(r["first_entry"]) * float(r["first_qty"]),
                           "regime_at_signal": context[asset][t]["regime"] if context and t in context[asset] else None,
                           "exit_reason": reason, "setup": r["setup"]})
    stats = stats_from_trades(trades)
    close_enough(stats["net_marked_usdt"], marks[-1] - OWN_SEED)
    return {**stats, "ending_usdt": marks[-1], "return_pct": 100 * (marks[-1] / OWN_SEED - 1),
            "mdd_15m_pct": drawdown(marks, OWN_SEED), "trades": sorted(trades, key=lambda r: (r["opened_ms"], r["asset"]))}


def our_annual(year, prepared):
    start, end = WINDOWS[year]
    markets = {a: {t: prepared[a][0].bars[t] for t in range(start, end, BAR)} for a in ASSETS}
    return our_strategy(year, start, end, PRICE_FILES, markets, {a: prepared[a][2] for a in ASSETS})


def entry_comparison(a, b):
    left, right = a["trades"], b["trades"]
    by_symbol = {}
    for asset in ASSETS:
        same_signals = nearby = 0
        examples = []
        for side in ("LONG", "SHORT"):
            x = [r for r in left if r["asset"] == asset and r["side"] == side]
            y = [r for r in right if r["asset"] == asset and r["side"] == side]
            same_signals += len({r["signal_ms"] for r in x} & {r["signal_ms"] for r in y})
            i = j = 0
            while i < len(x) and j < len(y):
                delta = y[j]["opened_ms"] - x[i]["opened_ms"]
                if delta < -HOUR:
                    j += 1
                elif delta > HOUR:
                    i += 1
                else:
                    nearby += 1
                    examples.append({"side": side, "left_entry": local(x[i]["opened_ms"]), "right_entry": local(y[j]["opened_ms"]),
                                     "minutes_apart": delta / 60_000, "left_net_pct_of_notional": 100 * x[i]["net_usdt"] / x[i]["opening_notional_usdt"],
                                     "right_net_pct_of_notional": 100 * y[j]["net_usdt"] / y[j]["opening_notional_usdt"]})
                    i += 1
                    j += 1
        by_symbol[asset] = {"same_closed_15m_signal": same_signals, "same_side_entries_within_1h_one_to_one": nearby,
                            "pairs": examples}
    return by_symbol


def recent_checks(prepared, market, pool):
    # The independent October setup is a direct regression against the previously verified experiment.
    known = json.loads((OUTPUTS / "BTC_ETH_Gate_v13_October_2026_regime_divergence.json").read_text(encoding="utf-8"))
    october = {}
    for mode in STRATEGIES:
        exact = gate_run(2026, mode, "adverse_first", market, prepared, pool, window=(OCTOBER, END))
        prior = known["cases"][mode]
        assert exact["opens"] == prior["opens"], (mode, exact["opens"], prior["opens"])
        close_enough(exact["return_pct"], prior["return_pct"])
        close_enough(exact["mdd_1m_pct"], prior["mdd_pct_at_minute_closes"])
        october[mode] = exact
        october[mode]["ten_second_calibration"] = {
            order: {k: value for k, value in gate_run(2026, mode, order, market, prepared, pool, window=(OCTOBER, END),
                                                    use_cached_prints=False).items() if k in ("return_pct", "opens", "mdd_1m_pct")}
            for order in PATH_ORDERS
        }
    october["our_original"] = our_strategy("oct2026", OCTOBER, END, PRICE_FILES,
                                          {a: {t: prepared[a][0].bars[t] for t in range(OCTOBER, END, BAR)} for a in ASSETS})
    recent_files = {a: WORK / PATHS[a] for a in ASSETS}
    recent_own = our_strategy("nov2026", NOVEMBER, DATA_END, recent_files,
                              {a: read_market(path, NOVEMBER, DATA_END) for a, path in recent_files.items()})
    recent_schedules = {a: market_schedules(a, build(PATHS[a], SEPTEMBER, DATA_END)) for a in ASSETS}
    actual = []
    for fill in FILLS:
        t = ms(fill.signal_time)
        signals, context = recent_schedules[fill.asset]
        own_nearby = [r for r in recent_own["trades"] if r["asset"] == fill.asset and r["side"] == "SHORT"
                      and abs(r["opened_ms"] - ms(fill.opened)) <= HOUR]
        near_signals = {mode: [local(time) for time in range(t - HOUR, t + HOUR + 1, BAR)
                               if signals[mode].get(time) == -1] for mode in STRATEGIES}
        actual.append({"asset": fill.asset, "signal_local": fill.signal_time, "signal_time_inferred": fill.signal_inferred,
                       "opened_local": fill.opened, "closed_local": fill.closed, "entry": fill.entry, "exit": fill.exit,
                       "net_usdt": fill.net_usdt, "rung_from_report": fill.rung, "entry_context": context[t],
                       "same_15m_short_signal": {mode: signals[mode].get(t) == -1 for mode in STRATEGIES},
                       "short_signals_within_1h": near_signals, "our_original_short_fills_within_1h": own_nearby})
    return {"october_verified": october, "november_original_same_gate": recent_own, "five_known_competitor_trades": actual}


def add_readable_times(node):
    if isinstance(node, list):
        for row in node:
            add_readable_times(row)
    elif isinstance(node, dict):
        for k, value in tuple(node.items()):
            if k in ("signal_ms", "opened_ms", "closed_ms"):
                node[k.replace("_ms", "_local")] = local(value)
            elif isinstance(value, (list, dict)):
                add_readable_times(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", choices=tuple(WINDOWS), help="Run selected year(s); default is all.")
    years = sorted(set(parser.parse_args().year or WINDOWS))
    market = json.loads((MARKET_CACHE / "prepared_market.json").read_text(encoding="utf-8"))
    prepared = {}
    for asset, path in PRICE_FILES.items():
        leg = build(path, EARLIEST_START, END)
        schedules, context = market_schedules(asset, leg, price_file=path)
        prepared[asset] = leg, {mode: schedules[mode] for mode in STRATEGIES}, context
    print("Prepared frozen signal schedules", flush=True)

    rows = {}
    with ThreadPoolExecutor(max_workers=2) as replay_pool, ThreadPoolExecutor(max_workers=2) as original_pool:
        own = {y: original_pool.submit(our_annual, y, prepared) for y in years}
        for y in years:
            branches = {mode: {order: gate_run(y, mode, order, market, prepared, replay_pool) for order in PATH_ORDERS}
                        for mode in STRATEGIES}
            original = own[y].result()
            split = branches["range_double_trend_retest"]["adverse_first"]
            print(y, "split", round(split["return_pct"], 2), split["opens"], "orig Gate",
                  round(branches["baseline"]["adverse_first"]["return_pct"], 2), "our original", round(original["return_pct"], 2), flush=True)
            rows[y] = {"window_utc8": [local(t) for t in WINDOWS[y]], "gate_models": branches, "our_original_same_gate": original,
                       "split_vs_our_original": entry_comparison(split, original),
                       "split_vs_gate_baseline": entry_comparison(split, branches["baseline"]["adverse_first"])}
        recent = recent_checks(prepared, market, replay_pool) if 2026 in years else None

    older_report = json.loads((OUTPUTS / "BTC_ETH_bot_report_fit_audit_2020_2025.json").read_text(encoding="utf-8"))
    native = json.loads((OUTPUTS / "BTC_ETH_simultaneous_portfolio_2019_2026.json").read_text(encoding="utf-8"))
    doc = {"yearly_accounts_reset": True, "gate_models_initial_usdt": BOT_SEED, "our_original_initial_usdt": OWN_SEED,
           "quotes": "Gate USDT perpetual 10s OHLC, using the corresponding 1m archive if the 10s block does not reproduce it. "
                     "The two modeled high/low orders with 5s polling are sensitivity cases, not strict bounds. "
                     "The 2019-12 trade archive and checked recent prints are replayed at their real timestamps. "
                     "15m bars aggregate observed prices, carrying the last price when a whole bar is unobserved. "
                     "Unobserved minutes cannot fill simulated Gate orders.",
           "year_end": "Mark any open residual using the final quote. Original journals' artificial exit costs at the boundary are reversed.",
           "fees_pct_per_fill": 100 * FEE, "slippage_pct": 100 * SLIP, "funding_modeled": False,
           "same_market_own_original": "Existing shared 500 USDT rules, each asset capped at 2.5x and portfolio at 5x, on the Gate data, "
                                       "with both assets eligible throughout the common window. Mark-to-market drawdown measured at 15m closes.",
           "gate_market_coverage": market, "annual": rows, "october_and_live": recent,
           "competitor_v13_reported_targets": targets(), "competitor_5x_screenshot_separate": older_report["target_from_user_screenshot"],
           "our_previous_native_continuous_for_reference": {"start": native["start_local"], "end": native["end_exclusive_local"],
                                                            "years": native["shared_500"]["years"]}}
    add_readable_times(doc)
    suffix = "_" + "_".join(map(str, years)) if years != list(WINDOWS) else ""
    save_json(OUTPUTS / f"BTC_ETH_Gate_regime_annual_trade_comparison_2019_2026{suffix}.json", doc)


if __name__ == "__main__":
    main()
