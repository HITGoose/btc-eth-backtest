import csv
import json
from statistics import median

from combined_crypto_portfolio import WORK, ms, read_market
from extended_crypto_portfolio import ETH_START, START, SWITCH
from summarize_btc_eth_rsi_priority import replay_journal, summarize
from summarize_btc_rsi_4h import OUTPUTS, RSI_SETUP, WARMUP


def rows_for(prefix, label):
    with (WORK / f"{prefix}_trades.csv").open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["scenario"] == label]


def holding_audit(btc_rows):
    holds = [(ms(r["closed"]) - ms(r["opened"]), r["reason"]) for r in btc_rows if r["setup"] == RSI_SETUP]
    hour_ms = 3_600_000
    six_hours = 6 * hour_ms
    return {
        "rsi_trades": len(holds),
        "median_hours": median(duration for duration, _ in holds) / hour_ms,
        # An intrabar stop in the final locked candle is recorded at that candle's close.
        "hard_stops_during_first_6h": sum(
            (reason == "stop" and duration <= six_hours) or (reason == "stop_gap" and duration < six_hours)
            for duration, reason in holds
        ),
        "ordinary_exits_before_6h": sum(
            duration < six_hours and reason not in ("stop", "stop_gap", "end_of_data") for duration, reason in holds
        ),
        "data_boundary_exits_before_6h": sum(duration < six_hours and reason == "end_of_data" for duration, reason in holds),
    }


def main():
    previous = json.loads((OUTPUTS / "BTC_ETH_RSI6_BTC_only_overlay_2019_2026.json").read_text())
    end = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
    btc_early = read_market(WORK / "BTCUSDT_Binance_2019_2020_continuous.csv", START - WARMUP, SWITCH)
    btc_bybit = read_market(WORK / "BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH - WARMUP, end)
    eth_bybit = read_market(WORK / "ETHUSDT_Bybit_2021_2026_continuous.csv", ETH_START, end)

    early = replay_journal("rsi4h_hold6h_binance", {"BTC": btc_early}, {"BTC": "rsi_4h_hold6h"}, 500, START, SWITCH)
    seed = early[0]["ending_equity_usdt"]
    solo = replay_journal("rsi4h_hold6h_bybit", {"BTC": btc_bybit}, {"BTC": "rsi_4h_hold6h"}, seed, SWITCH, end)
    shared = replay_journal("rsi4h_shared_hold6h_bybit", {"BTC": btc_bybit, "ETH": eth_bybit},
                            {"BTC": "BTC", "ETH": "ETH"}, seed, SWITCH, end)

    eth_before = rows_for("rsi4h_shared_priority_bybit", "ETH")
    eth_after = shared[1]["ETH"]
    eth_signals = ("opened", "closed", "side", "reason")
    assert [tuple(r[k] for k in eth_signals) for r in eth_before] == [tuple(r[k] for k in eth_signals) for r in eth_after]
    early_before = rows_for("rsi4h_priority_binance", "rsi_4h_priority")
    early_after = early[1]["BTC"]
    results = {
        "btc_solo": {
            "previous": previous["btc_only_rsi_priority"],
            "hold_6h": summarize([early, solo]),
            "previous_rsi_holding": holding_audit(early_before + rows_for("rsi4h_priority_bybit", "rsi_4h_priority")),
            "hold_6h_rsi_holding": holding_audit(early_after + solo[1]["BTC"]),
        },
        "btc_eth_shared": {
            "previous": previous["shared_rsi_priority"],
            "hold_6h": summarize([early, shared]),
            "previous_rsi_holding": holding_audit(early_before + rows_for("rsi4h_shared_priority_bybit", "BTC")),
            "hold_6h_rsi_holding": holding_audit(early_after + shared[1]["BTC"]),
        },
    }
    for account, variants in results.items():
        audit = variants["hold_6h_rsi_holding"]
        assert audit["ordinary_exits_before_6h"] == 0
        for variant in ("previous", "hold_6h"):
            result = variants[variant]
            print(account, variant, *(result[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries",
                  "asset_net_usdt", "hard_stops", "time_exits", "below_minimum_order_attempts")))
            print("by_side", result["by_side"])
            print("rsi_entries", result["btc_rsi_entries"])
            print("conflicts", result["btc_rsi_conflicts"], "settlements", result["terminal_settlements_local"])
        print("holding", variants["previous_rsi_holding"], audit)
        for y, row in variants["hold_6h"]["years"].items():
            print(y, *(row[k] for k in ("ending_equity_usdt", "return_pct", "entries")))

    metadata = {k: previous[k] for k in (
        "start_local", "end_exclusive_local", "eth_shared_first_trade_eligible_local", "initial_equity_usdt_per_account",
        "per_asset_opening_cap_x", "shared_gross_cap_x", "fee_pct_per_fill", "slippage_pct_per_side",
        "hard_stop_price_pct", "funding_modeled", "min_order_notional_usdt_by_asset", "drawdown_sampling",
    )}
    out = {
        **metadata,
        "btc_rsi": {**previous["btc_rsi"], "minimum_hold_hours": 6, "hard_stop_active_during_hold": True,
                    "partial_profit_taking_active_during_hold": False,
                    "normal_exits_resume": "first 15-minute decision at or after 6 hours"},
        "eth_only_original": previous["eth_only_original"],
        **results,
    }
    (OUTPUTS / "BTC_ETH_RSI6_BTC_6h_hold_2019_2026.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
