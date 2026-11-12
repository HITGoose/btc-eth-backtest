import csv
import json
from collections import Counter
from statistics import median

from combined_crypto_portfolio import FEE, SLIP, WORK, close_enough, ms
from extended_crypto_portfolio import ETH_START, START, SWITCH, local
from run_original_ladder_compare import markets, prefixes
from summarize_btc_eth_rsi_priority import replay_journal
from summarize_btc_rsi_4h import OUTPUTS
from summarize_original_ladder_compare import describe, ladder_segment


END = ms("2026-01-01T00:00:00+08:00")
TAG = "through2025"


def journal(prefix):
    with (WORK / f"{prefix}_trades.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def year_end_mark(result, parts):
    costs = Counter()
    asset_costs = Counter()
    for part in parts:
        for asset, trades in part[1].items():
            for row in trades:
                if row["reason"] == "end_of_data" and ms(row["closed"]) == END:
                    side = 1 if row["side"] == "LONG" else -1
                    exit_price, qty = float(row["exit"]), float(row["qty"])
                    reference = exit_price / (1 - side * SLIP)
                    cost = qty * (exit_price * FEE + reference * SLIP)
                    costs[row["side"]] += cost
                    asset_costs[asset] += cost
    annual = result["years"][2025]
    settled = result["ending_equity_usdt"]
    marked = settled + costs.total()
    # The last bar is not a trough that determines any reported drawdown.
    assert annual["low_equity_usdt"] < settled
    assert 100 * (1 - settled / annual["peak_equity_usdt"]) < annual["max_drawdown_pct"]
    assert 100 * (1 - settled / max(r["peak_equity_usdt"] for r in result["years"].values())) < result["max_drawdown_pct"]
    pnl = {side: result["by_side"][side]["net_usdt"] + costs[side] for side in ("LONG", "SHORT")}
    close_enough(sum(pnl.values()), marked - 500)
    return {"ending_equity_usdt": marked, "return_pct": 100 * (marked / 500 - 1),
            "return_2025_pct": 100 * (marked / annual["opening_equity_usdt"] - 1),
            "by_side_net_usdt": pnl, "synthetic_exit_cost_usdt": costs.total(),
            "synthetic_exit_cost_by_asset_usdt": dict(asset_costs),
            "ending_equity_if_closed_usdt": settled}


def assert_previous_window(result, previous):
    assert result["status"] == "completed"
    for y, row in result["years"].items():
        reference = previous["years"][str(y)]
        ending = row["ending_equity_usdt"] if y < 2025 else result["year_end_mark"]["ending_equity_usdt"]
        close_enough(ending, reference["ending_equity_usdt"])
        close_enough(row["max_drawdown_pct"], reference["max_drawdown_pct"])
        assert row["entries"] == reference["entries"]
    for key in ("ending_equity_usdt", "return_pct"):
        close_enough(result["year_end_mark"][key], previous["through_2025"][key])
    close_enough(result["max_drawdown_pct"], previous["through_2025"]["max_drawdown_pct"])
    assert result["total_trades"] == previous["through_2025"]["trades"]


def by_entry(parts):
    rows = {(a, r["opened"], r["side"]): r for p in parts for a, trades in p[1].items() for r in trades}
    assert len(rows) == sum(len(trades) for p in parts for trades in p[1].values())
    return rows


def compare_matched(original, overlay):
    base, changed = by_entry(original), by_entry(overlay)
    paired = base.keys() & changed.keys()
    exits = {k: r for k, r in changed.items() if r["reason"] in ("ladder_gap", "ladder_lock")}
    common_exits = exits.keys() & paired
    times = [(ms(base[k]["closed"]) - ms(changed[k]["closed"])) / 3_600_000 for k in common_exits]

    def pnl_pct(row):
        return 100 * float(row["net"]) / (float(row["first_qty"]) * float(row["first_entry"]))

    net_deltas = {k: pnl_pct(changed[k]) - pnl_pct(base[k]) for k in common_exits}
    worst_2024 = min((k for k in common_exits if local(ms(k[1])).startswith("2024-")), key=net_deltas.get)
    before, after = base[worst_2024], changed[worst_2024]
    return {
        "matched_entries": len(paired), "baseline_only_entries": len(base.keys() - paired),
        "overlay_only_entries": len(changed.keys() - paired), "ladder_exit_count": len(exits),
        "ladder_exits_by_side": dict(Counter(r["side"] for r in exits.values())),
        "ladder_exits_with_matching_baseline_entry": len(common_exits),
        "matched_ladder_exits_before_original_close": sum(hours > 0 for hours in times),
        "median_matched_ladder_exit_hours_earlier": median(times) if times else None,
        "matched_ladder_exits_with_improved_net_per_notional": sum(delta > 0 for delta in net_deltas.values()),
        "matched_non_ladder_exits_with_changed_time_or_price": sum(
            any(changed[k][field] != base[k][field] for field in ("closed", "exit")) for k in paired - exits.keys()),
        "largest_2024_pnl_decrease_per_opening_notional": {
            "asset": worst_2024[0], "side": worst_2024[2], "opened_local": local(ms(worst_2024[1])),
            "original_closed_local": local(ms(before["closed"])), "overlay_closed_local": local(ms(after["closed"])),
            "original_net_pct": pnl_pct(before), "overlay_net_pct": pnl_pct(after),
        },
        "example_btc_2020_04_28": {"original": base.get(("BTC", "2020-04-28T09:45:00.000Z", "LONG")),
                                  "overlay": changed.get(("BTC", "2020-04-28T09:45:00.000Z", "LONG"))},
    }


def main():
    early_market, late_market = markets(END)
    early_prefix, late_prefix = f"{TAG}_control_binance", f"{TAG}_control_bybit"
    base_early = replay_journal(early_prefix, early_market, {"BTC": "original"}, 500, START, SWITCH)
    base_late = replay_journal(late_prefix, late_market, {"BTC": "BTC", "ETH": "ETH"},
                               base_early[0]["ending_equity_usdt"], SWITCH, END)
    assert journal(early_prefix) == journal("our_ladder_control_binance")
    old = [r for r in journal("our_ladder_control_bybit") if ms(r["opened"]) < END]
    for actual, reference in zip(journal(late_prefix), old, strict=True):
        if actual["reason"] == "end_of_data":
            assert ms(reference["closed"]) >= END
            for key in ("scenario", "side", "setup", "opened", "first_entry", "first_qty"):
                assert actual[key] == reference[key]
        else:
            assert actual == reference
    base_parts = [base_early, base_late]
    cases = {"original": describe(base_parts)}
    cases["original"]["year_end_mark"] = year_end_mark(cases["original"], base_parts)
    audit = json.loads((WORK / f"{TAG}_ladder_refinement.json").read_text(encoding="utf-8"))
    assert not (audit["unresolved_15m"] or audit["unresolved_1m"]), audit
    for mode in ("ladder_overlay", "ladder_72h"):
        a = prefixes(mode, "adverse", TAG)
        f = prefixes(mode, "favorable", TAG)
        for first, second in zip(a, f):
            assert journal(first) == journal(second), mode
        early = ladder_segment(a[0], early_market, 500, START, SWITCH)
        late = ladder_segment(a[1], late_market, early[0]["ending_equity_usdt"], SWITCH, END)
        parts = [early, late]
        cases[mode] = describe(parts)
        cases[mode]["year_end_mark"] = year_end_mark(cases[mode], parts)
        if mode == "ladder_overlay":
            matched = compare_matched(base_parts, parts)

    prior = json.loads((OUTPUTS / "BTC_ETH_original_entries_ladder_exit_2019_2026.json").read_text(encoding="utf-8"))
    assert_previous_window(cases["original"], prior["results"]["original"])
    assert_previous_window(cases["ladder_72h"], prior["results"]["ladder_72h_adverse"])
    audit["both_extreme_orders_produce_identical_trade_journals"] = True
    comparison = {
        name: {**result["year_end_mark"], "max_drawdown_pct": result["max_drawdown_pct"],
               "entries": result["total_trades"],
               "annual_returns_pct": {y: row["return_pct"] if y < 2025 else result["year_end_mark"]["return_2025_pct"]
                                      for y, row in result["years"].items()}}
        for name, result in cases.items()
    }
    out = {
        "initial_equity_usdt": 500, "start_local": local(START), "end_exclusive_local": local(END),
        "btc_bybit_switch_local": local(SWITCH), "eth_first_eligible_local": local(ETH_START),
        **{k: prior[k] for k in ("per_asset_opening_cap_x", "portfolio_opening_cap_x", "drawdown_sampling",
                                "fee_pct_per_fill", "slippage_pct_per_side", "funding_modeled")},
        "entry": prior["entry"], "exit_settings": prior["exit"],
        "year_end_reporting": "Use year_end_mark for marked equity and net P&L before the cost of liquidating any open positions. "
                              "The trade journal and other ending equity fields include synthetic year-end closes.",
        "overlay": "Original partial at +0.8%, MA5/MA30 exit, structure exit and one-hour range short exit are retained. "
                   "The simulated ladder may stop the remaining position earlier. The original hard-stop priority is "
                   "retained on bars where the ladder has not armed.",
        "comparison_at_year_end_mark": comparison, "matched_entry_comparison": matched,
        "detailed_results_with_synthetic_closes": cases, "refinement": audit,
    }
    (OUTPUTS / "BTC_ETH_original_vs_ladder_overlay_2019_2025.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for name, result in cases.items():
        print(name, {k: result[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries",
                                            "asset_net_usdt", "total_trades", "by_side", "exit_reasons",
                                            "median_holding_hours", "longest_trade", "terminal_settlements", "year_end_mark")})
        print("annual", {y: (r["return_pct"], r["ending_equity_usdt"], r["max_drawdown_pct"], r["entries"])
                         for y, r in result["years"].items()})
    print("matched", json.dumps(matched))


if __name__ == "__main__":
    main()
