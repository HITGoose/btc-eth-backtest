import argparse
import json
from math import fsum
from statistics import median

from combined_crypto_portfolio import WORK, close_enough, ms, read_market
from extended_crypto_portfolio import ETH_START, START, SWITCH, local
from summarize_btc_eth_rsi_priority import compare_reference, replay_journal, summarize
from summarize_btc_rsi_4h import OUTPUTS, RSI_SETUP, WARMUP
from summarize_btc_rsi_6h_hold import rows_for


def audit_rsi(result, btc_trades, minimum_hours):
    rows = [r for r in btc_trades if r["setup"] == RSI_SETUP]
    pnl = [float(r["net"]) for r in rows]
    wins = [n for n in pnl if n > 1e-9]
    losses = [n for n in pnl if n < -1e-9]
    holds = [(ms(r["closed"]) - ms(r["opened"])) / 3_600_000 for r in rows]
    reasons = [r["reason"] for r in rows]
    early_normal = sum(h < minimum_hours and reason not in ("stop", "stop_gap", "end_of_data")
                       for h, reason in zip(holds, reasons))
    assert early_normal == 0
    reference = result["btc_rsi_entries"]["totals"]
    assert len(pnl) == reference["trades"]
    close_enough(fsum(pnl), reference["net_usdt"])
    return {
        **result,
        "btc_rsi_trade_audit": {
            "wins": len(wins), "losses": len(losses), "breakeven": len(pnl) - len(wins) - len(losses),
            "win_rate_pct": 100 * len(wins) / len(pnl) if pnl else None,
            "winning_trades_net_usdt": fsum(wins), "losing_trades_net_usdt": fsum(losses),
            "median_holding_hours": median(holds) if holds else None,
            # The engine records an intrabar stop at the end of the candle in which it occurs.
            "hard_stops_during_lock": sum((reason == "stop" and h <= minimum_hours) or
                                          (reason == "stop_gap" and h < minimum_hours)
                                          for h, reason in zip(holds, reasons)),
            "ordinary_exits_during_lock": early_normal,
            "data_boundary_exits_during_lock": sum(h < minimum_hours and reason == "end_of_data"
                                                   for h, reason in zip(holds, reasons)),
        },
        "last_btc_open_local": local(ms(btc_trades[-1]["opened"])) if btc_trades else None,
    }


def main(first_hour, last_hour, range_only):
    previous = json.loads((OUTPUTS / "BTC_ETH_RSI6_BTC_6h_hold_2019_2026.json").read_text())
    end = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
    btc_early = read_market(WORK / "BTCUSDT_Binance_2019_2020_continuous.csv", START - WARMUP, SWITCH)
    btc_late = read_market(WORK / "BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH - WARMUP, end)
    eth_late = read_market(WORK / "ETHUSDT_Bybit_2021_2026_continuous.csv", ETH_START, end)
    grid = {}
    qualifier = "range_" if range_only else ""
    if first_hour == 1 and not range_only:
        old_early = rows_for("rsi4h_priority_binance", "rsi_4h_priority")
        grid[0] = {
            "btc_solo": audit_rsi(previous["btc_solo"]["previous"], old_early + rows_for("rsi4h_priority_bybit", "rsi_4h_priority"), 0),
            "btc_eth_shared": audit_rsi(previous["btc_eth_shared"]["previous"], old_early + rows_for("rsi4h_shared_priority_bybit", "BTC"), 0),
        }
    for hours in range(first_hour, last_hour + 1):
        prefix = f"rsi4h_sweep_{qualifier}hold{hours}h"
        label = f"rsi_4h_{qualifier}hold{hours}h"
        early = replay_journal(f"{prefix}_binance", {"BTC": btc_early}, {"BTC": label}, 500, START, SWITCH)
        seed = early[0]["ending_equity_usdt"]
        solo = replay_journal(f"{prefix}_solo_bybit", {"BTC": btc_late}, {"BTC": label}, seed, SWITCH, end)
        joint = replay_journal(f"{prefix}_shared_bybit", {"BTC": btc_late, "ETH": eth_late},
                               {"BTC": "BTC", "ETH": "ETH"}, seed, SWITCH, end)
        grid[hours] = {
            "btc_solo": audit_rsi(summarize([early, solo]), early[1]["BTC"] + solo[1]["BTC"], hours),
            "btc_eth_shared": audit_rsi(summarize([early, joint]), early[1]["BTC"] + joint[1]["BTC"], hours),
        }

    if not range_only:
        for account, result in grid.get(6, {}).items():
            compare_reference(result, previous[account]["hold_6h"])
            assert result["btc_rsi_trade_audit"]["hard_stops_during_lock"] == (
                previous[account]["hold_6h_rsi_holding"]["hard_stops_during_first_6h"])

    metadata = {k: v for k, v in previous.items() if k not in ("btc_rsi", "btc_solo", "btc_eth_shared")}
    rsi_rule = {k: v for k, v in previous["btc_rsi"].items() if k not in ("minimum_hold_hours", "normal_exits_resume")}
    if range_only:
        rsi_rule["entry_regime"] = {"indicator": "Kaufman efficiency ratio", "closed_price_changes": 20,
                                    "bar_minutes": 15, "exclusive_max": 0.25, "at": "entry signal close"}
    out = {**metadata, "btc_rsi": {**rsi_rule, "minimum_hold_hours_tested": list(grid),
                                    "normal_exits_resume": "first 15-minute decision at or after the minimum hold"},
           "results_by_minimum_hold_hours": grid}
    path = OUTPUTS / f"BTC_ETH_BTC_RSI6_{qualifier}hold_{first_hour}h_to_{last_hour}h_2019_2026.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for hours, cases in grid.items():
        for account, result in cases.items():
            print(hours, account, *(result[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries",
                  "asset_net_usdt", "hard_stops", "time_exits", "below_minimum_order_attempts", "last_btc_open_local")))
            print("rsi", result["btc_rsi_trade_audit"], "net", result["btc_rsi_entries"]["totals"]["net_usdt"])
            print("years", {y: (r["return_pct"], r["entries"]) for y, r in result["years"].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("first_hour", type=int, nargs="?", default=1)
    parser.add_argument("last_hour", type=int, nargs="?", default=6)
    parser.add_argument("--range-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.first_hour <= args.last_hour <= 24:
        parser.error("Expected an inclusive holding range between 1 and 24 hours")
    main(args.first_hour, args.last_hour, args.range_only)
