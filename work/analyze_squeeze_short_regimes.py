import json
from collections import Counter, defaultdict
from math import fsum

from backtest_squeeze_short import END, ETH_EARLY, HOUR, TREND_THRESHOLDS, build_leg, simulate
from combined_crypto_portfolio import BAR, WORK, close_enough, ms, year
from extended_crypto_portfolio import ETH_START, START, SWITCH, local


REGIMES = ("down", "up", "range", "transition")
BTC_EARLY = "BTCUSDT_Binance_2019_2020_continuous.csv"
BTC_BYBIT = "BTCUSDT_Bybit_2020_2026_continuous.csv"
ETH_BINANCE = "ETHUSDT_Binance_2019_2021_early.csv"
ETH_BYBIT = "ETHUSDT_Bybit_2021_2026_continuous.csv"


def gated_runs(legs):
    return {mode: simulate(legs, regime_only=None if mode == "all" else mode) for mode in ("all", *REGIMES)}


def summarize_trades(rows):
    n = len(rows)
    if not n:
        return {"trades": 0, "win_pct": None, "net_bps_per_trade": None, "after_slippage_before_fee_bps_per_trade": None}
    return {
        "trades": n,
        "win_pct": 100 * sum(r["net"] > 0 for r in rows) / n,
        "net_bps_per_trade": 10_000 * fsum(r["net"] / r["entry_notional"] for r in rows) / n,
        "after_slippage_before_fee_bps_per_trade": 10_000 * fsum((r["net"] + r["fees"]) / r["entry_notional"] for r in rows) / n,
    }


def fixed_size_attribution(legs):
    # This diagnostic uses the same entry/exit chronology but ignores the equity cap.
    _, trades = simulate(legs, fixed_notional=1000, with_journal=True)
    by_regime = defaultdict(list)
    by_asset = {a: defaultdict(list) for a in legs}
    by_year = defaultdict(lambda: defaultdict(list))
    for asset, rows in trades.items():
        for row in rows:
            t = row["signal"]
            leg = next(leg for leg in legs[asset] if leg.start <= t < leg.end)
            regime = leg.regime_at(t)[0]
            by_asset[asset][regime].append(row)
            by_regime[regime].append(row)
            by_year[year(t)][regime].append(row)
    return {
        "order_notional_target_usdt": 1000,
        "by_regime": {r: summarize_trades(by_regime[r]) for r in REGIMES},
        "by_asset": {a: {r: summarize_trades(groups[r]) for r in REGIMES} for a, groups in by_asset.items()},
        "by_signal_year": {y: {r: summarize_trades(groups[r]) for r in REGIMES} for y, groups in sorted(by_year.items())},
    }


def regime_distribution(legs):
    by_year = defaultdict(Counter)
    for leg in legs:
        for t in leg.bars:
            by_year[year(t)][leg.regime_at(t)[0]] += 1
    return {y: {r: 100 * counts[r] / sum(counts.values()) for r in REGIMES} for y, counts in by_year.items()}


def current_year_market(leg):
    first = leg.bars[leg.start].o
    last = leg.bars[leg.end - BAR].c
    close_peak = close_low = first
    worst_drawdown = max_rebound = 0.0
    monthly = {}
    for t, bar in leg.bars.items():
        month = local(t)[:7]
        monthly.setdefault(month, [bar.o, None])[1] = bar.c
        close_peak = max(close_peak, bar.c)
        close_low = min(close_low, bar.c)
        worst_drawdown = max(worst_drawdown, 1 - bar.c / close_peak)
        max_rebound = max(max_rebound, bar.c / close_low - 1)
    highest = max(leg.bars, key=lambda t: leg.bars[t].h)
    lowest = min(leg.bars, key=lambda t: leg.bars[t].l)
    return {
        "opening_price": first, "ending_price": last, "return_pct": 100 * (last / first - 1),
        "high": {"price": leg.bars[highest].h, "bar_open_local": local(highest)},
        "low": {"price": leg.bars[lowest].l, "bar_open_local": local(lowest)},
        "close_based_max_drawdown_pct": 100 * worst_drawdown,
        "close_based_max_rebound_pct": 100 * max_rebound,
        "monthly_return_pct": {m: 100 * (values[1] / values[0] - 1) for m, values in monthly.items()},
        "regime_time_pct": regime_distribution([leg])[2026],
    }


def confirm_control(all_result, prior):
    for key in ("ending_equity_usdt", "return_pct", "max_drawdown_pct"):
        close_enough(all_result[key], prior[key])
    assert all_result["entries"] == prior["entries"]
    for y, stats in all_result["years"].items():
        row = prior["years"][str(y)]
        assert stats["entries"] == row["entries"]
        close_enough(stats["ending_equity_usdt"], row["ending_equity_usdt"])


def main():
    outputs = WORK.parent / "outputs"
    prior = json.loads((outputs / "BTC_ETH_squeeze_expansion_short_2019_2025.json").read_text())
    asof = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
    btc_early = build_leg(BTC_EARLY, START, SWITCH)
    btc_late = build_leg(BTC_BYBIT, SWITCH, END)
    eth_early = build_leg(ETH_BINANCE, ETH_EARLY, ETH_START)
    eth_late = build_leg(ETH_BYBIT, ETH_START, END)
    old_legs = {
        "btc_solo": {"BTC": [btc_early, btc_late]},
        "eth_solo": {"ETH": [eth_early, eth_late]},
        "btc_eth_shared": {"BTC": [btc_early, btc_late], "ETH": [eth_late]},
    }
    historic = {}
    for account, legs in old_legs.items():
        historic[account] = gated_runs(legs)
        confirm_control(historic[account]["all"], prior["reconstructed_squeeze_short_only"][account])
        print("Verified ungated control and four gated runs", account, flush=True)
    historic_attribution = fixed_size_attribution(old_legs["btc_eth_shared"])

    current = {"BTC": build_leg(BTC_BYBIT, END, asof), "ETH": build_leg(ETH_BYBIT, END, asof)}
    current_legs = {a: [leg] for a, leg in current.items()}
    current_results = gated_runs(current_legs)
    current_attribution = fixed_size_attribution(current_legs)
    market = {a: current_year_market(leg) for a, leg in current.items()}
    screenshot_signals = []
    for asset, hh in (("BTC", "01:15"), ("BTC", "01:30"), ("ETH", "01:30"),
                      ("BTC", "06:00"), ("ETH", "06:00"), ("ETH", "16:30")):
        t = ms(f"2026-11-09T{hh}:00+08:00")
        leg = current[asset]
        assert t in leg.entries
        regime, d24, d120 = leg.regime_at(t)
        screenshot_signals.append({"asset": asset, "signal_local": local(t), "hourly_close_local": local(t // HOUR * HOUR),
                                   "regime": regime, "signed_er_24h": d24, "signed_er_120h": d120})
    out = {
        "data_scope": {"start_local": local(START), "split_local": local(END), "end_exclusive_local": local(asof),
                       "eth_shared_start_local": local(ETH_START), "eth_solo_start_local": local(ETH_EARLY)},
        "classifier": {"input": "completed one-hour closes known at order submission", "trend_windows": [
            {"hours": hours, "abs_threshold": threshold} for hours, threshold in TREND_THRESHOLDS],
            "up_or_down": "both windows agree at their thresholds", "range": "both windows are below their thresholds",
            "transition": "all other combinations", "order_policy": "existing 60-minute order life after qualifying submission"},
        "execution": {k: prior[k] for k in ("entry", "exits", "initial_usdt_each", "per_asset_cap_at_submission_x",
                                             "shared_cap_at_submission_x", "fee_pct_per_fill", "exit_slippage_pct", "funding_modeled")},
        "historical_2019_2025": historic,
        "historical_regime_time_pct_by_asset": {a: regime_distribution(legs[a]) for a, legs in (
            ("BTC", old_legs["btc_solo"]), ("ETH", old_legs["eth_solo"]))},
        "historical_shared_trade_attribution": historic_attribution,
        "current_2026_market": market, "current_2026_shared_fresh_500": current_results,
        "current_2026_shared_trade_attribution": current_attribution, "screenshot_signal_context": screenshot_signals,
    }
    (outputs / "BTC_ETH_squeeze_short_market_regimes_2019_2026.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for label, cases in (*historic.items(), ("2026_shared", current_results)):
        for mode, row in cases.items():
            print(label, mode, *(row[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries",
                                                 "asset_net_usdt", "fees", "hard_stops", "time_exits")))
    print("fixed history", json.dumps(historic_attribution["by_regime"]))
    print("fixed 2026", json.dumps(current_attribution["by_regime"]))
    print("2026 markets", json.dumps(market))
    print("screenshot contexts", json.dumps(screenshot_signals))


if __name__ == "__main__":
    main()
