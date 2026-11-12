from collections import Counter

import numpy as np

from gate_annual_market import WINDOWS, load_prepared, read_december_trades
from gate_public_data import CACHE
from replay_gate_bot import GateMinutes, POLL_SECONDS, polled_events
from replay_gate_october_seconds import POLL_PHASE_SECONDS, replay_asset


PATH_ORDERS = ("adverse_first", "favorable_first")


def ohlc_events(second, ohlc, step, side, order):
    opening, high, low, close = ohlc
    high_first = (side == -1) == (order == "adverse_first")
    first, second_extreme = (high, low) if high_first else (low, high)
    return ((second, opening), (second + 0.3 * step, first), (second + 0.6 * step, second_extreme),
            (second + step - 0.001, close))


class AnnualTimeline:
    def __init__(self, asset, year, metadata, order, *, use_cached_prints=True):
        self.asset = asset
        self.first = metadata["start_epoch_s"]
        self.minutes, self.resolution, self.ten_time, self.ten_prices = load_prepared(asset, year)
        self.market = self
        self.order = order
        self.step_in_events = 0
        self.prints = GateMinutes(asset, self, download_missing=False) if use_cached_prints and year == 2026 else None
        self.december_trades = read_december_trades(asset) if year == 2019 else None
        self.used = Counter()
        self.cached_print_errors = {}
        self.close_discrepancies = {} if self.prints is None else self.prints.close_discrepancies

    def __getitem__(self, t):
        offset = (t - self.first) // 60
        if offset == -1:
            opening = self.minutes[0, 0]
            return opening, opening, opening, opening, 0
        return self.minutes[offset]

    def modeled_stop_at_level(self, stamp):
        return self.step_in_events != 0 and round(stamp * 1000) % (self.step_in_events * 1000) != 0

    def events(self, minute, phase, *, side=None, poll_seconds=POLL_SECONDS):
        offset = minute - self.first
        step = int(self.resolution[offset // 60])
        self.step_in_events = 0
        if self.prints is not None:
            cached = CACHE / f"{self.asset}_USDT_decimal_trades_{minute}_{minute + 60}.json"
            if cached.exists():
                try:
                    self.prints.tape(minute)
                except (OSError, ValueError) as error:
                    self.cached_print_errors[str(minute)] = str(error)
                else:
                    self.used["verified_trade_minutes"] += 1
                    yield from self.prints.events(minute, phase, side=side, poll_seconds=poll_seconds)
                    return
        previous = float(self[minute - 60][3])
        if not step:
            self.used["no_price_observed"] += 1
            yield from polled_events(minute, phase, (), previous, poll_seconds=poll_seconds)
            return

        if self.december_trades is not None:
            left, right = np.searchsorted(self.december_trades[:, 0], (minute, minute + 60))
            assert left < right
            self.used["archived_trade_minutes"] += 1
            prices = ((float(stamp), float(price)) for stamp, price, _ in self.december_trades[left:right])
            yield from polled_events(minute, phase, prices, previous, poll_seconds=poll_seconds)
            return

        self.step_in_events = step
        if step == 10:
            self.used["simulated_10s_minutes"] += 1
            left, right = np.searchsorted(self.ten_time, (offset, offset + 60))
            prices = [event for start, ohlc in zip(self.ten_time[left:right], self.ten_prices[left:right], strict=True)
                      for event in ohlc_events(self.first + int(start), ohlc, 10, side, self.order)]
        else:
            self.used["simulated_1m_minutes"] += 1
            prices = ohlc_events(minute, self[minute][:4], 60, side, self.order)
        yield from polled_events(minute, phase, ((stamp, float(price)) for stamp, price in prices), previous,
                                 poll_seconds=poll_seconds)


def replay_annual_asset(asset, year, leg, schedule, metadata, order, *, window=None, use_cached_prints=True,
                        poll_seconds=POLL_SECONDS, poll_phase=POLL_PHASE_SECONDS, size_multipliers=None, leverage=3.0):
    start, end = WINDOWS[year] if window is None else window
    market = AnnualTimeline(asset, year, metadata, order, use_cached_prints=use_cached_prints)
    result = replay_asset(asset, leg=leg, signals=schedule, market=market, print_progress=False, start=start, end=end,
                          poll_seconds=poll_seconds, poll_phase=poll_phase, size_multipliers=size_multipliers, leverage=leverage)
    result.pop("verified_minutes_with_trade_prints")
    result["execution_event_minutes"] = dict(market.used)
    result["cached_print_errors"] = market.cached_print_errors
    return result
