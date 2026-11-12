import csv
import json
from collections import Counter
from dataclasses import dataclass
from math import floor, fsum
from statistics import median

from combined_crypto_portfolio import BAR, FEE, RULES, SLIP, WORK, close_enough, ms, year
from extended_crypto_portfolio import START, SWITCH, join_results, local
from run_original_ladder_compare import ASOF, AUDIT, VARIANTS, markets, prefixes
from summarize_btc_eth_rsi_priority import compare_reference, replay_journal
from summarize_btc_rsi_4h import OUTPUTS, trade_totals


@dataclass(frozen=True)
class Partial:
    bar_open: int
    qty: float
    net: float


@dataclass(frozen=True)
class Execution:
    opened: int
    exit_bar: int
    closed: int
    side: int
    qty: float
    entry: float
    net: float
    fees: float
    partial: Partial | None

    def live_qty(self, cutoff):
        return self.qty - self.partial.qty if self.partial and self.partial.bar_open < cutoff else self.qty

    def mark(self, price, cutoff):
        qty = self.live_qty(cutoff)
        realized = self.partial.net if qty < self.qty else 0
        return realized + qty * (price - self.entry) * self.side - self.qty * self.entry * FEE


def execution(row, asset, bars, end, config):
    opened, exit_bar, closed = (ms(row[k]) for k in ("opened", "exit_bar_open", "closed"))
    side = {"LONG": 1, "SHORT": -1}[row["side"]]
    qty, entry, exit_price, net, fees = (float(row[k]) for k in ("first_qty", "entry", "exit", "net", "fees"))
    remaining = float(row["qty"])
    rung, reason = int(row["ladder_rung"]), row["reason"]
    start_bar, last = bars[opened], bars[exit_bar]
    assert row["add_fills"] == "0" and float(row["funding"]) == 0
    assert ms(row["signal"]) == opened <= exit_bar and qty * start_bar.o >= RULES[asset][1]
    close_enough(entry, start_bar.o * (1 + side * SLIP))
    initial_stop = entry * (1 - side * 0.02)
    close_enough(float(row["initial_stop"]), initial_stop)
    scale = 10 if asset == "BTC" else 100
    assert 0 <= rung <= 5
    stop = floor(entry * (1 + side * rung * 0.01) * scale + 0.5) / scale if rung else initial_stop
    close_enough(float(row["final_stop"]), stop)
    partial, partial_gross, partial_fee = None, 0.0, 0.0
    if row.get("tp_fills"):
        assert row["tp_fills"] == "1" and config["ladderOverlay"]
        assert config["takeProfitSteps"] == [0.4] and config["takeProfitFraction"] == 0.2
        part_bar = ms(row["tp_bar_open"])
        assert opened <= part_bar <= exit_bar
        level = entry + (entry - initial_stop) * 0.4
        candle = bars[part_bar]
        assert candle.h >= level if side == 1 else candle.l <= level
        step = RULES[asset][0]
        part_qty = floor((qty * 0.2 + 1e-12) / step) * step
        assert part_qty > 0
        close_enough(remaining, qty - part_qty)
        part_exit = level * (1 - side * SLIP)
        partial_gross = side * part_qty * (part_exit - entry)
        partial_fee = FEE * part_qty * part_exit
        partial = Partial(part_bar, part_qty, partial_gross - partial_fee)
        close_enough(float(row["partial_gross"]), partial_gross)
    else:
        assert not row.get("tp_bar_open")
        close_enough(remaining, qty)
    if reason in ("stop", "ladder_lock"):
        assert closed == exit_bar + BAR and last.l <= stop <= last.h
        assert (rung > 0) == (reason == "ladder_lock")
        raw = stop
    elif reason in ("stop_gap", "ladder_gap"):
        assert closed == exit_bar and (last.o - stop) * side <= 0
        assert (rung > 0) == (reason == "ladder_gap")
        raw = last.o
    elif reason == "ladder_time_cap":
        hold_cap = config["ladderMaxHours"]
        assert hold_cap and closed == exit_bar and closed - opened == hold_cap * 4 * BAR
        raw = last.o
    elif reason in ("ma5_ma30_cross", "15m_structure_flip", "er_1h_timeout"):
        assert config["ladderOverlay"] and opened < closed == exit_bar
        if reason == "er_1h_timeout":
            assert side == -1 and closed - opened == 4 * BAR
        raw = last.o
    else:
        assert reason == "end_of_data" and closed == end == exit_bar + BAR
        raw = last.c
    close_enough(exit_price, raw * (1 - side * SLIP))
    close_enough(fees, FEE * (qty * entry + remaining * exit_price) + partial_fee)
    close_enough(net, partial_gross + side * remaining * (exit_price - entry) - fees)
    return Execution(opened, exit_bar, closed, side, qty, entry, net, fees, partial)


def ladder_segment(prefix, market, seed, start, end):
    doc = json.loads((WORK / f"{prefix}_summary.json").read_text())
    assert doc["continuous"] and (ms(doc["since"]), ms(doc["until"])) == (start, end)
    with (WORK / f"{prefix}_trades.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by_asset = {a: [r for r in rows if r["scenario"] == a] for a in market}
    opens, exits = {}, {}
    for asset, records in by_asset.items():
        summary = doc["summaries"][asset]
        assert len(records) == summary["overall"]["trades"]
        trades = [execution(r, asset, market[asset], end, summary["config"]) for r in records]
        opens[asset] = {trade.opened: trade for trade in trades}
        exits[asset] = {trade.exit_bar: trade for trade in trades}
        assert len(opens[asset]) == len(trades) == len(exits[asset])

    years, positions = {}, {}
    realized = dict.fromkeys(market, 0.0)
    marks = realized.copy()
    equity = seed
    first_insolvent = None
    maximum_exposure = 0.0
    both_held = 0
    for t in range(start, end, BAR):
        y = year(t)
        if y not in years:
            opening = marks.copy()
            years[y] = {"opening_equity_usdt": equity, "peak_equity_usdt": equity, "low_equity_usdt": equity,
                        "max_drawdown_pct": 0.0, "entries": dict.fromkeys(market, 0)}
        annual = years[y]
        entered = False
        for a in market:
            ending = exits[a].get(t)
            if ending and ending.closed == t:
                assert positions.pop(a) == ending
                realized[a] += ending.net
            if trade := opens[a].get(t):
                assert a not in positions
                positions[a] = trade
                annual["entries"][a] += 1
                entered = True
        both_held += len(positions) == 2
        if entered:
            open_equity = seed + fsum(realized.values()) + fsum(p.mark(market[a][t].o, t) for a, p in positions.items())
            gross = fsum(p.live_qty(t) * market[a][t].o for a, p in positions.items())
            assert gross <= 5 * open_equity + 1e-8
            maximum_exposure = max(maximum_exposure, gross / open_equity)
        for a in market:
            ending = exits[a].get(t)
            if ending and ending.closed == t + BAR:
                assert positions.pop(a) == ending
                realized[a] += ending.net
        marks = {a: realized[a] + (positions[a].mark(market[a][t].c, t + BAR) if a in positions else 0.0) for a in market}
        prior_equity = equity
        equity = seed + fsum(marks.values())
        if first_insolvent is None and equity <= 0:
            first_insolvent = {
                "bar_close_local": local(t + BAR), "equity_usdt": equity, "previous_bar_equity_usdt": prior_equity,
                "cumulative_realized_pnl_usdt": realized.copy(),
                "open_positions": {a: {"side": "LONG" if p.side == 1 else "SHORT", "opened_local": local(p.opened),
                                        "entry_price": p.entry, "quantity": p.live_qty(t + BAR), "bar_close_price": market[a][t].c,
                                        "marked_pnl_usdt": p.mark(market[a][t].c, t + BAR)} for a, p in positions.items()},
            }
        annual["ending_equity_usdt"] = equity
        annual["peak_equity_usdt"] = max(annual["peak_equity_usdt"], equity)
        annual["low_equity_usdt"] = min(annual["low_equity_usdt"], equity)
        annual["max_drawdown_pct"] = max(annual["max_drawdown_pct"], 100 * (1 - equity / annual["peak_equity_usdt"]))
        annual["asset_net_usdt"] = {a: marks[a] - opening[a] for a in market}
    assert not positions
    for r in years.values():
        r["return_pct"] = 100 * (r["ending_equity_usdt"] / r["opening_equity_usdt"] - 1)
    for a, summary in doc["summaries"].items():
        close_enough(seed + realized[a], summary["endingEquity"])
        total = seed
        for y, r in years.items():
            total += r["asset_net_usdt"][a]
            if str(y) in summary["yearlyEquity"]:
                close_enough(total, summary["yearlyEquity"][str(y)]["endingEquity"])
    segment = {"years": years, "ending_equity_usdt": equity, "asset_net_usdt": realized,
               "first_insolvent": first_insolvent,
               "entries": {a: len(recs) for a, recs in by_asset.items()}, "max_gross_exposure_at_entry": maximum_exposure,
               "both_assets_held_bars": both_held,
               "hard_stops": {a: sum(r["reason"] in ("stop", "stop_gap") for r in recs) for a, recs in by_asset.items()},
               "time_exits": {a: sum(r["reason"] in ("er_1h_timeout", "ladder_time_cap") for r in recs) for a, recs in by_asset.items()},
               "fees": {a: fsum(float(r["fees"]) for r in recs) for a, recs in by_asset.items()}}
    return segment, by_asset, {a: s["rejected"] for a, s in doc["summaries"].items()}


def describe(parts):
    trades = [dict(r, asset=a) for part in parts for a, rows in part[1].items() for r in rows]
    for part in parts:
        if breach := part[0].get("first_insolvent"):
            last = ms(breach["bar_close_local"])
            return {"status": "insolvent", "first_insolvent": breach,
                    "entries_before_first_insolvent_close": sum(ms(row["opened"]) < last for row in trades)}
    out = join_results([part[0] for part in parts])
    out["status"] = "completed"
    rejected = Counter()
    for part in parts:
        rejected.update(part[2])
    out["total_trades"] = len(trades)
    out["total_fees_usdt"] = fsum(float(r["fees"]) for r in trades)
    out["by_side"] = {side: trade_totals([r for r in trades if r["side"] == side]) for side in ("LONG", "SHORT")}
    out["exit_reasons"] = dict(Counter(r["reason"] for r in trades))
    out["rejected_entries"] = dict(rejected)
    out["median_holding_hours"] = median((ms(r["closed"]) - ms(r["opened"])) / 3_600_000 for r in trades)
    longest = max(trades, key=lambda r: ms(r["closed"]) - ms(r["opened"]))
    out["longest_trade"] = {"asset": longest["asset"], "side": longest["side"], "opened_local": local(ms(longest["opened"])),
                            "closed_local": local(ms(longest["closed"])), "reason": longest["reason"], "net_usdt": float(longest["net"])}
    out["terminal_settlements"] = [{"asset": r["asset"], "opened_local": local(ms(r["opened"])),
                                    "closed_local": local(ms(r["closed"])), "side": r["side"], "net_usdt": float(r["net"])}
                                   for r in trades if r["reason"] == "end_of_data"]
    snapshot = out["years"][2025]
    out["through_2025"] = {"ending_equity_usdt": snapshot["ending_equity_usdt"],
                           "return_pct": snapshot["cumulative_return_pct"], "max_drawdown_pct": snapshot["drawdown_since_start_pct"],
                           "trades": sum(sum(r["entries"].values()) for y, r in out["years"].items() if y <= 2025)}
    close_enough(fsum(float(r["net"]) for r in trades), out["ending_equity_usdt"] - 500)
    return out


def main():
    early_market, late_market = markets()
    early_base = replay_journal("our_ladder_control_binance", early_market, {"BTC": "original"}, 500, START, SWITCH)
    late_base = replay_journal("our_ladder_control_bybit", late_market, {"BTC": "BTC", "ETH": "ETH"},
                               early_base[0]["ending_equity_usdt"], SWITCH, ASOF)
    control = describe([early_base, late_base])
    previous = json.loads((OUTPUTS / "BTC_ETH_simultaneous_portfolio_2019_2026.json").read_text())
    compare_reference(control, previous["shared_500"])
    audit = json.loads(AUDIT.read_text())
    if not (audit["unresolved_15m"] or audit["unresolved_1m"]):
        for mode in ("ladder", "ladder_72h"):
            for first, second in zip(prefixes(mode, "adverse"), prefixes(mode, "favorable")):
                assert (WORK / f"{first}_trades.csv").read_bytes() == (WORK / f"{second}_trades.csv").read_bytes(), mode
        audit["both_extreme_orders_produce_identical_trade_journals"] = True
    cases = {"original": control}
    for mode, path in VARIANTS:
        early_prefix, late_prefix = prefixes(mode, path)
        early = ladder_segment(early_prefix, early_market, 500, START, SWITCH)
        late = ladder_segment(late_prefix, late_market, early[0]["ending_equity_usdt"], SWITCH, ASOF)
        cases[f"{mode}_{path}"] = describe([early, late])
    out = {
        "initial_equity_usdt": 500, "start_local": local(START), "end_exclusive_local": local(ASOF),
        **{k: previous[k] for k in ("btc_bybit_switch_local", "eth_first_eligible_local", "per_asset_opening_cap_x",
                                    "portfolio_opening_cap_x", "drawdown_sampling", "fee_pct_per_fill", "slippage_pct_per_side", "funding_modeled")},
        "entry": "existing BTC/ETH main long/short rules, same next-open market fills, no RSI overlay",
        "exit": {"hard_stop_pct": 2, "ladder_activation_pct": 2, "first_lock_pct": 1, "rung_step_pct": 1,
                 "maximum_lock_pct": 5, "full_exit_at_stop": True, "time_cap_hours_in_timed_variant": 72,
                 "trigger_quote": "traded price; exact archive order used for reconciled intervals",
                 "bar_stop_fill": "stop level with slippage inside a 15-minute candle; opening gaps use the opening price",
                 "maintenance_margin_and_liquidations_modeled": False},
        "refinement": audit, "results": cases,
        "separate_live_evidence": {
            "asset": "ETH", "side": "SHORT", "entry_local": "2026-11-09T16:43:00+08:00", "entry_price": 2112.07,
            "first_lock_local": "2026-11-10T21:30:00+08:00", "first_lock_price": 2090.95,
            "exit_notice_local": "2026-11-10T21:36:00+08:00", "reported_rung": 2, "reported_net_usdt": 3.27,
            "used_in_backtest": False,
            "bybit_quote_comparison": json.loads((WORK / "eth_2112_exit_quotes_audit.json").read_text()),
            "prior_bybit_mark_price_checks": json.loads((WORK / "nov09_bot_mark_quote_checks.json").read_text()),
        },
    }
    (OUTPUTS / "BTC_ETH_original_entries_ladder_exit_2019_2026.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for name, result in cases.items():
        if result["status"] == "insolvent":
            print(name, result)
            continue
        print(name, "2019-25", result["through_2025"], "all", *(result[k] for k in ("ending_equity_usdt", "return_pct",
              "max_drawdown_pct", "entries", "asset_net_usdt", "exit_reasons", "total_fees_usdt", "median_holding_hours", "longest_trade")))
        print("annual", {y: (round(r["return_pct"], 3), round(r["ending_equity_usdt"], 2), r["entries"]) for y, r in result["years"].items()})
        print("sides", result["by_side"], "settlements", result["terminal_settlements"])


if __name__ == "__main__":
    main()
