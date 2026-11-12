import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from combined_crypto_portfolio import WORK, BAR, close_enough, ms, read_market, read_plan, run, verify_isolated


START = ms("2019-09-23T17:45:00Z")
SWITCH = ms("2020-04-09T10:30:00Z")
ETH_START = ms("2021-03-30T00:00:00Z")
TZ = timezone(timedelta(hours=8))


def local(t):
    return datetime.fromtimestamp(t / 1_000, tz=TZ).isoformat()


def join_results(parts):
    years = {}
    for segment in parts:
        for y, row in segment["years"].items():
            if y not in years:
                years[y] = {**row, "entries": row["entries"].copy(), "asset_net_usdt": row["asset_net_usdt"].copy()}
                continue
            a = years[y]
            close_enough(a["ending_equity_usdt"], row["opening_equity_usdt"])
            cross_dd = 100 * (1 - row["low_equity_usdt"] / a["peak_equity_usdt"])
            a["max_drawdown_pct"] = max(a["max_drawdown_pct"], row["max_drawdown_pct"], cross_dd)
            a["peak_equity_usdt"] = max(a["peak_equity_usdt"], row["peak_equity_usdt"])
            a["low_equity_usdt"] = min(a["low_equity_usdt"], row["low_equity_usdt"])
            a["ending_equity_usdt"] = row["ending_equity_usdt"]
            a["return_pct"] = 100 * (a["ending_equity_usdt"] / a["opening_equity_usdt"] - 1)
            for key in ("entries", "asset_net_usdt"):
                for asset, value in row[key].items():
                    a[key][asset] = a[key].get(asset, 0) + value
    peak, drawdown, end = 500.0, 0.0, 500.0
    for y, r in years.items():
        close_enough(end, r["opening_equity_usdt"])
        close_enough(sum(r["asset_net_usdt"].values()), r["ending_equity_usdt"] - end)
        drawdown = max(drawdown, r["max_drawdown_pct"], 100 * (1 - r["low_equity_usdt"] / peak))
        peak = max(peak, r["peak_equity_usdt"])
        end = r["ending_equity_usdt"]
        r["cumulative_return_pct"] = 100 * (end / 500 - 1)
        r["drawdown_since_start_pct"] = drawdown
    totals = {}
    for key in ("entries", "asset_net_usdt", "hard_stops", "time_exits", "fees"):
        c = Counter()
        for p in parts:
            c.update(p[key])
        totals[key] = dict(c)
    close_enough(sum(totals["asset_net_usdt"].values()), end - 500)
    return {
        "years": years, "ending_equity_usdt": end, "return_pct": 100 * (end / 500 - 1),
        "max_drawdown_pct": drawdown,
        "max_gross_exposure_at_entry": max(x["max_gross_exposure_at_entry"] for x in parts),
        "both_assets_held_bars": sum(x["both_assets_held_bars"] for x in parts),
        **totals,
    }


def main():
    asof = json.loads((WORK / "btc_eth_extended_asof.json").read_text())
    end = asof["end_exclusive_ms"]
    inputs = [
        ("BTC", "BTCUSDT_Binance_2019_2020_continuous.csv", ("ext_btc_binance", "actual_fee_5x_cap"), START, SWITCH),
        ("BTC", "BTCUSDT_Bybit_2020_2026_continuous.csv", ("ext_btc_bybit", "actual_fee_5x_cap"), SWITCH, end),
        ("ETH", "ETHUSDT_Bybit_2021_2026_continuous.csv", ("ext_eth_bybit", "eth_current_strategy"), ETH_START, end),
    ]
    markets = []
    plans = []
    for asset, path, spec, first, stop in inputs:
        bars = read_market(WORK / path, first, stop)
        plan, records, summary = read_plan(spec, first, stop)
        test, events = run({asset: bars}, {asset: plan}, {asset: asset}, {asset: 500}, 5, first, stop)
        verify_isolated(test, events, asset, records, summary)
        markets.append(bars)
        plans.append(plan)

    early, early_events = run({"BTC": markets[0]}, {"BTC": plans[0]}, {"BTC": "shared"},
                              {"shared": 500}, 2.5, START, SWITCH)
    seed = early["ending_equity_usdt"]
    later, later_events = run({"BTC": markets[1], "ETH": markets[2]}, {"BTC": plans[1], "ETH": plans[2]},
                              {"BTC": "shared", "ETH": "shared"}, {"shared": seed}, 2.5, SWITCH, end)
    solo, _ = run({"BTC": markets[1]}, {"BTC": plans[1]}, {"BTC": "shared"},
                  {"shared": seed}, 2.5, SWITCH, end)
    combined = join_results([early, later])
    comparison = join_results([early, solo])
    # There is no earlier ETH data mixed into this portfolio.
    assert all(combined["years"][y]["entries"].get("ETH", 0) == 0 for y in (2019, 2020))
    assert combined["max_gross_exposure_at_entry"] <= 5
    # A hypothetical closing trade at the end of a venue/window is accounted for.
    terminal = [{"asset": asset, "at_local": local(e["closed"]), "net_usdt": e["net"]}
                for events in (early_events, later_events) for asset, rows in events.items()
                for e in rows if e["reason"] == "end_of_data"]
    out = {"initial_equity_usdt": 500, "start_local": local(START), "end_exclusive_local": local(end),
           "exchange_server_time_local": local(asof["server_time_ms"]), "btc_bybit_switch_local": local(SWITCH),
           "eth_first_eligible_local": local(ETH_START), "per_asset_opening_cap_x": 2.5,
           "portfolio_opening_cap_x": 5, "drawdown_sampling": "synchronized 15-minute bar-close account equity",
           "fee_pct_per_fill": 0.05, "slippage_pct_per_side": 0.02, "hard_stop_pct": 2, "funding_modeled": False,
           "verified_market_candles": {"BTC_Binance": len(markets[0]), "BTC_Bybit": len(markets[1]), "ETH_Bybit": len(markets[2])},
           "venue_or_window_end_closes": terminal, "shared_500": combined, "btc_only_same_2p5_cap": comparison}
    file = WORK.parent / "outputs" / "BTC_ETH_simultaneous_portfolio_2019_2026.json"
    file.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("Coverage", out["start_local"], out["end_exclusive_local"], out["verified_market_candles"], "terminal", terminal)
    for label, res in (("combined", combined), ("BTC-only", comparison)):
        print(label, "total", res["ending_equity_usdt"], res["return_pct"], res["max_drawdown_pct"], res["entries"])
        for y, row in res["years"].items():
            print(y, json.dumps(row))


if __name__ == "__main__":
    main()
