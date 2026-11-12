import csv
import json
import math
from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from combined_crypto_portfolio import BYBIT_DIR, WORK


TZ = timezone(timedelta(hours=8))
BAR = 900_000
FEE = 0.0005
SLIP = 0.0002
TARGET = 0.008
STOP = 0.02
STEP = 0.001
MIN_EXIT_IMPROVEMENT = 0.001
HARD = {"stop", "stop_gap"}
EXIT_NAME = {
    "stop": "2%硬止损",
    "stop_gap": "2%硬止损（跳空）",
    "ma5_ma30_cross": "MA5/MA30反转",
    "15m_structure_flip": "15分钟结构反转",
    "er_1h_timeout": "低ER一小时退出",
    "end_of_data": "区间结束结算",
}


def ms(value):
    return int(datetime.fromisoformat(value).timestamp() * 1_000)


def local(timestamp):
    return datetime.fromtimestamp(timestamp / 1_000, tz=TZ)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def close_enough(left, right):
    assert math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-8), (left, right)


@dataclass
class Candle:
    time: int
    opening: float
    high: float
    low: float
    close: float


@dataclass
class Position:
    side: int
    entry: float
    original_qty: float
    qty: float
    fees: float
    partial_gross: float = 0
    target_time: int | None = None
    mfe: float = 0
    mae: float = 0

    @classmethod
    def open(cls, side, entry, qty):
        return cls(side, entry, qty, qty, FEE * entry * qty)

    @property
    def stop(self):
        return self.entry * (1 - self.side * STOP)

    @property
    def target(self):
        return self.entry + (self.entry - self.stop) * 0.4

    def observe(self, price):
        move = self.side * (price - self.entry) / self.entry
        self.mfe = max(self.mfe, move)
        self.mae = max(self.mae, -move)

    def reduce_if_touched(self, price, time):
        if self.target_time is not None or self.side * (price - self.target) < 0:
            return
        self.target_time = time
        qty = math.floor((self.original_qty * 0.2 + 1e-12) / STEP) * STEP
        fill = self.target * (1 - self.side * SLIP)
        self.partial_gross += self.side * qty * (fill - self.entry)
        self.fees += FEE * fill * qty
        self.qty -= qty

    def advance(self, bar):
        self.observe(bar.opening)
        if self.side * (bar.opening - self.stop) <= 0:
            return ("stop_gap", bar.opening, bar.time)
        self.reduce_if_touched(bar.opening, bar.time)
        favorable = bar.high if self.side == 1 else bar.low
        adverse = bar.low if self.side == 1 else bar.high
        if self.side * (adverse - self.stop) <= 0:
            self.observe(self.stop)
            return ("stop", self.stop, bar.time + BAR)
        self.observe(favorable)
        self.observe(adverse)
        self.reduce_if_touched(favorable, bar.time + BAR)
        return None

    def settle(self, price):
        fill = price * (1 - self.side * SLIP)
        gross = self.partial_gross + self.side * (fill - self.entry) * self.qty
        fees = self.fees + FEE * fill * self.qty
        return fill, gross, fees, gross - fees


def read_market(path, start, end):
    result = {}
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            time = int(row["timestamp"])
            if start <= time < end:
                result[time] = Candle(time, *(float(row[k]) for k in ("open", "high", "low", "close")))
    assert list(result) == list(range(start, end, BAR))
    return result


def held_path(position, market, start, end):
    for time in range(start, end, BAR):
        stop = position.advance(market[time])
        if stop is not None:
            return stop
    return None


def compare_delayed_exit(actual, market, closed, hours):
    end = closed + hours * 4 * BAR
    if end not in market:
        return None
    held = copy(actual)
    stop = held_path(held, market, closed, end)
    reason, price, time = stop or ("scheduled", market[end].opening, end)
    if reason == "scheduled" and held.side * (price - held.stop) <= 0:
        reason = "stop_gap"
    return {
        "net": held.settle(price)[-1],
        "target_after_exit": held.target_time is not None and actual.target_time is None,
        "stopped": reason in HARD,
        "ending": time,
    }


def four_hour_target(side, market, start, end):
    position = Position.open(side, market[start].opening * (1 + side * SLIP), 1)
    stop = held_path(position, market, start, end)
    if position.target_time is not None:
        return "达标"
    return "先到2%止损" if stop else "未达标"


def explain(row, market, segment, ident):
    opened = ms(row["opened"])
    closed = ms(row["closed"])
    side = 1 if row["side"] == "LONG" else -1
    qty = float(row["first_qty"])
    entry = float(row["first_entry"])
    net = float(row["net"])
    reason = row["reason"]
    close_enough(entry, market[opened].opening * (1 + side * SLIP))
    assert int(row["add_fills"]) == 0 and float(row["funding"]) == 0 and int(row["tp_orders"]) == 1

    position = Position.open(side, entry, qty)
    stop = held_path(position, market, opened, closed)
    if reason == "stop_gap":
        assert stop is None
        stop = position.advance(market[closed])
    if reason in HARD:
        assert stop is not None and stop[0] == reason and stop[2] == closed
        raw_exit = stop[1]
    else:
        assert stop is None
        raw_exit = market[closed - BAR].close if reason == "end_of_data" else market[closed].opening
    fill, gross, fees, replay_net = position.settle(raw_exit)
    for key, value in (("exit", fill), ("gross", gross), ("fees", fees), ("net", replay_net),
                       ("qty", position.qty), ("partial_gross", position.partial_gross),
                       ("initial_stop", position.stop)):
        close_enough(float(row[key]), value)
    reached = position.target_time is not None
    assert reached == bool(row["tp_fills"])

    soft = reason not in HARD and reason != "end_of_data"
    h1 = compare_delayed_exit(position, market, closed, 1) if soft else None
    h4 = compare_delayed_exit(position, market, closed, 4) if soft else None
    d1 = h1["net"] - net if h1 else None
    d4 = h4["net"] - net if h4 else None
    post_target = h4["target_after_exit"] if h4 else None
    benchmark = entry * qty * MIN_EXIT_IMPROVEMENT
    if reason in HARD:
        exit_class = "2%硬止损"
    elif h1 is None or h4 is None:
        exit_class = "后续窗口不足"
    elif min(d1, d4) >= benchmark:
        if net > 0:
            exit_class = "盈利离场偏早候选"
        elif min(h1["net"], h4["net"]) >= 0:
            exit_class = "亏损软退偏早候选"
        else:
            exit_class = "两档延后均改善"
    elif max(d1, d4) <= -benchmark:
        exit_class = "原退出优于两档延后"
    else:
        exit_class = "两档结论不一致或差距小"

    horizon = opened + 16 * BAR
    original4, delayed4 = None, None
    if horizon - BAR in market:
        original4 = four_hour_target(side, market, opened, horizon)
        delayed4 = four_hour_target(side, market, opened + 4 * BAR, horizon)
    timing = not reached and original4 not in (None, "达标") and delayed4 == "达标"
    if reached:
        entry_class = "持仓内达标"
    elif reason in HARD:
        entry_class = "2%硬止损先到"
    elif timing:
        entry_class = "延后入场达标"
    elif post_target:
        entry_class = "出场后方向走出"
    elif h4 is None or original4 is None:
        entry_class = "后续窗口不足"
    else:
        entry_class = "短线内未达目标"

    no_partial = Position.open(side, entry, qty).settle(raw_exit)[-1] - net if reached else None
    if no_partial is None:
        partial_class = "未减仓"
    elif no_partial > 1e-8:
        partial_class = "减仓少赚"
    elif no_partial < -1e-8:
        partial_class = "减仓保护收益"
    else:
        partial_class = "两者基本一致"

    first_hour = Position.open(side, entry, qty)
    held_path(first_hour, market, opened, min(opened + 4 * BAR, closed))
    pre4 = side * (market[opened - BAR].close / market[opened - 17 * BAR].close - 1)
    return {
        "id": ident, "year": local(opened).year, "quarter": (local(opened).month - 1) // 3 + 1,
        "exchange": segment["exchange"], "opened": local(opened).isoformat(), "closed": local(closed).isoformat(),
        "side": "多" if side == 1 else "空", "net": net, "gross": gross, "fees": fees,
        "entry_class": entry_class, "reason": EXIT_NAME[reason], "exit_class": exit_class,
        "hard_stop": reason in HARD, "time_exit": reason == "er_1h_timeout", "reached": reached,
        "timing": timing, "post_target": post_target, "partial_class": partial_class, "no_partial_delta": no_partial,
        "delta1": d1, "delta4": d4, "alt1": h1["net"] if h1 else None, "alt4": h4["net"] if h4 else None,
        "original4": original4, "delayed4": delayed4,
        "pre4": pre4, "first_hour_mfe": first_hour.mfe, "mfe": position.mfe, "mae": position.mae,
        "entry": entry, "exit": fill, "qty": qty, "reduced_qty": qty - position.qty, "hard_stop_price": position.stop,
        "target_price": position.target, "hold_hours": (closed - opened) / (4 * BAR),
        "after_close_equity": float(row["equity"]), "target_time": local(position.target_time).isoformat() if reached else None,
    }


def summarize(group):
    return {
        "count": len(group), "wins": sum(x["net"] > 0 for x in group), "losses": sum(x["net"] < 0 for x in group),
        "net": sum(x["net"] for x in group), "gross": sum(x["gross"] for x in group),
        "fees": sum(x["fees"] for x in group), "target": sum(x["reached"] for x in group),
        "hard_stops": sum(x["hard_stop"] for x in group), "timeouts": sum(x["time_exit"] for x in group),
        "timing": sum(x["timing"] for x in group), "post_target": sum(x["post_target"] is True for x in group),
        "entry_classes": dict(Counter(x["entry_class"] for x in group)),
        "exit_classes": dict(Counter(x["exit_class"] for x in group)),
        "partial_classes": dict(Counter(x["partial_class"] for x in group)),
    }


def main():
    source = WORK.parent / "outputs" / "BTCUSDT_rolling_account_2019_2025.json"
    doc = json.loads(source.read_text())
    paths = [
        (WORK / "BTCUSDT_futures_2019_verified.csv", WORK / "rolling_account_2019_trades.csv"),
        (BYBIT_DIR / "bybit_2025_completed_scratch.csv", WORK / "rolling_account_2020_2025_trades.csv"),
    ]
    trades = []
    year_count = Counter()
    quarter_prices = {}
    for segment, (prices, executions) in zip(doc["segments"], paths):
        start = ms(segment["start_utc"])
        end = ms(segment["end_exclusive_utc"])
        market = read_market(prices, start - 20 * BAR, end)
        for stamp, bar in market.items():
            if stamp < start:
                continue
            date = local(stamp)
            if date.year not in (2019, 2020, 2025):
                continue
            key = (date.year, (date.month - 1) // 3 + 1)
            if key not in quarter_prices:
                quarter_prices[key] = [bar.opening, bar.close]
            quarter_prices[key][-1] = bar.close
        for row in read_csv(executions):
            year = local(ms(row["opened"])).year
            year_count[year] += 1
            trades.append(explain(row, market, segment, f"{year}-{year_count[year]:03}"))
    assert len(trades) == 212
    by_year = {}
    for year, basis in doc["years"].items():
        group = [t for t in trades if t["year"] == int(year)]
        assert len(group) == basis["entries"]
        close_enough(sum(t["net"] for t in group), basis["ending_equity_usdt"] - basis["opening_equity_usdt"])
        by_year[year] = {
            **basis, **summarize(group),
            "by_side": {side: summarize([t for t in group if t["side"] == side]) for side in ("多", "空")},
            "no_target_losses": summarize([t for t in group if not t["reached"] and t["net"] < 0]),
            "target_losses": summarize([t for t in group if t["reached"] and t["net"] < 0]),
            "by_exit_reason": {why: summarize([t for t in group if t["reason"] == why]) for why in {t["reason"] for t in group}},
        }
    quarters = []
    for (year, quarter), (start, end) in quarter_prices.items():
        group = [t for t in trades if t["year"] == year and t["quarter"] == quarter]
        quarters.append({"year": year, "quarter": quarter, "btc_return": end / start - 1,
                         "net": sum(t["net"] for t in group), "count": len(group),
                         "long": sum(t["net"] for t in group if t["side"] == "多"),
                         "short": sum(t["net"] for t in group if t["side"] == "空")})
    out = {"trades": trades, "years": by_year, "quarters": quarters, "totals": summarize(trades),
           "initial": doc["initial_equity_usdt"], "final": doc["ending_equity_usdt"],
           "sources": {"roll": str(source), "trades": [str(x[1]) for x in paths], "prices": [str(x[0]) for x in paths]}}
    (WORK / "rolling_trade_diagnosis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["totals"], ensure_ascii=False))
    for year, summary in by_year.items():
        print(year, summary["net"], summary["gross"], summary["fees"], summary["entry_classes"], summary["exit_classes"])
    for x in quarters:
        print(x)


if __name__ == "__main__":
    main()
