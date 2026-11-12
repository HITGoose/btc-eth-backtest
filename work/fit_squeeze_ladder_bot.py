import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
from math import floor, fsum

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from backtest_squeeze_short import END, WARMUP, ema, sma
from combined_crypto_portfolio import BAR, FEE, RULES, SLIP, TZ, WORK, close_enough, ms, read_market
from extended_crypto_portfolio import ETH_START, SWITCH, local


START = ms("2020-01-01T00:00:00+08:00")
SCALES = {"BTC": 10, "ETH": 100}
LIMIT_OFFSET = 0.002
ORDER_LIFETIME = 4 * BAR
INITIAL_STOP_DISTANCE = 0.02
LADDER_CAP = 5
REFERENCE = {
    2020: (59, 39, 2662.11, 33.8, 165.1),
    2021: (17, 24, 3889.54, 22.1, 42.0),
    2022: (61, 42, 12602.81, 30.7, 465.6),
    2023: (77, 106, 40102.89, 37.1, 402.2),
    2024: (55, 47, 84320.24, 33.7, 161.7),
    2025: (65, 48, 176094.74, 39.3, -6.7),
    2026: (52, 59, 645742.35, 45.1, 213.4),
}
TRAIN = (2020, 2021, 2022, 2023)
VALIDATION = (2024, 2025)
LIVE_TRADES = (
    ("BTC", "02:06:49.858", 75820.30, "05:56", 2),
    ("ETH", "01:43:14.578", 2229.45, "05:56", 5),
    ("BTC", "06:00:21.805", 74217.10, "20:18", None),
    ("ETH", "06:00:22.120", 2131.13, "16:24", 1),
    ("ETH", "16:43:14.835", 2112.07, "20:18", None),
)


def stamp(time):
    return datetime.fromisoformat(f"2026-11-09T{time}+08:00").timestamp()


def tick_time(time):
    return datetime.fromtimestamp(float(time), TZ).isoformat(timespec="milliseconds")


def limit_price(asset, reference, side, *, nearest_tick=False):
    scale = SCALES[asset]
    ticks = reference * (1 - side * LIMIT_OFFSET) * scale
    return (round(ticks) if nearest_tick else floor(ticks + 1e-9)) / scale


def stop_price(asset, entry, side, rung):
    scale = SCALES[asset]
    distance = rung / 100 if rung else -INITIAL_STOP_DISTANCE
    return round(entry * (1 + side * distance) * scale) / scale


def ladder_rung(favorable_pct, exit_policy):
    rung = max(0, floor(favorable_pct + 1e-10) - 1)
    if exit_policy == "uncapped" or (exit_policy == "trail_from_8pct" and favorable_pct >= 8 - 1e-10):
        return rung
    return min(LADDER_CAP, rung)


def live_replay():
    tapes = {}
    for asset in SCALES:
        pieces = [np.load(WORK / f"bot_fit_{asset}_{day}.npz") for day in ("2026-11-08", "2026-11-09")]
        tapes[asset] = [np.concatenate([p[k] for p in pieces]) for k in ("time", "price")]
        for p in pieces:
            p.close()
    rows = []
    for asset, opened, entry, observed, observed_rung in LIVE_TRADES:
        times, prices = tapes[asset]
        first, last = stamp(opened), stamp(observed + ":00") + 60
        l, r = np.searchsorted(times, [first, last])
        ticks = times[l:r], prices[l:r]
        seconds = np.arange(np.ceil(first / 3) * 3, last, 3)
        sampled = seconds, prices[np.searchsorted(times, seconds, side="right") - 1]
        row = {"asset": asset, "entry_price": entry, "reported_minute": observed, "reported_rung": observed_rung}
        for label, (ts, ps), cap in (("tick_cap_5", ticks, 5), ("tick_unlimited", ticks, 99),
                                     ("3s_sample_cap_5", sampled, 5)):
            favorable = np.maximum.accumulate(100 * (1 - ps / entry))
            rungs = np.clip(np.floor(favorable + 1e-10) - 1, 0, cap)
            stop = np.rint(entry * np.where(rungs > 0, 1 - rungs / 100, 1.02) * SCALES[asset]) / SCALES[asset]
            hits = np.flatnonzero(ps >= stop)
            armed = np.flatnonzero(rungs > 0)
            close = None if not len(hits) else int(hits[0])
            row[label] = {"armed_local": tick_time(ts[armed[0]]) if len(armed) else None,
                          "exit_local": None if close is None else tick_time(ts[close]),
                          "rung": None if close is None else int(rungs[close]),
                          "stop_price": None if close is None else float(stop[close])}
        match = row["3s_sample_cap_5"]
        assert match["rung"] == observed_rung and (observed_rung is None or match["exit_local"][11:16] == observed)
        rows.append(row)
    return rows


@dataclass(frozen=True)
class Settings:
    lookback: int
    aligned_lines: int
    squeeze_threshold: float = 0.25
    exit_policy: str = "fixed"

    @property
    def key(self):
        return f"N{self.lookback}_K{self.aligned_lines}_T{self.squeeze_threshold}_{self.exit_policy}"


@dataclass(frozen=True)
class Leg:
    start: int
    end: int
    first: int
    bars: dict
    width: np.ndarray
    squeeze: dict
    up: np.ndarray
    down: np.ndarray
    above_band: np.ndarray
    below_band: np.ndarray
    histogram: np.ndarray

    def signals(self, settings, *, macd_crosses=None):
        active = self.squeeze[settings.lookback] <= settings.squeeze_threshold
        if macd_crosses is None:
            bullish, bearish = self.histogram > 0, self.histogram < 0
        else:
            bullish, bearish = macd_crosses == 1, macd_crosses == -1
        buy = active & self.above_band & bullish & (self.up >= settings.aligned_lines)
        sell = active & self.below_band & bearish & (self.down >= settings.aligned_lines)
        assert not np.any(buy & sell)
        minimum = (self.start - self.first) // BAR
        return {self.first + (int(i) + 1) * BAR: (1 if buy[i] else -1)
                for i in np.flatnonzero(buy | sell) if minimum <= i < len(buy) - 1}


def build(path, start, end):
    raw = read_market(WORK / path, start - WARMUP, end)
    first = next(iter(raw))
    c = np.array([b.c for b in raw.values()])
    lines = np.stack([sma(c, n) for n in (20, 60, 120)] + [ema(c, n) for n in (20, 60, 120)])
    high, low = lines.max(axis=0), lines.min(axis=0)
    width = 100 * (high - low) / c
    squeeze = {n: np.r_[np.full(n - 1, np.inf), sliding_window_view(width, n).min(axis=1)]
               for n in (48, 96)}
    up = np.r_[np.zeros(3), (lines[:, 3:] > lines[:, :-3]).sum(axis=0)]
    down = np.r_[np.zeros(3), (lines[:, 3:] < lines[:, :-3]).sum(axis=0)]
    dif = ema(c, 12) - ema(c, 26)
    return Leg(start, end, first, {t: b for t, b in raw.items() if t >= start}, width, squeeze, up, down,
               c > high, c < low, dif - ema(dif, 9))


@dataclass
class Order:
    time: int
    side: int
    price: float
    qty: float


@dataclass
class Position:
    order: Order
    stop: float
    opened: int
    rung: int = 0
    opening_cash: float = 0.0

    def marked(self, price):
        return self.order.side * (price - self.order.price) * self.order.qty


@dataclass(frozen=True)
class Sizing:
    leverage: float = 5.0
    btc_step: float = RULES["BTC"][0]
    fee_reserve: bool = True


@dataclass
class Sleeve:
    asset: str
    exit_policy: str
    cash: float = 500.0
    realized: float = 0.0
    order: Order | None = None
    position: Position | None = None
    stats: Counter = field(default_factory=Counter)
    sizing: Sizing = Sizing()
    journal: list | None = None

    def credit(self, pnl):
        self.cash += pnl
        self.realized += pnl

    def equity(self, price):
        return self.cash + (self.position.marked(price) if self.position else 0.0)

    def place(self, t, ref, side, *, nearest_tick=False, size_multiplier=1.0):
        price = limit_price(self.asset, ref, side, nearest_tick=nearest_tick)
        step, minimum = RULES[self.asset]
        if self.asset == "BTC":
            step = self.sizing.btc_step
        leverage = self.sizing.leverage * size_multiplier
        reserve = 1 + 2 * leverage * FEE if self.sizing.fee_reserve else 1
        qty = floor((max(0.0, leverage * self.cash / reserve) / price + 1e-12) / step) * step
        if qty * price < minimum:
            self.stats["rejected"] += 1
            return
        self.order = Order(t, side, price, qty)
        self.stats["submitted"] += 1

    def close(self, price, reason, time):
        p = self.position
        price *= 1 - p.order.side * SLIP
        fee = price * p.order.qty * FEE
        net = p.marked(price) - fee
        self.credit(net)
        if self.journal is not None:
            notional = p.order.price * p.order.qty
            self.journal.append({"signal_ms": p.order.time, "opened_ms": p.opened, "closed_ms": time,
                                 "side": "LONG" if p.order.side == 1 else "SHORT", "reason": reason,
                                 "entry": p.order.price, "exit": price, "notional": notional, "net": net - FEE * notional,
                                 "rung": p.rung, "opening_sleeve_cash_usdt": p.opening_cash})
        self.stats[reason] += 1
        self.stats["fees"] += fee
        self.position = None

    def visit(self, price, t, at_open, *, advance_ladder=True, stop_at_level=False):
        if self.order and self.order.side * (price - self.order.price) <= 0:
            o, self.order = self.order, None
            fee = o.price * o.qty * FEE
            opening_cash = self.cash
            self.credit(-fee)
            self.stats["fees"] += fee
            self.stats["long" if o.side == 1 else "short"] += 1
            self.position = Position(o, stop_price(self.asset, o.price, o.side, 0), t, opening_cash=opening_cash)
        if p := self.position:
            side, entry = p.order.side, p.order.price
            if side * (price - p.stop) <= 0:
                self.close(price if at_open and not stop_at_level else p.stop, "ladder_exit" if p.rung else "hard_stop",
                           t if at_open else t + BAR)
                return
            if self.exit_policy == "target_8pct" and side * (price / entry - 1) * 100 >= 8 - 1e-10:
                self.close(entry * (1 + side * 0.08), "upper_target", t if at_open else t + BAR)
                return
            if self.exit_policy == "time_72h" and at_open and t - p.opened >= 72 * 4 * BAR:
                self.close(price, "time_exit", t)
                return
            if advance_ladder:
                self.update_ladder(price)

    def update_ladder(self, quote):
        if p := self.position:
            side, entry = p.order.side, p.order.price
            rung = ladder_rung(side * (quote / entry - 1) * 100, self.exit_policy)
            if rung > p.rung:
                p.rung = rung
                p.stop = stop_price(self.asset, entry, side, rung)


def simulate(legs_by_asset, settings, until, *, rebalance, favorable_first=False,
             sizing=Sizing(), replay=None, signal_gate=None, capture_trades=False, start=START, capture_equity=False):
    markets = {a: {t: b for leg in legs for t, b in leg.bars.items()} for a, legs in legs_by_asset.items()}
    signals = {a: {t: s for leg in legs for t, s in leg.signals(settings).items()
                   if signal_gate is None or signal_gate(a, t, s)} for a, legs in legs_by_asset.items()}
    switches = {a: {leg.end for leg in legs[:-1]} for a, legs in legs_by_asset.items()}
    books = {a: Sleeve(a, settings.exit_policy, sizing=sizing, journal=[] if capture_trades else None) for a in markets}
    boundaries = {ms(f"{y}-{m:02}-01T00:00:00+08:00"): (y, m) for y in range(2020, 2027) for m in range(1, 13)}
    equity = peak = 1000.0
    drawdown = 0.0
    years = {}
    first_insolvent = None
    closing_pnl = dict.fromkeys(markets, 0.0)
    equity_trace = [] if capture_equity else None
    for t in range(start, until, BAR):
        bars = {a: bars[t] for a, bars in markets.items()}
        if t in boundaries or t == start:
            y, month = boundaries.get(t, (datetime.fromtimestamp(t / 1000, TZ).year, 0))
            if month == 1 or t == start:
                years[y] = {"opening_equity_usdt": equity, "max_drawdown_pct": 0.0,
                            "counts": dict.fromkeys(books, 0), "long_counts": dict.fromkeys(books, 0),
                            "opening_pnl": closing_pnl.copy()}
                year_peak = equity
            if rebalance and t != start:
                marked = {a: book.equity(bars[a].o) for a, book in books.items()}
                target = fsum(marked.values()) / len(marked)
                for a, book in books.items():
                    book.cash += target - marked[a]
        row = years[y]
        for a, book in books.items():
            b = bars[a]
            if book.order and t >= book.order.time + ORDER_LIFETIME:
                book.order = None
                book.stats["expired"] += 1
            if not book.order and not book.position and (side := signals[a].get(t)):
                book.place(t, b.o, side)
            if trade := book.order or (book.position.order if book.position else None):
                before = book.stats["long"] + book.stats["short"]
                if replay is None:
                    first_is_high = (trade.side == -1) != favorable_first
                    extremes = (b.h, b.l) if first_is_high else (b.l, b.h)
                    for k, price in enumerate((b.o, *extremes, b.c)):
                        book.visit(price, t, k == 0)
                else:
                    replay(a, book, b, t)
                if book.stats["long"] + book.stats["short"] > before:
                    row["counts"][a] += 1
                    row["long_counts"][a] += trade.side == 1
            if t + BAR in switches[a]:
                if book.position:
                    book.close(b.c, "venue_switch", t + BAR)
                if book.order:
                    book.order = None
                    book.stats["venue_cancelled"] += 1
        closing_pnl = {a: book.realized + (book.position.marked(bars[a].c) if book.position else 0.0)
                       for a, book in books.items()}
        equity = 1000 + fsum(closing_pnl.values())
        if equity_trace is not None:
            equity_trace.append((t + BAR, equity))
        peak, year_peak = max(peak, equity), max(year_peak, equity)
        drawdown = max(drawdown, 100 * (1 - equity / peak))
        row["max_drawdown_pct"] = max(row["max_drawdown_pct"], 100 * (1 - equity / year_peak))
        row["ending_equity_usdt"] = equity
        row["marked_net_usdt_by_asset"] = {a: closing_pnl[a] - row["opening_pnl"][a] for a in books}
        if equity <= 0 and replay is not None:
            first_insolvent = {"time_local": local(t + BAR), "equity_usdt": equity}
            break
    close_enough(equity, fsum(book.equity(bars[a].c) for a, book in books.items()))
    for a, book in books.items():
        fills = book.stats["long"] + book.stats["short"]
        assert fills == sum(r["counts"][a] for r in years.values())
        assert book.stats["submitted"] == fills + book.stats["expired"] + book.stats["venue_cancelled"] + bool(book.order)
        closed = sum(book.stats[k] for k in ("hard_stop", "ladder_exit", "venue_switch", "upper_target", "time_exit"))
        assert fills == closed + bool(book.position)
    for r in years.values():
        r["return_pct"] = 100 * (r["ending_equity_usdt"] / r["opening_equity_usdt"] - 1)
        del r["opening_pnl"]
    return {"ending_equity_usdt": equity, "return_pct": 100 * (equity / 1000 - 1), "max_drawdown_pct": drawdown,
            **({"first_insolvent": first_insolvent} if first_insolvent is not None else {}),
            **({"trades": {a: book.journal for a, book in books.items()}} if capture_trades else {}),
            **({"equity_trace": equity_trace} if equity_trace is not None else {}),
            "years": years, "stats": {a: dict(book.stats) for a, book in books.items()},
            "open_positions": {a: {"opened_local": local(book.position.opened), "entry": book.position.order.price,
                                   "side": book.position.order.side, "rung": book.position.rung}
                               for a, book in books.items() if book.position}}


def count_error(result, years):
    return sum(abs(result["years"][y]["counts"][a] - count)
               for y in years for a, count in zip(("BTC", "ETH"), REFERENCE[y][:2]))


def count_relative_error(result):
    return fsum(abs(result["years"][y]["counts"][a] / count - 1)
                for y in TRAIN for a, count in zip(("BTC", "ETH"), REFERENCE[y][:2])) / (2 * len(TRAIN))


def main():
    trace = live_replay()
    print("Replayed all three reported ladder closes and two still-open positions on a common 3-second grid", flush=True)
    asof = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
    legs = {
        "BTC": [build("BTCUSDT_Binance_2019_2020_continuous.csv", START, SWITCH),
                build("BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH, asof)],
        "ETH": [build("ETHUSDT_Binance_2019_2021_early.csv", START, ETH_START),
                build("ETHUSDT_Bybit_2021_2026_continuous.csv", ETH_START, asof)],
    }
    default = Settings(96, 5)
    candidates = [Settings(*values) for values in product((48, 96), (5, 6), (0.10, 0.15, 0.25),
                                                          ("target_8pct", "trail_from_8pct", "time_72h"))]
    recent_end = ms("2026-11-10T13:15:00Z")
    recent = {a: build(f"{a}USDT_Bybit_bot_signal_review.csv", ms("2026-11-07T16:00:00Z"), recent_end) for a in legs}
    known_times = {"BTC": ("01:30", "06:00"), "ETH": ("01:30", "06:00", "16:30")}
    def matches_entry_tape(case):
        signals = {a: leg.signals(case) for a, leg in recent.items()}
        return all(signals[a].get(int(stamp(h + ":00") * 1000)) == -1
                   for a, windows in known_times.items() for h in windows)

    cases = [default, *(case for case in candidates if matches_entry_tape(case))]
    assert matches_entry_tape(default)
    fits = {}
    for case in cases:
        result = simulate(legs, case, END, rebalance=True)
        fits[case.key] = {"training_count_error": count_error(result, TRAIN),
                          "training_mean_absolute_relative_count_error": count_relative_error(result),
                          "validation_count_error": count_error(result, VALIDATION), "backtest": result}
        print(case.key, "train count error", fits[case.key]["training_count_error"], "end", round(result["ending_equity_usdt"], 2), flush=True)
    selected = min(cases[1:], key=lambda case: fits[case.key]["training_mean_absolute_relative_count_error"])
    sensitivity = {
        "selected_favorable_first": simulate(legs, selected, END, rebalance=True, favorable_first=True),
        "selected_no_rebalance": simulate(legs, selected, END, rebalance=False),
        "selected_continuous_through_2026": simulate(legs, selected, asof, rebalance=True),
    }
    for y, row in fits[selected.key]["backtest"]["years"].items():
        assert row == sensitivity["selected_continuous_through_2026"]["years"][y]
    out = {
        "start_local": local(START), "end_exclusive_local": local(END), "extension_end_exclusive_local": local(asof),
        "live_replay": trace, "report_reference": {y: dict(zip(("btc_trades", "eth_trades", "end_usdt", "year_mdd_pct",
                                                                "no_rebalance_return_pct"), row)) for y, row in REFERENCE.items()},
        "entry": "SMA/EMA 20,60,120 band, rolling minimum within the squeeze threshold, 3-bar slopes, price outside band and MACD sign, symmetric longs and shorts",
        "limit": "next-bar open proxy +/- 0.20%, floor to tick, 60 minutes, one order or position per symbol",
        "exit": "2% initial stop, arm at +2%, lock +1% and advance in 1% steps through locked +5%. Behavior beyond the fifth rung is a tested hypothesis.",
        "sizing": {"start_usdt": 1000, "starting_split": "500/500 BTC and ETH", "cap_x_each_sleeve": 5,
                   "rebalance": "month-open 50/50 marked equity without resizing existing trades", "fee_pct": 0.05,
                   "exit_slippage_pct": 0.02, "funding_modeled": False},
        "execution": "15-minute OHLC adverse extreme first, plus favorable-extreme-first sensitivity; bar-close marked equity",
        "selection": {"training_years": TRAIN, "holdout_years": VALIDATION,
                      "loss": "mean absolute relative error in per-asset annual trade counts", "eligible": "non-default cases matching the observed entry and exit tape"},
        "default": default.key, "selected": selected.key, "fits": fits, "sensitivity": sensitivity,
    }
    (WORK.parent / "outputs" / "BTC_ETH_bot_ladder_reconstruction_2020_2026.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("selected", selected.key, "training", fits[selected.key]["training_count_error"], "holdout", fits[selected.key]["validation_count_error"])
    for label, result in (("default", fits[default.key]["backtest"]), ("selected", fits[selected.key]["backtest"]), *sensitivity.items()):
        print(label, "end", result["ending_equity_usdt"], "max_dd", result["max_drawdown_pct"], "stats", result["stats"])
        for y, row in result["years"].items():
            print(y, row["counts"], row["return_pct"], row["max_drawdown_pct"], row["ending_equity_usdt"])


if __name__ == "__main__":
    main()
