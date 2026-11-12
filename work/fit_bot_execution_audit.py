import json
from concurrent.futures import ThreadPoolExecutor
from math import floor, fsum

import numpy as np

from backtest_squeeze_short import HOUR, hourly_regimes
from combined_crypto_portfolio import BAR, WORK, Bar
from fetch_eth_2021_2024 import fetch_window
from fit_squeeze_ladder_bot import (END, REFERENCE, START, TRAIN, VALIDATION, Settings, Sizing, build, ladder_rung,
                                    simulate, stop_price)
from extended_crypto_portfolio import ETH_START, SWITCH, local
from original_ladder_tick_data import MINUTE, refine_ticks
from run_original_ladder_compare import CACHE as SHARED_CACHE, aggregate


OUTPUTS = WORK.parent / "outputs"
CACHE = WORK / "bot_fit_verified_execution_cache.json"
SWITCHES = {"BTC": SWITCH, "ETH": ETH_START}
REFERENCE_NET = {
    2020: (1195.69, 466.42), 2021: (695.33, 532.10), 2022: (9177.94, -360.26),
    2023: (21065.49, 6330.18), 2024: (28278.19, 15939.15), 2025: (-16025.12, 108893.73),
}
LIVE_SIZING = (
    ("BTC", 75820.30, 50.56, 20), ("BTC", 74217.10, 53.51, 21),
    ("ETH", 2229.45, 50.55, 6), ("ETH", 2131.13, 56.92, 8), ("ETH", 2112.07, 58.49, 8),
)


def live_sizing():
    rows = []
    for asset, entry, balance, contracts in LIVE_SIZING:
        unit = 0.0001 if asset == "BTC" else 0.01
        per_contract = entry * unit
        row = {"asset": asset, "entry_price": entry, "inferred_unit": unit, "sleeve_balance_usdt": balance,
               "observed_contracts": contracts, "contracts_at_3x": floor(3 * balance / per_contract),
               "contracts_at_5x": floor(5 * balance / per_contract),
               "implied_opening_leverage": contracts * per_contract / balance,
               "max_leverage_before_next_contract": (contracts + 1) * per_contract / balance}
        assert row["contracts_at_3x"] == contracts
        rows.append(row)
    return rows


class ExecutionReplay:
    def __init__(self, cache, favorable_first=False):
        self.cache = cache
        self.favorable_first = favorable_first
        self.uncertain_bars = set()
        self.uncertain_minutes = set()

    @staticmethod
    def trade(book):
        return book.position.order if book.position else book.order

    @staticmethod
    def ambiguous(book, candle, order):
        side, entry = order.side, order.price
        best, worst = (candle.h, candle.l) if side == 1 else (candle.l, candle.h)
        if book.order and (worst - entry) * side > 0:
            return False
        favorable = (best / entry - 1) * side * 100
        rung = ladder_rung(favorable, book.exit_policy)
        if book.order:
            return rung > 0
        if rung <= book.position.rung:
            return False
        lock = stop_price(book.asset, entry, side, rung)
        return (worst - lock) * side <= 0

    def prices(self, book, candle, side):
        first_high = (side == -1) != self.favorable_first
        return (candle.h, candle.l, candle.c) if first_high else (candle.l, candle.h, candle.c)

    def __call__(self, asset, book, candle, t):
        book.visit(candle.o, t, True)
        if not (order := self.trade(book)):
            return
        key = str(t)
        whole = self.cache.get("fullBars", {}).get(asset, {}).get(key)
        minutes = self.cache[asset].get(key)
        if whole:
            for price in whole:
                book.visit(price, t, False)
                if not self.trade(book):
                    break
            return
        if minutes:
            ticks = self.cache.get("ticks", {}).get(asset, {})
            for i, row in enumerate(minutes):
                minute_time = t + i * MINUTE
                b = Bar(*row)
                book.visit(b.o, t, False)
                if not (order := self.trade(book)):
                    break
                tape = ticks.get(str(minute_time))
                if tape is None:
                    if self.ambiguous(book, b, order):
                        self.uncertain_minutes.add((asset, minute_time, MINUTE))
                    tape = self.prices(book, b, order.side)
                for price in tape:
                    book.visit(price, t, False)
                    if not self.trade(book):
                        break
        else:
            if self.ambiguous(book, candle, order):
                self.uncertain_bars.add((asset, t, BAR))
            for price in self.prices(book, candle, order.side):
                book.visit(price, t, False)


def fit_legs():
    return {
        "BTC": [build("BTCUSDT_Binance_2019_2020_continuous.csv", START, SWITCH),
                build("BTCUSDT_Bybit_2020_2026_continuous.csv", SWITCH, END)],
        "ETH": [build("ETHUSDT_Binance_2019_2021_early.csv", START, ETH_START),
                build("ETHUSDT_Bybit_2021_2026_continuous.csv", ETH_START, END)],
    }


def trend_regimes(legs):
    regimes = {}
    for asset, segments in legs.items():
        markets = {t: b for leg in segments for t, b in leg.bars.items()}
        hours = [(t + BAR, b.c) for t, b in markets.items() if (t + BAR) % HOUR == 0]
        regimes[asset] = hourly_regimes(np.array([c for _, c in hours]), hours[0][0])
    return regimes


def trend_gate(legs):
    regimes = trend_regimes(legs)

    def permitted(asset, time, side):
        regime, *_ = regimes[asset].get(time // HOUR * HOUR, ("transition",))
        return (regime, side) not in (("up", -1), ("down", 1))

    return permitted


def archive_venue(asset, time):
    return "binance" if time < SWITCHES[asset] else "bybit"


def fetch_minutes(task, market):
    asset, time, _ = task
    rows = fetch_window(archive_venue(asset, time), time, time + BAR, asset + "USDT", minutes=1)
    minutes = [r[1:5] for r in rows]
    b = market[asset][time]
    if aggregate(minutes) != (b.o, b.h, b.l, b.c):
        raise ValueError(f"1m OHLC mismatch {aggregate(minutes)} != {(b.o, b.h, b.l, b.c)}")
    return minutes


def refine(legs, cases, cache):
    market = {a: {t: b for leg in segments for t, b in leg.bars.items()} for a, segments in legs.items()}
    failed_minute, failed_tape = {}, {}
    before = {a: len(cache[a]) for a in market}
    for step in range(1, 8):
        replay = ExecutionReplay(cache)
        results = {name: simulate(legs, settings, END, rebalance=rebalance, sizing=sizing, replay=replay, signal_gate=gate)
                   for name, (settings, sizing, rebalance, gate) in cases.items()}
        print(f"Pass {step}: {len(replay.uncertain_bars)} bars and {len(replay.uncertain_minutes)} minutes to resolve", flush=True)
        pending = sorted(replay.uncertain_bars - failed_minute.keys())
        tapes = (replay.uncertain_bars & failed_minute.keys()) | replay.uncertain_minutes
        tapes -= failed_tape.keys()
        if not (pending or tapes) or step == 7:
            break
        if pending:
            with ThreadPoolExecutor(max_workers=8) as pool:
                tasks = {task: pool.submit(fetch_minutes, task, market) for task in pending}
                for task, future in tasks.items():
                    asset, time, _ = task
                    try:
                        cache[asset][str(time)] = future.result()
                    except Exception as error:
                        failed_minute[task] = str(error)
            print("Verified minute bars", len(pending) - sum(task in failed_minute for task in pending), flush=True)
        for asset in market:
            windows = sorted(task for task in tapes if task[0] == asset)
            if windows:
                count, failed = refine_ticks(cache, windows, lambda a, t: market[a][t],
                                             lambda t: archive_venue(asset, t))
                failed_tape.update(failed)
                print(asset, "verified trade windows", count, "of", len(windows), flush=True)
        CACHE.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    other = ExecutionReplay(cache, favorable_first=True)
    alternative = {name: simulate(legs, settings, END, rebalance=rebalance, sizing=sizing, replay=other, signal_gate=gate)
                   for name, (settings, sizing, rebalance, gate) in cases.items()}
    return results, alternative, {
        "unresolved_15m": [(a, local(t)) for a, t, _ in sorted(replay.uncertain_bars | other.uncertain_bars)],
        "unresolved_1m": [(a, local(t)) for a, t, _ in sorted(replay.uncertain_minutes | other.uncertain_minutes)],
        "new_verified_1m_bars": {a: len(cache[a]) - before[a] for a in market},
        "failed_1m": [(a, local(t), err) for (a, t, _), err in failed_minute.items()],
        "failed_trade_tapes": [(a, local(t), span, err) for (a, t, span), err in failed_tape.items()],
        "both_ohlc_orders_agree": {name: results[name] == alternative[name] for name in cases},
    }


def targets():
    start_equity = 1000
    rows = {}
    for y in (*TRAIN, *VALIDATION):
        btc, eth, equity, drawdown, no_rebalance = REFERENCE[y]
        b, e = REFERENCE_NET[y]
        rows[y] = {"counts": {"BTC": btc, "ETH": eth}, "ending_equity_usdt": equity,
                   "return_pct": 100 * (equity / start_equity - 1), "max_drawdown_pct": drawdown,
                   "no_rebalance_return_pct": no_rebalance, "reported_net_usdt": {"BTC": b, "ETH": e},
                   "equity_change_less_reported_pnl_usdt": round(equity - start_equity - b - e, 2)}
        start_equity = equity
    return rows


def compare(result, target):
    return {label: {
        "absolute_trade_count_error": sum(abs(result["years"][y]["counts"][a] - target[y]["counts"][a])
                                          for a in ("BTC", "ETH") for y in years),
        "mean_absolute_annual_return_error_pp": fsum(abs(result["years"][y]["return_pct"] - target[y]["return_pct"])
                                                    for y in years) / len(years),
        "mean_absolute_annual_drawdown_error_pp": fsum(abs(result["years"][y]["max_drawdown_pct"] - target[y]["max_drawdown_pct"])
                                                      for y in years) / len(years),
    } for label, years in (("2020_2023", TRAIN), ("2024_2025", VALIDATION)) if all(y in result["years"] for y in years)}


def main():
    legs = fit_legs()
    old_signal = Settings(96, 6, 0.15, "time_72h")
    screen_signal = Settings(96, 5, 0.25, "time_72h")
    live_5x = Sizing(5, 0.0001, False)
    cases = {
        "prior_fit_corrected_execution_5x": (old_signal, Sizing(), True, None),
        "live_lots_5x": (old_signal, live_5x, True, None),
        "live_lots_3x": (old_signal, Sizing(3, 0.0001, False), True, None),
        "live_lots_5x_no_rebalance": (old_signal, live_5x, False, None),
        "live_lots_5x_trend_gate": (old_signal, live_5x, True, trend_gate(legs)),
        "screenshot_parameters_5x": (screen_signal, live_5x, True, None),
    }
    cache_file = CACHE if CACHE.exists() else SHARED_CACHE
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    results, other, audit = refine(legs, cases, cache)
    target = targets()
    old = json.loads((OUTPUTS / "BTC_ETH_bot_ladder_reconstruction_2020_2026.json").read_text(encoding="utf-8"))
    prior = old["fits"][old["selected"]]["backtest"]
    quote = json.loads((WORK / "fit_bot_early_rung_quote_audit.json").read_text(encoding="utf-8"))
    out = {"window_local": [local(START), local(END)], "target_from_user_screenshot": target,
           "sizing_inference_pre_restart": live_sizing(), "early_eth_quote_audit": quote,
           "sizing_and_fills": "1000 USDT split equally at start. Monthly 50/50 marked equity is an assumption. "
                               "Previous +0.20% short and -0.20% long limit model, 60-minute order expiry, "
                               "capped ladder with hypothesized 72-hour position cap, 0.05% fee and 0.02% exit slippage. "
                               "Funding and maintenance margin are omitted.",
           "previous_fit": {"backtest": prior, "errors": compare(prior, target)},
           "tests": {name: {"settings": cases[name][0].key, "sizing": vars(cases[name][1]),
                            "monthly_rebalance": cases[name][2], "trend_direction_gate": cases[name][3] is not None,
                            "backtest": r, "errors": compare(r, target),
                            "favorable_first": other[name] if r != other[name] else None} for name, r in results.items()},
           "execution_audit": audit}
    (OUTPUTS / "BTC_ETH_bot_report_fit_audit_2020_2025.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("AUDIT", json.dumps(audit), flush=True)
    for name, result in results.items():
        print(name, round(result["ending_equity_usdt"], 2), round(result["max_drawdown_pct"], 2), compare(result, target), flush=True)
        for y, row in result["years"].items():
            print(y, row["counts"], round(row["return_pct"], 2), round(row["max_drawdown_pct"], 2), flush=True)


if __name__ == "__main__":
    main()
