import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path


WORK = Path(__file__).resolve().parent
DEFAULT_BYBIT_DIR = Path(r"D:\coding\btc_backtest_work")
if not DEFAULT_BYBIT_DIR.is_dir():
    DEFAULT_BYBIT_DIR = WORK.parent / "bybit_legacy"
BYBIT_DIR = Path(environ.get("BTC_BACKTEST_BYBIT_DIR", str(DEFAULT_BYBIT_DIR)))
START = 1617062400000
END = 1735660800000
BAR = 900_000
FEE = 0.0005
SLIP = 0.0002
TZ = timezone(timedelta(hours=8))
RULES = {"BTC": (0.001, 100), "ETH": (0.01, 5)}
BASE_PLANS = {"BTC": ("btc_matched_2021_2024", "actual_fee_5x_cap"),
              "ETH": ("eth_bybit_2021_2024", "eth_current_strategy")}
SLEEVE_PLANS = {"BTC": ("btc_sleeve_250", "actual_fee_5x_cap"),
                "ETH": ("eth_sleeve_250", "eth_current_strategy")}


def ms(s):
    return int(datetime.fromisoformat(s).timestamp() * 1000)


def year(t):
    return datetime.fromtimestamp(t / 1000, tz=TZ).year


def close_enough(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8), (a, b)


@dataclass(frozen=True)
class Bar:
    o: float
    h: float
    l: float
    c: float


@dataclass(frozen=True)
class Signal:
    opened: int
    closed: int
    side: int
    reason: str
    entry: float
    exit: float
    soft_exit_from: int = 0
    protect_profit: bool = False


@dataclass
class Position:
    signal: Signal
    qty: float
    first_qty: float
    fees: float
    partial_gross: float = 0
    reduced: bool = False
    profit_locked: bool = False

    @property
    def entry(self):
        return self.signal.entry

    @property
    def side(self):
        return self.signal.side

    @property
    def initial_stop(self):
        return self.entry * (1 - self.side * 0.02)

    @property
    def stop(self):
        return self.entry * (1 + self.side * 0.01) if self.profit_locked else self.initial_stop

    @property
    def target(self):
        return self.entry + (self.entry - self.initial_stop) * 0.4

    def marked(self, price):
        return (price - self.entry) * self.side * self.qty


def read_market(path, start=START, end=END):
    with path.open(encoding="utf-8", newline="") as f:
        bars = {}
        for row in csv.DictReader(f):
            time = int(row["timestamp"])
            if start <= time < end:
                assert time not in bars
                bars[time] = Bar(*(float(row[k]) for k in ("open", "high", "low", "close")))
    assert list(bars) == list(range(start, end, BAR))
    return bars


def read_plan(spec, start=START, end=END):
    prefix, scenario = spec
    with (WORK / f"{prefix}_trades.csv").open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["scenario"] == scenario]
    plan = {}
    for r in rows:
        t = ms(r["opened"])
        assert t not in plan and r["add_fills"] == "0" and float(r["funding"]) == 0
        plan[t] = Signal(t, ms(r["closed"]), 1 if r["side"] == "LONG" else -1,
                         r["reason"], float(r["first_entry"]), float(r["exit"]))
    doc = json.loads((WORK / f"{prefix}_summary.json").read_text())
    assert ms(doc["since"]) == start and ms(doc["until"]) == end and doc["continuous"]
    summary = doc["summaries"][scenario]
    assert summary["rejected"] == 0 and summary["overall"]["trades"] == len(rows)
    return plan, rows, summary


def run(markets, plans, bucket_of, opening, max_per_asset, start=START, end=END, *, capture_equity=False):
    assets = list(markets)
    cash = opening.copy()
    positions = {}
    events = {k: [] for k in assets}
    contributions = dict.fromkeys(assets, 0.0)
    peak = low = sum(opening.values())
    max_dd = 0.0
    max_open_exposure = 0.0
    both = same = opposite = both_signals = 0
    years = {}
    year_entries = defaultdict(Counter)
    prev_close = peak
    prev_assets = contributions.copy()
    reserve = 1 + 2 * 5 * FEE
    equity_marks = [] if capture_equity else None

    def credit(asset, amount):
        cash[bucket_of[asset]] += amount
        contributions[asset] += amount

    def close(asset, raw, time, reason):
        p = positions.pop(asset)
        assert (p.signal.closed, p.signal.reason) == (time, reason), (asset, time, reason, p.signal)
        assert time >= p.signal.soft_exit_from or reason in ("stop", "stop_gap", "end_of_data")
        exit_price = raw * (1 - p.side * SLIP)
        close_enough(exit_price, p.signal.exit)
        fee = exit_price * p.qty * FEE
        gross = p.marked(exit_price)
        credit(asset, gross - fee)
        fees = p.fees + fee
        net = gross + p.partial_gross - fees
        events[asset].append({"opened": p.signal.opened, "closed": time, "reason": reason,
                              "side": p.side, "qty": p.first_qty, "remaining_qty": p.qty,
                              "net": net, "fees": fees, "reduced": p.reduced})

    def reduce_if_touched(asset, price, bar_open_time):
        p = positions[asset]
        if bar_open_time < p.signal.soft_exit_from or p.reduced or p.side * (price - p.target) < 0:
            return
        step, _ = RULES[asset]
        qty = math.floor((p.first_qty * 0.2 + 1e-12) / step) * step
        if qty <= 0:
            return
        price = p.target * (1 - p.side * SLIP)
        gain = (price - p.entry) * p.side * qty
        fee = price * qty * FEE
        credit(asset, gain - fee)
        p.partial_gross += gain
        p.fees += fee
        p.qty -= qty
        p.reduced = True

    for t in range(start, end, BAR):
        bars = {k: markets[k][t] for k in assets if t in markets[k]}
        assert bars
        y = year(t)
        if y not in years:
            years[y] = {"opening_equity_usdt": prev_close, "starting_asset_contribution": prev_assets.copy(),
                        "peak_equity_usdt": prev_close, "low_equity_usdt": prev_close, "max_drawdown_pct": 0}
        annual = years[y]
        for asset in list(positions):
            p = positions[asset]
            bar = bars[asset]
            if (bar.o - p.stop) * p.side <= 0:
                close(asset, bar.o, t, "profit_floor_gap" if p.profit_locked else "stop_gap")
            elif p.signal.closed == t and p.signal.reason not in ("stop", "profit_floor", "end_of_data"):
                close(asset, bar.o, t, p.signal.reason)

        new = [asset for asset in assets if t in plans[asset]]
        assert all(asset not in positions and asset in bars for asset in new)
        both_signals += len(new) == 2
        by_bucket = defaultdict(list)
        for asset in new:
            by_bucket[bucket_of[asset]].append(asset)
        for bucket, candidates in by_bucket.items():
            current = [asset for asset in positions if bucket_of[asset] == bucket]
            equity = cash[bucket] + sum(positions[k].marked(bars[k].o) for k in current)
            existing = sum(positions[k].qty * bars[k].o for k in current)
            available_each = (5 * equity - existing) / reserve / len(candidates)
            asset_notional = min(max_per_asset * equity / reserve, available_each)
            for asset in candidates:
                signal = plans[asset][t]
                close_enough(signal.entry, bars[asset].o * (1 + signal.side * SLIP))
                step, min_notional = RULES[asset]
                qty = math.floor((asset_notional / signal.entry + 1e-12) / step) * step
                # A rejected order could change the later signal stream. Fail explicitly.
                assert qty * bars[asset].o >= min_notional, (asset, t, equity, asset_notional)
                fee = FEE * signal.entry * qty
                credit(asset, -fee)
                positions[asset] = Position(signal, qty, qty, fee)
                year_entries[y][asset] += 1
            bucket_positions = [k for k in positions if bucket_of[k] == bucket]
            equity_after = cash[bucket] + sum(positions[k].marked(bars[k].o) for k in bucket_positions)
            exposure_after = sum(positions[k].qty * bars[k].o for k in bucket_positions)
            assert exposure_after <= 5 * equity_after + 1e-8, (bucket, t, exposure_after, equity_after)
        if new:
            open_equity = sum(cash.values()) + sum(p.marked(bars[k].o) for k, p in positions.items())
            gross = sum(p.qty * bars[k].o for k, p in positions.items())
            max_open_exposure = max(max_open_exposure, gross / open_equity)
        if len(positions) == 2:
            both += 1
            if positions["BTC"].side == positions["ETH"].side:
                same += 1
            else:
                opposite += 1

        for asset in list(positions):
            p = positions[asset]
            bar = bars[asset]
            reduce_if_touched(asset, bar.o, t)
            adverse = bar.l if p.side == 1 else bar.h
            favorable = bar.h if p.side == 1 else bar.l
            if (adverse - p.stop) * p.side <= 0:
                close(asset, p.stop, t + BAR, "profit_floor" if p.profit_locked else "stop")
            else:
                reduce_if_touched(asset, favorable, t)
                if t + BAR == end:
                    close(asset, bar.c, end, "end_of_data")
                elif p.signal.protect_profit and p.reduced and (bar.c - p.entry) * p.side >= p.entry * 0.02:
                    p.profit_locked = True

        prev_assets = {k: contributions[k] + (positions[k].marked(bars[k].c) if k in positions else 0)
                       for k in assets}
        prev_close = sum(opening.values()) + sum(prev_assets.values())
        if equity_marks is not None:
            equity_marks.append(prev_close)
        close_enough(prev_close, sum(cash.values()) + sum(p.marked(bars[k].c) for k, p in positions.items()))
        peak = max(peak, prev_close)
        low = min(low, prev_close)
        max_dd = max(max_dd, 1 - prev_close / peak)
        annual["peak_equity_usdt"] = max(annual["peak_equity_usdt"], prev_close)
        annual["low_equity_usdt"] = min(annual["low_equity_usdt"], prev_close)
        annual["max_drawdown_pct"] = max(annual["max_drawdown_pct"], 100 * (1 - prev_close / annual["peak_equity_usdt"]))
        annual["ending_equity_usdt"] = prev_close
        annual["asset_net_usdt"] = {k: prev_assets[k] - annual["starting_asset_contribution"][k] for k in assets}

    assert not positions
    for asset, plan in plans.items():
        assert len(events[asset]) == len(plan)
        close_enough(contributions[asset], sum(row["net"] for row in events[asset]))
    for y, r in years.items():
        r["return_pct"] = 100 * (r["ending_equity_usdt"] / r["opening_equity_usdt"] - 1)
        r["entries"] = {k: year_entries[y][k] for k in assets}
        close_enough(sum(r["asset_net_usdt"].values()), r["ending_equity_usdt"] - r["opening_equity_usdt"])
        del r["starting_asset_contribution"]
    return {
        "initial_equity_usdt": sum(opening.values()), "ending_equity_usdt": prev_close,
        "return_pct": 100 * (prev_close / sum(opening.values()) - 1),
        "max_drawdown_pct": 100 * max_dd, "max_gross_exposure_at_entry": max_open_exposure,
        "peak_equity_usdt": peak, "low_equity_usdt": low,
        "both_assets_held_bars": both, "same_side_overlap_bars": same, "opposite_side_overlap_bars": opposite,
        "both_entry_signals_at_same_open": both_signals, "years": years, "asset_net_usdt": contributions,
        "entries": {k: len(events[k]) for k in assets},
        "hard_stops": {k: sum(t["reason"] in ("stop", "stop_gap") for t in events[k]) for k in assets},
        "time_exits": {k: sum(t["reason"] == "er_1h_timeout" for t in events[k]) for k in assets},
        "fees": {k: sum(t["fees"] for t in events[k]) for k in assets},
        **({"equity_marks_at_15m_close": equity_marks} if equity_marks is not None else {}),
    }, events


def verify_isolated(out, events, asset, records, summary):
    observed = events[asset]
    assert len(observed) == len(records)
    for row, r in zip(observed, records):
        assert (row["opened"], row["closed"], row["reason"]) == (ms(r["opened"]), ms(r["closed"]), r["reason"])
        assert row["reduced"] == bool(r["tp_fills"])
        for own, ref in (("qty", "first_qty"), ("remaining_qty", "qty"), ("net", "net"), ("fees", "fees")):
            close_enough(row[own], float(r[ref]))
    close_enough(out["asset_net_usdt"][asset], summary["overall"]["net"])
    eq = next(iter(summary["yearlyEquity"].values()))["openingEquity"]
    for y, stats in out["years"].items():
        x = summary["yearlyEquity"][str(y)]
        eq += stats["asset_net_usdt"][asset]
        close_enough(eq, x["endingEquity"])


def main():
    markets = {
        "BTC": read_market(BYBIT_DIR / "bybit_2025_completed_scratch.csv"),
        "ETH": read_market(WORK / "ETHUSDT_Bybit_2021_2024_verified.csv"),
    }
    base = {asset: read_plan(spec) for asset, spec in BASE_PLANS.items()}
    plans = {k: v[0] for k, v in base.items()}
    results = {}
    for asset, (_, rows, summary) in base.items():
        result, events = run({asset: markets[asset]}, {asset: plans[asset]}, {asset: asset}, {asset: 500}, 5)
        verify_isolated(result, events, asset, rows, summary)
        results[f"{asset}_only"] = result
    sleeves, events = run(markets, plans, {"BTC": "BTC", "ETH": "ETH"}, {"BTC": 250, "ETH": 250}, 5)
    for asset, spec in SLEEVE_PLANS.items():
        sleeve_plan, rows, summary = read_plan(spec)
        assert sleeve_plan == plans[asset], asset
        verify_isolated(sleeves, events, asset, rows, summary)
    results["fixed_250_each"] = sleeves
    results["shared_500"] = run(markets, plans, {"BTC": "shared", "ETH": "shared"}, {"shared": 500}, 2.5)[0]
    results["BTC_only_same_2p5_cap"] = run({"BTC": markets["BTC"]}, {"BTC": plans["BTC"]},
                                          {"BTC": "BTC"}, {"BTC": 500}, 2.5)[0]
    out = {"source": "Bybit BTCUSDT and ETHUSDT linear perpetual", "start_utc": datetime.fromtimestamp(START/1000, timezone.utc).isoformat(),
           "end_exclusive_utc": datetime.fromtimestamp(END/1000, timezone.utc).isoformat(), "candles_per_asset": (END-START)//BAR,
           "drawdown_sampling": "synchronized 15-minute bar-close account equity", "results": results}
    (WORK.parent / "outputs" / "BTC_ETH_simultaneous_portfolio_2021_2024.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for name, result in results.items():
        print(name, json.dumps(result))


if __name__ == "__main__":
    main()
