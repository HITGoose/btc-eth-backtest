import csv
import json
from collections import Counter
from math import fsum

from combined_crypto_portfolio import BAR, WORK, Signal, close_enough, ms, read_market, run, verify_isolated, year
from extended_crypto_portfolio import START, SWITCH, join_results, local


RSI_SETUP = "rsi_4h_extreme"
FOUR_HOURS = 16 * BAR
WARMUP = 15 * 96 * BAR
OUTPUTS = WORK.parent / "outputs"


def check_rsi_entries(rows, bars, period):
    first_complete_end = next(iter(bars)) + FOUR_HOURS
    closes = [(t + BAR, b.c) for t, b in bars.items()
              if t + BAR >= first_complete_end and (t + BAR) % FOUR_HOURS == 0]
    gains = losses = 0.0
    rsi_at_close = {}
    for i, ((_, prev_close), (t, price)) in enumerate(zip(closes, closes[1:]), 1):
        gain = max(0.0, price - prev_close)
        loss = max(0.0, prev_close - price)
        if i <= period:
            gains += gain / period
            losses += loss / period
        else:
            gains = (gains * (period - 1) + gain) / period
            losses = (losses * (period - 1) + loss) / period
        if i >= period:
            rsi_at_close[t] = 100 - 100 / (1 + gains / losses) if losses else 100 if gains else 50
    for r in rows:
        if r["setup"] != RSI_SETUP:
            assert not r.get("entry_rsi_4h")
            continue
        t = ms(r["opened"])
        assert ms(r["signal"]) == t and t in rsi_at_close
        value = rsi_at_close[t]
        close_enough(value, float(r["entry_rsi_4h"]))
        assert value < 20 if r["side"] == "LONG" else value > 80


def trade_totals(rows):
    return {
        "trades": len(rows),
        **{f"{k}_usdt": fsum(float(r[k]) for r in rows) for k in ("gross", "fees", "net")},
        "hard_stop_count": sum(r["reason"] in ("stop", "stop_gap") for r in rows),
        "one_hour_exit_count": sum(r["reason"] == "er_1h_timeout" for r in rows),
    }


def summarize(case, label, inputs):
    segments, all_rows = [], []
    seed, rejected = 500.0, 0
    for venue, bars, start, end in inputs:
        prefix = WORK / f"rsi4h_{case}_{venue}"
        doc = json.loads(prefix.with_name(prefix.name + "_summary.json").read_text())
        assert (ms(doc["since"]), ms(doc["until"])) == (start, end) and doc["continuous"]
        summary = doc["summaries"][label]
        with prefix.with_name(prefix.name + "_trades.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert summary["overall"]["trades"] == len(rows)
        if period := summary["config"].get("rsi4hPeriod"):
            check_rsi_entries(rows, bars, period)
        plan = {}
        for row in rows:
            opened = ms(row["opened"])
            assert opened not in plan and row["add_fills"] == "0" and float(row["funding"]) == 0
            side = {"LONG": 1, "SHORT": -1}[row["side"]]
            plan[opened] = Signal(opened, ms(row["closed"]), side, row["reason"],
                                  float(row["first_entry"]), float(row["exit"]))
        segment, events = run({"BTC": bars}, {"BTC": plan}, {"BTC": "BTC"}, {"BTC": seed}, 2.5, start, end)
        verify_isolated(segment, events, "BTC", rows, summary)
        seed = segment["ending_equity_usdt"]
        close_enough(seed, summary["endingEquity"])
        rejected += summary["rejected"]
        segments.append(segment)
        all_rows.extend(rows)

    result = join_results(segments)
    rsi_rows = [r for r in all_rows if r["setup"] == RSI_SETUP]
    rsi_entries_by_year = Counter(year(ms(r["opened"])) for r in rsi_rows)
    for y, stats in result["years"].items():
        stats["rsi_entry_count"] = rsi_entries_by_year[y]
    return {
        **result,
        "totals": trade_totals(all_rows),
        "by_side": {side: trade_totals([r for r in all_rows if r["side"] == side]) for side in ("LONG", "SHORT")},
        "rsi_entries": {
            "totals": trade_totals(rsi_rows),
            "by_side": {side: trade_totals([r for r in rsi_rows if r["side"] == side]) for side in ("LONG", "SHORT")},
        },
        "other_entries": trade_totals([r for r in all_rows if r["setup"] != RSI_SETUP]),
        "rejected_entries_below_order_minimum": rejected,
        "last_closed_trade_local": local(ms(all_rows[-1]["closed"])),
        "terminal_settlements_local": [local(ms(r["closed"])) for r in all_rows if r["reason"] == "end_of_data"],
    }


def main():
    previous = json.loads((OUTPUTS / "BTC_vs_ETH_single_asset_2019_2026.json").read_text())["btc_only"]
    end = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
    inputs = [(venue, read_market(WORK / market, start - WARMUP, until), start, until)
              for venue, market, start, until in (
                  ("binance", "BTCUSDT_Binance_2019_2020_continuous.csv", START, SWITCH),
                  ("bybit", "BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH, end),
              )]
    original = summarize("control", "original", inputs)
    with_rsi = summarize("add", "with_rsi_4h", inputs)
    for name in ("ending_equity_usdt", "return_pct", "max_drawdown_pct"):
        close_enough(original[name], previous[name])
    for y, stats in original["years"].items():
        prior = previous["years"][str(y)]
        for name in ("ending_equity_usdt", "return_pct", "max_drawdown_pct"):
            close_enough(stats[name], prior[name])
        assert stats["entries"] == prior["entries"]
    out = {
        "start_local": local(START), "bybit_switch_local": local(SWITCH), "end_exclusive_local": local(end),
        "initial_equity_usdt": 500, "opening_cap_x": 2.5, "fee_pct_per_fill": 0.05,
        "slippage_pct_per_side": 0.02, "hard_stop_price_pct": 2, "funding_modeled": False,
        "min_order_notional_usdt": 100, "quantity_step_btc": 0.001,
        "rsi_signal": {"period": 6, "timeframe_hours": 4, "long_below": 20, "short_above": 80,
                       "entry": "next 15-minute open after each qualifying completed 4-hour candle, when flat and without an original entry"},
        "original": original, "original_plus_rsi": with_rsi,
    }
    (OUTPUTS / "BTCUSDT_4h_RSI6_2019_2026.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for case, result in (("original", original), ("with_rsi", with_rsi)):
        print(case, "summary", *(result[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct")))
        for k in ("totals", "by_side", "rsi_entries", "other_entries", "rejected_entries_below_order_minimum",
                  "last_closed_trade_local", "terminal_settlements_local"):
            print(k, json.dumps(result[k]))
        for y, row in result["years"].items():
            print(y, *(row[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries", "rsi_entry_count")))


if __name__ == "__main__":
    main()
