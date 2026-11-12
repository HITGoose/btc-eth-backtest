import json
from collections import Counter
from dataclasses import dataclass
from math import floor, fsum

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from combined_crypto_portfolio import BAR, FEE, RULES, SLIP, WORK, close_enough, ms, read_market, read_plan, run, verify_isolated, year
from extended_crypto_portfolio import ETH_START, START, SWITCH, join_results, local


END = ms("2025-12-31T16:00:00Z")
ETH_EARLY = ms("2019-12-14T00:00:00Z")
WARMUP = 15 * 96 * BAR
HOUR = 4 * BAR
TREND_THRESHOLDS = ((24, 0.20), (120, 0.10))
CAP = 2.5
GROSS_CAP = 5
RESERVE = 1 + 2 * GROSS_CAP * FEE
TICKS = {"BTC": 0.1, "ETH": 0.01}


def sma(x, n):
    total = np.r_[0.0, np.cumsum(x)]
    return np.r_[np.full(n - 1, np.nan), (total[n:] - total[:-n]) / n]


def ema(x, n):
    values = np.empty_like(x)
    values[0] = x[0]
    for i in range(1, len(x)):
        values[i] = values[i - 1] + (x[i] - values[i - 1]) * 2 / (n + 1)
    return values


def hourly_regimes(closes, first_close, *, thresholds=TREND_THRESHOLDS):
    path = np.r_[0.0, np.cumsum(np.abs(np.diff(closes)))]
    efficiencies = []
    for hours, _ in thresholds:
        move = closes[hours:] - closes[:-hours]
        travel = path[hours:] - path[:-hours]
        signed = np.divide(move, travel, out=np.zeros_like(move), where=travel > 0)
        efficiencies.append(np.r_[np.full(hours, np.nan), signed])
    result = {}
    for i in range(max(hours for hours, _ in thresholds), len(closes)):
        signed = tuple(float(values[i]) for values in efficiencies)
        signs = [1 if value >= threshold else -1 if value <= -threshold else 0
                 for value, (_, threshold) in zip(signed, thresholds)]
        tag = {1: "up", -1: "down", 0: "range"}[signs[0]] if signs[0] == signs[1] else "transition"
        result[first_close + i * HOUR] = (tag, *signed)
    return result


@dataclass(frozen=True)
class Leg:
    start: int
    end: int
    bars: dict
    entries: dict
    exits: dict
    regimes: dict

    def regime_at(self, time):
        return self.regimes[time // HOUR * HOUR]


def build_leg(path, start, end):
    raw = read_market(WORK / path, start - WARMUP, end)
    first = next(iter(raw))
    prices = np.array([(b.o, b.h, b.l, b.c) for b in raw.values()])
    _, highs, lows, closes = prices.T
    lines = np.stack([sma(closes, n) for n in (20, 60, 120)] + [ema(closes, n) for n in (20, 60, 120)])
    band_bottom = lines.min(axis=0)
    widths = 100 * (lines.max(axis=0) - band_bottom) / closes
    recent_min = np.r_[np.full(95, np.nan), sliding_window_view(widths, 96).min(axis=1)]
    down = np.r_[np.zeros(3), (lines[:, 3:] < lines[:, :-3]).sum(axis=0)]
    dif = ema(closes, 12) - ema(closes, 26)
    candidates = (recent_min <= 0.25) & (down >= 5) & (closes < band_bottom) & (dif < ema(dif, 9))

    aligned = (-first % HOUR) // BAR
    count = (len(prices) - aligned) // 4
    groups = prices[aligned:aligned + count * 4].reshape(-1, 4, 4)
    hour_close = groups[:, -1, 3]
    prev = np.r_[hour_close[0], hour_close[:-1]]
    true_range = np.maximum(groups[:, :, 1].max(axis=1), prev) - np.minimum(groups[:, :, 2].min(axis=1), prev)
    hourly_atr = sma(true_range, 14)
    first_hour_close = first + aligned * BAR + HOUR
    hourly = {first_hour_close + i * HOUR: value for i, value in enumerate(hourly_atr)}

    first_index = (start - first) // BAR
    entries = {}
    for i in np.flatnonzero(candidates):
        if not first_index <= i < len(prices) - 1:
            continue
        t = first + (int(i) + 1) * BAR
        window = closes[i - 20:i + 1]
        travel = float(np.abs(np.diff(window)).sum())
        in_range = travel == 0 or abs(window[-1] - window[0]) / travel < 0.25
        atr = float(hourly[t // HOUR * HOUR])
        assert atr > 0
        entries[t] = (bool(in_range), atr)

    difference = sma(closes, 5) - sma(closes, 30)
    tops, bottoms, exits = [], [], {}
    for i in range(4, len(prices)):
        neighbors = (i - 4, i - 3, i - 1, i)
        if all(highs[j] < highs[i - 2] for j in neighbors):
            tops.append(highs[i - 2])
        if all(lows[j] > lows[i - 2] for j in neighbors):
            bottoms.append(lows[i - 2])
        if i < first_index:
            continue
        t = first + (i + 1) * BAR
        if difference[i - 1] <= 0 < difference[i]:
            exits[t] = "ma5_ma30_cross"
        elif len(tops) >= 2 and len(bottoms) >= 2 and tops[-1] > tops[-2] and closes[i] >= bottoms[-1] > bottoms[-2]:
            exits[t] = "15m_structure_flip"
    return Leg(start, end, {t: b for t, b in raw.items() if t >= start}, entries, exits,
               hourly_regimes(hour_close, first_hour_close))


@dataclass(frozen=True)
class Order:
    time: int
    limit: float
    qty: float
    in_range: bool
    atr: float


@dataclass
class Short:
    order: Order
    opened: int
    qty: float
    fees: float
    partial_gross: float = 0.0
    reduced: bool = False
    mfe: float = 0.0
    exit_reason: str | None = None

    def marked(self, price):
        return self.qty * (self.order.limit - price)


def simulate(legs_by_asset, *, regime_only=None, fixed_notional=None, with_journal=False):
    markets = {a: {t: b for leg in legs for t, b in leg.bars.items()} for a, legs in legs_by_asset.items()}
    signals = {a: {t: context for leg in legs for t, context in leg.entries.items()
                   if regime_only is None or leg.regime_at(t)[0] == regime_only} for a, legs in legs_by_asset.items()}
    exits = {a: {t: reason for leg in legs for t, reason in leg.exits.items()} for a, legs in legs_by_asset.items()}
    segment_ends = {a: {leg.end for leg in legs} for a, legs in legs_by_asset.items()}
    first = min(leg.start for legs in legs_by_asset.values() for leg in legs)
    end = max(leg.end for legs in legs_by_asset.values() for leg in legs)
    positions, resting, years = {}, {}, {}
    orders = {a: Counter(submitted=0, filled=0, expired=0, boundary_cancelled=0, rejected=0) for a in markets}
    trades = {a: [] for a in markets}
    contributions = dict.fromkeys(markets, 0.0)
    last_marks = contributions.copy()
    seed = 500.0 if fixed_notional is None else 1_000_000.0
    cash = equity = peak = seed
    drawdown = 0.0

    def credit(asset, amount):
        nonlocal cash
        cash += amount
        contributions[asset] += amount

    def close(asset, raw, time, reason):
        p = positions.pop(asset)
        price = raw * (1 + SLIP)
        gross = p.marked(price)
        fee = p.qty * price * FEE
        credit(asset, gross - fee)
        trades[asset].append({"signal": p.order.time, "entry_notional": p.order.qty * p.order.limit,
                              "opened": p.opened, "closed": time, "reason": reason,
                              "net": gross + p.partial_gross - p.fees - fee, "fees": p.fees + fee})

    def reduce(asset, price, target):
        p = positions[asset]
        if p.reduced or price > target:
            return
        step, _ = RULES[asset]
        qty = floor((p.order.qty * 0.2 + 1e-12) / step) * step
        if not qty:
            return
        execution = target * (1 + SLIP)
        gross = qty * (p.order.limit - execution)
        fee = qty * execution * FEE
        credit(asset, gross - fee)
        p.qty -= qty
        p.fees += fee
        p.partial_gross += gross
        p.reduced = True

    for t in range(first, end, BAR):
        bars = {a: rows[t] for a, rows in markets.items() if t in rows}
        assert bars
        y = year(t)
        if y not in years:
            years[y] = {"opening_equity_usdt": equity, "peak_equity_usdt": equity, "low_equity_usdt": equity,
                        "max_drawdown_pct": 0.0, "entries": dict.fromkeys(markets, 0), "opening_marks": last_marks.copy()}
        annual = years[y]
        for asset, order in list(resting.items()):
            if t >= order.time + 4 * BAR:
                orders[asset]["expired"] += 1
                del resting[asset]
        # The just-closed bar can submit only if that symbol was already flat.
        new = [a for a in bars if a not in positions and a not in resting and t in signals[a]]
        for asset, p in list(positions.items()):
            b = bars[asset]
            if b.o >= p.order.limit * 1.02:
                close(asset, b.o, t, "stop_gap")
            elif p.exit_reason:
                close(asset, b.o, t, p.exit_reason)
        if new:
            if fixed_notional is None:
                open_equity = cash + fsum(p.marked(bars[a].o) for a, p in positions.items())
                reserved = fsum(p.qty * bars[a].o for a, p in positions.items()) + fsum(o.qty * o.limit for o in resting.values())
                notional = max(0, min(CAP * open_equity / RESERVE, (GROSS_CAP * open_equity - reserved) / RESERVE / len(new)))
            else:
                notional = fixed_notional
            for asset in new:
                ticks_per_unit = round(1 / TICKS[asset])
                limit = floor(bars[asset].o * 1.002 * ticks_per_unit + 1e-9) / ticks_per_unit
                step, minimum = RULES[asset]
                qty = floor((notional / limit + 1e-12) / step) * step
                if qty * limit >= minimum:
                    resting[asset] = Order(t, limit, qty, *signals[asset][t])
                    orders[asset]["submitted"] += 1
                else:
                    orders[asset]["rejected"] += 1

        time = t + BAR
        for asset, b in bars.items():
            late_fill = False
            order = resting.get(asset)
            if order and b.h >= order.limit:
                del resting[asset]
                late_fill = b.o < order.limit
                fee = order.qty * order.limit * FEE
                credit(asset, -fee)
                positions[asset] = Short(order, time if late_fill else t, order.qty, fee)
                orders[asset]["filled"] += 1
                annual["entries"][asset] += 1
            if p := positions.get(asset):
                entry = p.order.limit
                stop, target = entry * 1.02, entry * 0.992
                if b.o >= stop:
                    close(asset, b.o, t, "stop_gap")
                else:
                    if not late_fill:
                        reduce(asset, b.o, target)
                    if b.h >= stop:
                        close(asset, stop, time, "stop")
                    else:
                        # The candle low might precede an intrabar short fill. The close cannot.
                        favorable = b.c if late_fill else b.l
                        reduce(asset, favorable, target)
                        if time in segment_ends[asset]:
                            close(asset, b.c, time, "end_of_data")
                        else:
                            p.mfe = max(p.mfe, (entry - favorable) / entry)
                            p.exit_reason = exits[asset].get(time)
                            if not p.exit_reason and p.order.in_range and time - p.opened == 4 * BAR and p.mfe < min(0.004, 0.5 * p.order.atr / entry):
                                p.exit_reason = "er_1h_timeout"
            if time in segment_ends[asset] and asset in resting:
                orders[asset]["boundary_cancelled"] += 1
                del resting[asset]

        last_marks = {a: contributions[a] + (positions[a].marked(bars[a].c) if a in positions else 0) for a in markets}
        equity = seed + fsum(last_marks.values())
        peak = max(peak, equity)
        drawdown = max(drawdown, 100 * (1 - equity / peak))
        annual["ending_equity_usdt"] = equity
        annual["peak_equity_usdt"] = max(annual["peak_equity_usdt"], equity)
        annual["low_equity_usdt"] = min(annual["low_equity_usdt"], equity)
        annual["max_drawdown_pct"] = max(annual["max_drawdown_pct"], 100 * (1 - equity / annual["peak_equity_usdt"]))
        annual["asset_net_usdt"] = {a: last_marks[a] - annual["opening_marks"][a] for a in markets}

    assert not positions and not resting
    close_enough(cash, equity)
    for asset, counts in orders.items():
        assert counts["submitted"] == counts["filled"] + counts["expired"] + counts["boundary_cancelled"]
        assert counts["filled"] == len(trades[asset]) == sum(r["entries"][asset] for r in years.values())
        close_enough(contributions[asset], fsum(r["net"] for r in trades[asset]))
    for r in years.values():
        del r["opening_marks"]
        r["return_pct"] = 100 * (r["ending_equity_usdt"] / r["opening_equity_usdt"] - 1)
    result = {
        "ending_equity_usdt": equity, "return_pct": 100 * (equity / seed - 1), "max_drawdown_pct": drawdown,
        "years": years, "asset_net_usdt": contributions, "entries": {a: len(rows) for a, rows in trades.items()},
        "wins": {a: sum(r["net"] > 0 for r in rows) for a, rows in trades.items()},
        "fees": {a: fsum(r["fees"] for r in rows) for a, rows in trades.items()},
        "hard_stops": {a: sum(r["reason"] in ("stop", "stop_gap") for r in rows) for a, rows in trades.items()},
        "time_exits": {a: sum(r["reason"] == "er_1h_timeout" for r in rows) for a, rows in trades.items()},
        "orders": orders,
        "venue_or_end_settlements": [{"asset": a, "closed_local": local(r["closed"]), "net_usdt": r["net"]}
                                     for a, rows in trades.items() for r in rows if r["reason"] == "end_of_data"],
    }
    return (result, trades) if with_journal else result


def baseline_plan(asset, leg, prefix):
    plan, rows, summary = read_plan((prefix, f"{asset.lower()}_short_only"), leg.start, leg.end)
    result, events = run({asset: leg.bars}, {asset: plan}, {asset: asset}, {asset: 500}, 5, leg.start, leg.end)
    verify_isolated(result, events, asset, rows, summary)
    for signal in plan.values():
        if signal.reason in ("ma5_ma30_cross", "15m_structure_flip"):
            assert leg.exits.get(signal.closed) == signal.reason, (asset, local(signal.closed), signal.reason)
    return plan


def main():
    btc_early = build_leg("BTCUSDT_Binance_2019_2020_continuous.csv", START, SWITCH)
    btc_late = build_leg("BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH, END)
    eth_early = build_leg("ETHUSDT_Binance_2019_2021_early.csv", ETH_EARLY, ETH_START)
    eth_late = build_leg("ETHUSDT_Bybit_2021_2026_continuous.csv", ETH_START, END)
    new = {
        "btc_solo": simulate({"BTC": [btc_early, btc_late]}),
        "eth_solo": simulate({"ETH": [eth_early, eth_late]}),
        "btc_eth_shared": simulate({"BTC": [btc_early, btc_late], "ETH": [eth_late]}),
    }
    old_btc_early = baseline_plan("BTC", btc_early, "side_btc_binance")
    old_btc_late = baseline_plan("BTC", btc_late, "squeeze_btc_control_bybit")
    old_eth_early = baseline_plan("ETH", eth_early, "squeeze_eth_control_binance")
    old_eth_late = baseline_plan("ETH", eth_late, "squeeze_eth_control_bybit")

    def old_segment(markets, plans, seed, first, last):
        return run(markets, plans, dict.fromkeys(markets, "shared"), {"shared": seed}, CAP, first, last)[0]

    early_btc = old_segment({"BTC": btc_early.bars}, {"BTC": old_btc_early}, 500, START, SWITCH)
    early_eth = old_segment({"ETH": eth_early.bars}, {"ETH": old_eth_early}, 500, ETH_EARLY, ETH_START)
    seed_btc = early_btc["ending_equity_usdt"]
    old = {
        "btc_solo": join_results([early_btc, old_segment({"BTC": btc_late.bars}, {"BTC": old_btc_late}, seed_btc, SWITCH, END)]),
        "eth_solo": join_results([early_eth, old_segment({"ETH": eth_late.bars}, {"ETH": old_eth_late}, early_eth["ending_equity_usdt"], ETH_START, END)]),
        "btc_eth_shared": join_results([early_btc, old_segment({"BTC": btc_late.bars, "ETH": eth_late.bars},
                                       {"BTC": old_btc_late, "ETH": old_eth_late}, seed_btc, SWITCH, END)]),
    }
    out = {
        "start_local": local(START), "end_exclusive_local": local(END), "btc_bybit_switch_local": local(SWITCH),
        "eth_solo_start_local": local(ETH_EARLY), "eth_shared_start_local": local(ETH_START), "initial_usdt_each": 500,
        "per_asset_cap_at_submission_x": CAP, "shared_cap_at_submission_x": GROSS_CAP,
        "fee_pct_per_fill": 100 * FEE, "exit_slippage_pct": 100 * SLIP, "funding_modeled": False,
        "entry": {"moving_averages": ["SMA20", "SMA60", "SMA120", "EMA20", "EMA60", "EMA120"],
                  "width_pct_max_in_last_96": 0.25, "falling_lines_vs_three_bars_ago": 5,
                  "close_below_band": True, "macd_short": "DIF < DEA", "limit_premium_pct": 0.2,
                  "limit_reference": "next 15-minute bar open", "limit_tick_by_asset": TICKS, "expiry_minutes": 60,
                  "fill": "first 15-minute high at or above the limit, at limit price", "size": "fixed and reserved at submission"},
        "exits": {"hard_stop_pct": 2, "partial_size_pct": 20, "partial_price_move_pct": 0.8,
                  "soft": ["MA5 crosses above MA30", "15-minute bullish structure", "original low-ER one-hour exit"],
                  "intrabar_fill": "hard stop active; only the candle close can confirm an after-fill favorable move",
                  "elapsed_time_for_intrabar_fill": "from end of first touching 15-minute candle"},
        "drawdown": "marked portfolio equity at 15-minute closes",
        "original_short_only": old, "reconstructed_squeeze_short_only": new,
    }
    (WORK.parent / "outputs" / "BTC_ETH_squeeze_expansion_short_2019_2025.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for name in new:
        for label, r in (("original", old[name]), ("squeeze", new[name])):
            print(name, label, *(r[k] for k in ("ending_equity_usdt", "return_pct", "max_drawdown_pct", "entries", "asset_net_usdt", "fees", "hard_stops", "time_exits")))
            if label == "squeeze":
                print("orders", r["orders"], "wins", r["wins"], "settlements", r["venue_or_end_settlements"])
            for y, row in r["years"].items():
                print(y, row["ending_equity_usdt"], row["return_pct"], row["max_drawdown_pct"], row["entries"], row["asset_net_usdt"])


if __name__ == "__main__":
    main()
