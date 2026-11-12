import csv
import json
from collections import Counter, defaultdict
from math import fsum

from combined_crypto_portfolio import BAR, WORK, Signal, close_enough, ms, read_market, read_plan, run, verify_isolated
from extended_crypto_portfolio import ETH_START, START, SWITCH, join_results, local
from summarize_btc_rsi_4h import OUTPUTS, RSI_SETUP, WARMUP, check_rsi_entries, trade_totals


def replay_journal(prefix, markets, labels, seed, start, end, *, capture_equity=False):
    doc = json.loads((WORK / f"{prefix}_summary.json").read_text())
    assert (ms(doc["since"]), ms(doc["until"])) == (start, end) and doc["continuous"]
    trade_path = WORK / f"{prefix}_trades.csv"
    journal = []
    if trade_path.exists():
        with trade_path.open(newline="", encoding="utf-8") as f:
            journal = list(csv.DictReader(f))
    rows_by_asset, plans, rejected, conflicts = {}, {}, {}, []
    range_gate = None
    for asset, label in labels.items():
        config = doc["summaries"][label]["config"]
        rows = [r for r in journal if r["scenario"] == label]
        rows_by_asset[asset] = rows
        by_time = {r["opened"]: r for r in rows}
        assert len(rows) == len(by_time)
        hold_ms = config.get("rsiMinHoldHours", 0) * 3_600_000
        plans[asset] = {
            ms(time): Signal(ms(time), ms(r["closed"]), {"LONG": 1, "SHORT": -1}[r["side"]],
                             r["reason"], float(r["first_entry"]), float(r["exit"]),
                             ms(time) + hold_ms if hold_ms and r["setup"] == RSI_SETUP else 0,
                             protect_profit=config.get("profitExit") in ("profit_close_lock", "profit_runner"))
            for time, r in by_time.items()
        }
        summary = doc["summaries"][label]
        assert len(rows) == summary["overall"]["trades"]
        rejected[asset] = summary["rejected"]
        if asset == "ETH":
            assert "rsi4hPeriod" not in config and all(r["setup"] != RSI_SETUP for r in rows)
        if period := config.get("rsi4hPeriod"):
            assert period == 6
            checks = rows.copy()
            for c in summary["rsi4hConflicts"]:
                assert c["originalSide"] == -c["rsiSide"]
                expected_side = c["rsiSide"] if config.get("rsi4hPriority") else c["originalSide"]
                assert c["chosenSide"] == expected_side
                fill = by_time.get(c["time"])
                if fill:
                    assert fill["side"] == {1: "LONG", -1: "SHORT"}[c["chosenSide"]]
                else:
                    assert summary["rejected"] > 0
                conflicts.append({**c, "time_local": local(ms(c["time"])), "filled": bool(fill)})
                checks.append({"setup": RSI_SETUP, "opened": c["time"], "signal": c["time"],
                               "side": {1: "LONG", -1: "SHORT"}[c["rsiSide"]], "entry_rsi_4h": c["rsi"]})
            check_rsi_entries(checks, markets[asset], period)
        if config.get("rsiRangeOnly"):
            assert asset == "BTC"
            rsi_fills = 0
            for row in rows:
                if row["setup"] != RSI_SETUP:
                    assert not row["entry_er_20"]
                    continue
                t = ms(row["signal"])
                closes = [markets[asset][bar_open].c for bar_open in range(t - 21 * BAR, t, BAR)]
                travel = fsum(abs(right - left) for left, right in zip(closes, closes[1:]))
                er = abs(closes[-1] - closes[0]) / travel if travel else 0
                close_enough(er, float(row["entry_er_20"]))
                assert er < 0.25
                rsi_fills += 1
            range_gate = summary["rsiRangeGate"]
            assert 0 <= range_gate["allowed"] - rsi_fills <= summary["rejected"]

    result, events = run(markets, plans, dict.fromkeys(markets, "shared"), {"shared": seed}, 2.5, start, end,
                         capture_equity=capture_equity)
    if range_gate is not None:
        result["btc_rsi_range_gate"] = range_gate
    for asset, label in labels.items():
        summary = doc["summaries"][label]
        asset_years = {y: row for y, row in result["years"].items() if str(y) in summary["yearlyEquity"]}
        verify_isolated({**result, "years": asset_years}, events, asset, rows_by_asset[asset], summary)
    return result, rows_by_asset, rejected, conflicts


def summarize(parts):
    result = join_results([part[0] for part in parts])
    rows_by_asset = defaultdict(list)
    rejected = Counter()
    range_gate = Counter()
    conflicts = []
    for leg, rows, skips, disagreements in parts:
        for asset, trades in rows.items():
            rows_by_asset[asset].extend(trades)
        rejected.update(skips)
        range_gate.update(leg.get("btc_rsi_range_gate", {}))
        conflicts.extend(disagreements)
    all_rows = [r for rows in rows_by_asset.values() for r in rows]
    rsi_rows = [r for r in rows_by_asset.get("BTC", []) if r["setup"] == RSI_SETUP]
    close_enough(trade_totals(all_rows)["net_usdt"], result["ending_equity_usdt"] - 500)
    return {
        **result,
        "totals": trade_totals(all_rows),
        "by_side": {side: trade_totals([r for r in all_rows if r["side"] == side]) for side in ("LONG", "SHORT")},
        "by_asset": {asset: {"totals": trade_totals(rows), "by_side": {
            side: trade_totals([r for r in rows if r["side"] == side]) for side in ("LONG", "SHORT")
        }} for asset, rows in rows_by_asset.items()},
        "btc_rsi_entries": {"totals": trade_totals(rsi_rows), "by_side": {
            side: trade_totals([r for r in rsi_rows if r["side"] == side]) for side in ("LONG", "SHORT")
        }},
        "below_minimum_order_attempts": dict(rejected),
        **({"btc_rsi_range_gate": dict(range_gate)} if range_gate else {}),
        "btc_rsi_conflicts": conflicts,
        "terminal_settlements_local": [local(ms(r["closed"])) for r in all_rows if r["reason"] == "end_of_data"],
    }


def eth_solo(early_bars, late_bars, early_start, end):
    seed, parts = 500, []
    for bars, prefix, first, last in (
        (early_bars, "eth_binance_early_2019_2021", early_start, ETH_START),
        (late_bars, "ext_eth_bybit", ETH_START, end),
    ):
        plan, rows, _ = read_plan((prefix, "eth_current_strategy"), first, last)
        result, events = run({"ETH": bars}, {"ETH": plan}, {"ETH": "ETH"}, {"ETH": seed}, 2.5, first, last)
        assert len(rows) == len(events["ETH"])
        sized_rows = [dict(r, fees=e["fees"], net=e["net"], gross=e["net"] + e["fees"])
                      for r, e in zip(rows, events["ETH"])]
        parts.append((result, {"ETH": sized_rows}, {"ETH": 0}, []))
        seed = result["ending_equity_usdt"]
    return summarize(parts)


def compare_reference(actual, reference):
    for key in ("ending_equity_usdt", "return_pct", "max_drawdown_pct"):
        close_enough(actual[key], reference[key])
    for y, stats in actual["years"].items():
        prior = reference["years"][str(y)]
        for key in ("ending_equity_usdt", "return_pct", "max_drawdown_pct"):
            close_enough(stats[key], prior[key])
        assert stats["entries"] == prior["entries"]
    assert actual["entries"] == reference["entries"]


def main():
    end = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
    eth_early = ms("2019-12-14T00:00:00Z")
    btc_early = read_market(WORK / "BTCUSDT_Binance_2019_2020_continuous.csv", START - WARMUP, SWITCH)
    btc_bybit = read_market(WORK / "BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH - WARMUP, end)
    eth_bybit = read_market(WORK / "ETHUSDT_Bybit_2021_2026_continuous.csv", ETH_START, end)
    eth_binance = read_market(WORK / "ETHUSDT_Binance_2019_2021_early.csv", eth_early, ETH_START)
    solo_reference = json.loads((OUTPUTS / "BTC_vs_ETH_single_asset_2019_2026.json").read_text())
    shared_reference = json.loads((OUTPUTS / "BTC_ETH_simultaneous_portfolio_2019_2026.json").read_text())["shared_500"]
    previous_rsi = json.loads((OUTPUTS / "BTCUSDT_4h_RSI6_2019_2026.json").read_text())

    early_control = replay_journal("rsi4h_control_binance", {"BTC": btc_early}, {"BTC": "original"}, 500, START, SWITCH)
    early_rsi = replay_journal("rsi4h_priority_binance", {"BTC": btc_early}, {"BTC": "rsi_4h_priority"}, 500, START, SWITCH)
    late_solo = replay_journal("rsi4h_priority_bybit", {"BTC": btc_bybit}, {"BTC": "rsi_4h_priority"},
                               early_rsi[0]["ending_equity_usdt"], SWITCH, end)
    btc_rsi = summarize([early_rsi, late_solo])
    eth_original = eth_solo(eth_binance, eth_bybit, eth_early, end)
    compare_reference(btc_rsi, previous_rsi["original_plus_rsi"])
    compare_reference(eth_original, solo_reference["eth_only"])

    joint_legs = []
    for name, early in (("control", early_control), ("priority", early_rsi)):
        joint_legs.append(replay_journal(f"rsi4h_shared_{name}_bybit", {"BTC": btc_bybit, "ETH": eth_bybit},
                                         {"BTC": "BTC", "ETH": "ETH"}, early[0]["ending_equity_usdt"], SWITCH, end))
    shared_original = summarize([early_control, joint_legs[0]])
    shared_rsi = summarize([early_rsi, joint_legs[1]])
    compare_reference(shared_original, shared_reference)
    eth_lifecycles = [
        [(r["opened"], r["closed"], r["side"], r["reason"]) for r in leg[1]["ETH"]]
        for leg in joint_legs
    ]
    assert eth_lifecycles[0] == eth_lifecycles[1]
    assert (WORK / "rsi4h_shared_original_priority_bybit_trades.csv").read_bytes() == (
        WORK / "rsi4h_shared_priority_bybit_trades.csv").read_bytes()

    out = {
        "start_local": local(START), "btc_bybit_switch_local": local(SWITCH), "end_exclusive_local": local(end),
        "eth_solo_first_trade_eligible_local": local(eth_early), "eth_shared_first_trade_eligible_local": local(ETH_START),
        "initial_equity_usdt_per_account": 500, "per_asset_opening_cap_x": 2.5, "shared_gross_cap_x": 5,
        "fee_pct_per_fill": 0.05, "slippage_pct_per_side": 0.02, "hard_stop_price_pct": 2, "funding_modeled": False,
        "min_order_notional_usdt_by_asset": {"BTC": 100, "ETH": 5},
        "drawdown_sampling": "15-minute bar-close marked equity",
        "btc_rsi": {"timeframe_hours": 4, "period": 6, "long_below": 20, "short_above": 80,
                    "entry": "next 15-minute open after a qualifying completed 4-hour candle while flat",
                    "opposite_signal_priority": "RSI", "asset": "BTC"},
        "btc_only_original": previous_rsi["original"], "btc_only_rsi_priority": btc_rsi,
        "eth_only_original": eth_original, "shared_original": shared_original, "shared_rsi_priority": shared_rsi,
        "shared_eth_trade_lifecycles_identical": True,
        "priority_only_change_affects_fills": False,
    }
    (OUTPUTS / "BTC_ETH_RSI6_BTC_only_overlay_2019_2026.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for label in ("btc_only_original", "btc_only_rsi_priority", "eth_only_original", "shared_original", "shared_rsi_priority"):
        result = out[label]
        print(label, *(result[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries", "asset_net_usdt")))
        for key in ("totals", "by_side", "btc_rsi_entries", "below_minimum_order_attempts", "btc_rsi_conflicts", "terminal_settlements_local"):
            if key in result:
                print(key, result[key])
        for y, row in result["years"].items():
            print(y, *(row[k] for k in ("ending_equity_usdt", "return_pct", "entries", "asset_net_usdt")))


if __name__ == "__main__":
    main()
