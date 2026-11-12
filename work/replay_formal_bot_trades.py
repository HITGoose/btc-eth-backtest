import json
from dataclasses import dataclass
from math import ceil, floor

import numpy as np

from backtest_squeeze_short import HOUR, WARMUP, ema, hourly_regimes, sma
from combined_crypto_portfolio import BAR, WORK, ms, read_market
from extended_crypto_portfolio import local
from fit_squeeze_ladder_bot import (INITIAL_STOP_DISTANCE, LADDER_CAP, LIMIT_OFFSET, ORDER_LIFETIME, SCALES, build,
                                    ladder_rung, limit_price, stop_price, tick_time)


MINUTE = 60_000
QUOTES = WORK / "formal_bot_quotes_2026_11.json"


@dataclass(frozen=True)
class Fill:
    asset: str
    signal_time: str
    signal_inferred: bool
    opened: str
    closed: str
    entry: float
    exit: float
    quantity: float
    prior_sleeve_balance: float
    net_usdt: float
    rung: int | None
    archive_tail_utc_day: str | None = None

    @property
    def key(self):
        return f"{self.asset}_{self.entry}"


# Asia/Shanghai timestamps and quantities transcribed from the user's screenshots.
FILLS = (
    Fill("BTC", "2026-11-09T01:30:00+08:00", True, "2026-11-09T02:06:49+08:00", "2026-11-09T05:56:28+08:00",
         75820.30, 74293.40, 0.002, 50.56, 2.95, 2),
    Fill("ETH", "2026-11-09T01:30:00+08:00", False, "2026-11-09T01:43:07+08:00", "2026-11-09T05:56:02+08:00",
         2229.45, 2121.89, 0.06, 50.55, 6.36, 5),
    Fill("ETH", "2026-11-09T06:00:00+08:00", False, "2026-11-09T06:00:21+08:00", "2026-11-09T16:24:42+08:00",
         2131.13, 2110.00, 0.08, 56.92, 1.56, 1),
    Fill("ETH", "2026-11-09T16:30:00+08:00", False, "2026-11-09T16:43:18+08:00", "2026-11-10T21:36:18+08:00",
         2112.07, 2069.95, 0.08, 58.49, 3.27, 2, "2026-11-10"),
    Fill("BTC", "2026-11-09T06:00:00+08:00", False, "2026-11-09T06:00:24+08:00", "2026-11-11T02:33:07+08:00",
         74217.10, 73479.00, 0.0021, 53.51, 1.51, None, "2026-11-10"),
)


def signal_checks(settings, *, paths=None):
    start, end = ms("2026-11-08T00:00:00+08:00"), ms("2026-11-10T21:15:00+08:00")
    result = {}
    for asset in SCALES:
        path = f"{asset}USDT_Bybit_bot_signal_review.csv" if paths is None else paths[asset]
        leg = build(path, start, end)
        raw = read_market(WORK / path, start - WARMUP, end)
        signals = leg.signals(settings)
        closes = np.array([b.c for b in raw.values()])
        band_low = np.stack([ma(closes, n) for ma in (sma, ema) for n in (20, 60, 120)]).min(axis=0)
        dif = ema(closes, 12) - ema(closes, 26)
        histogram = dif - ema(dif, 9)
        hours = [(t + BAR, b.c) for t, b in raw.items() if (t + BAR) % HOUR == 0]
        regimes = hourly_regimes(np.array([c for _, c in hours]), hours[0][0])
        for fill in FILLS:
            if fill.asset != asset:
                continue
            t = ms(fill.signal_time)
            i = (t - leg.first) // BAR - 1
            recent = leg.width[i - settings.lookback + 1:i + 1]
            minimum = int(np.argmin(recent))
            regime, er_24h, er_120h = regimes[t // HOUR * HOUR]
            result[fill.key] = {
                "eligible_short": signals.get(t) == -1,
                "was_already_eligible_previous_bar": signals.get(t - BAR) == -1,
                "six_sma_ema_lines_declining": int(leg.down[i]),
                "last_closed_15m_price": float(closes[i]), "band_low": float(band_low[i]),
                "macd_dif_less_dea": float(histogram[i]), "previous_macd_dif_less_dea": float(histogram[i - 1]),
                "recent_minimum_bandwidth_pct": float(recent[minimum]),
                "recent_minimum_bandwidth_close_local": local(t - (len(recent) - 1 - minimum) * BAR),
                "signal_bandwidth_pct": float(leg.width[i]), "previous_bandwidth_pct": float(leg.width[i - 1]),
                "regime": regime, "signed_er_24h": er_24h, "signed_er_120h": er_120h,
            }
    return result


def trade_tapes(asset):
    tapes = []
    for day in ("2026-11-08", "2026-11-09"):
        with np.load(WORK / f"bot_fit_{asset}_{day}.npz") as data:
            tapes.append((data["time"], data["price"]))
    return tuple(np.concatenate(parts) for parts in zip(*tapes))


def first_touch(tape, minute_candles, submitted, limit):
    for minute in range(submitted, submitted + ORDER_LIFETIME, MINUTE):
        if minute_candles[minute][1] < limit:
            continue
        ts, prices = tape
        left, right = np.searchsorted(ts, [minute / 1000, (minute + MINUTE) / 1000])
        matches = np.flatnonzero(prices[left:right] >= limit)
        if len(matches):
            return float(ts[left + matches[0]])
        raise ValueError(f"Missing archived limit touch: {local(minute)}, limit {limit}")
    return None


def order_check(fill, tape, trade_quotes):
    t = ms(fill.signal_time)
    reference = trade_quotes[t][0]
    estimated = limit_price(fill.asset, reference, -1)
    touch = first_touch(tape, trade_quotes, t, fill.entry)
    estimated_touch = first_touch(tape, trade_quotes, t, estimated)
    archive_times, archive_prices = tape
    if t / 1000 < archive_times[0]:
        csv_path = WORK / f"bot_ticks_{fill.asset}USDT_2026-11-08.csv"
        archive_times, archive_prices = np.loadtxt(csv_path, skiprows=1, delimiter=",", usecols=(0, 1)).T
    left, right = np.searchsorted(archive_times, [t / 1000, t / 1000 + 15])
    assert left < right, (fill.key, t)
    quotes = archive_prices[left:right]
    candidate_limits = np.array([limit_price(fill.asset, p, -1) for p in quotes])
    nearest = int(np.argmin(abs(candidate_limits - fill.entry)))
    unit = 0.0001 if fill.asset == "BTC" else 0.01
    return {
        "limit_offset_from_bar_open_bp": 10_000 * (fill.entry / reference - 1),
        "limit_using_next_bar_open": estimated, "bar_open": reference,
        "candidate_reference_price": float(quotes[nearest]),
        "candidate_reference_local": tick_time(archive_times[left + nearest]),
        "limit_from_nearest_candidate_in_first_15_seconds": float(candidate_limits[nearest]),
        "observed_limit_first_touch_local": None if touch is None else tick_time(touch),
        "observed_limit_touch_vs_fill_seconds": None if touch is None else round(touch - ms(fill.opened) / 1000, 3),
        "proxy_limit_first_touch_local": None if estimated_touch is None else tick_time(estimated_touch),
        "proxy_limit_touch_vs_fill_seconds": None if estimated_touch is None else round(estimated_touch - ms(fill.opened) / 1000, 3),
        "order_to_observed_fill_seconds": (ms(fill.opened) - t) / 1000,
        "quantity_at_3x": floor(3 * fill.prior_sleeve_balance / fill.entry / unit) * unit,
        "quantity_at_5x": floor(5 * fill.prior_sleeve_balance / fill.entry / unit) * unit,
    }, estimated_touch


def tick_exit(fill, tape, start, *, seconds=0, phase=0, cap=LADDER_CAP, entry=None):
    times, prices = tape
    stop_at = ms(fill.closed) / 1000
    start = max(start, times[0])
    if seconds:
        first = ceil((start - phase) / seconds) * seconds + phase
        stamps = np.arange(first, stop_at + 60, seconds)
        quotes = prices[np.searchsorted(times, stamps, side="right") - 1]
    else:
        left, right = np.searchsorted(times, [start, stop_at + 60])
        stamps, quotes = times[left:right], prices[left:right]
    entry = fill.entry if entry is None else entry
    favorable = 100 * (1 - np.minimum.accumulate(quotes) / entry)
    rungs = np.maximum(0, np.floor(favorable + 1e-10).astype(int) - 1)
    if cap is not None:
        rungs = np.minimum(cap, rungs)
    scale = SCALES[fill.asset]
    stops = np.rint(entry * (1 - np.where(rungs, rungs / 100, -INITIAL_STOP_DISTANCE)) * scale) / scale
    hits = np.flatnonzero(quotes >= stops)
    if not len(hits):
        return None
    hit = int(hits[0])
    armed = np.flatnonzero(rungs[:hit + 1] > 0)
    return {"first_armed_local": tick_time(stamps[armed[0]]) if len(armed) else None,
            "trigger_local": tick_time(stamps[hit]), "rung": int(rungs[hit]), "stop": float(stops[hit]),
            "sampled_quote": float(quotes[hit]), "seconds_vs_recorded_close": round(float(stamps[hit] - stop_at), 3)}


def candle_exit(fill, candles, *, favorable_first, policy):
    rung = 0
    stop = stop_price(fill.asset, fill.entry, -1, rung)
    first = ms(fill.opened) // MINUTE * MINUTE
    last = ms(fill.closed) // MINUTE * MINUTE
    for t in range(first, last + MINUTE, MINUTE):
        opening, high, low, closing = candles[t]
        extremes = (low, high) if favorable_first else (high, low)
        for price in (opening, *extremes, closing):
            if price >= stop:
                return {"trigger_minute_local": local(t), "rung": rung, "stop": stop}
            reached = ladder_rung(100 * (1 - price / fill.entry), policy)
            if reached > rung:
                rung = reached
                stop = stop_price(fill.asset, fill.entry, -1, rung)
    return None


def quote_extremes(fill, candles):
    first = ms(fill.opened) // MINUTE * MINUTE
    last = ms(fill.closed) // MINUTE * MINUTE
    hold = range(first, last + MINUTE, MINUTE)
    high = max(hold, key=lambda t: candles[t][1])
    low = min(hold, key=lambda t: candles[t][2])
    return {"high": candles[high][1], "high_minute_local": local(high),
            "low": candles[low][2], "low_minute_local": local(low)}


def checked_tape(fill, tape, trade_quotes):
    if fill.archive_tail_utc_day is None:
        return tape, None
    with np.load(WORK / f"bot_fit_{fill.asset}_{fill.archive_tail_utc_day}_exit_window.npz") as data:
        times, prices = data["time"], data["price"]
    first = ceil(times[0] / 60) * MINUTE
    last = ms(fill.closed) // MINUTE * MINUTE
    carried_opens = 0
    for t in range(first, last + MINUTE, MINUTE):
        l, r = np.searchsorted(times, [t / 1000, (t + MINUTE) / 1000])
        prints = prices[l:r]
        opening, high, low, closing = trade_quotes[t]
        if prints[0] != opening:
            assert l > 0 and prices[l - 1] == opening, (fill.key, local(t))
            carried_opens += 1
        assert (max(opening, float(max(prints))), min(opening, float(min(prints))), prints[-1]) == (high, low, closing)
    earlier = [trade_quotes[t] for t in range(ms(fill.opened) // MINUTE * MINUTE, first, MINUTE)]
    prior_low, prior_high = min(x[2] for x in earlier), max(x[1] for x in earlier)
    assert fill.entry * (1 - INITIAL_STOP_DISTANCE) < prior_low
    assert prior_high < stop_price(fill.asset, fill.entry, -1, 0)
    below_four_pct = np.flatnonzero(prices <= fill.entry * 0.96)
    extreme_window = None
    if len(below_four_pct):
        first_tick, last_tick = int(below_four_pct[0]), int(below_four_pct[-1])
        extreme_window = {"four_percent_threshold": fill.entry * 0.96,
                          "prints_at_or_below_threshold": int(len(below_four_pct)),
                          "first_below_local": tick_time(times[first_tick]), "last_below_local": tick_time(times[last_tick]),
                          "first_to_last_below_ms": round(float((times[last_tick] - times[first_tick]) * 1000), 2)}
    return (times, prices), {
        "verified_minutes": (last - first) // MINUTE + 1, "official_open_carrying_previous_print_minutes": carried_opens,
        "prior_max_price": prior_high, "prior_min_price": prior_low,
        "four_percent_threshold_crossing": extreme_window,
    }


def audit_live_fills(settings):
    quotes = json.loads(QUOTES.read_text(encoding="utf-8"))
    conditions = signal_checks(settings)
    tapes = {asset: trade_tapes(asset) for asset in SCALES}
    checks = []
    poll_results = {}
    validation_tape = None
    for fill in FILLS:
        sources = quotes[fill.key]
        candles = {k: {int(t): values for t, values in v["market"].items()} for k, v in sources.items()}
        tape = tapes[fill.asset]
        order, proxy_touch = order_check(fill, tape, candles["trade"])
        tape, archive_check = checked_tape(fill, tape, candles["trade"])
        opened = ms(fill.opened) / 1000
        live = tick_exit(fill, tape, opened, seconds=3)
        if fill.rung is not None:
            assert conditions[fill.key]["eligible_short"]
            assert abs(order["quantity_at_3x"] - fill.quantity) < 1e-10
            assert order["observed_limit_touch_vs_fill_seconds"] is not None
            assert live and live["rung"] == fill.rung and abs(live["seconds_vs_recorded_close"]) <= 10
            poll_results[fill.key] = {str(period): [tick_exit(fill, tape, opened, seconds=period, phase=phase)
                                                    for phase in range(period)]
                                      for period in (1, 2, 3, 4, 5, 6, 10, 15, 20, 30, 60)}
        else:
            validation_tape = fill, tape, opened
        row = {
            "fill": vars(fill), "new_trade_used_for_frozen_rule_check": fill.rung is None,
            "signal_check": conditions[fill.key], "limit_check": order,
            "initial_stop": stop_price(fill.asset, fill.entry, -1, 0),
            "recorded_rung_stop": None if fill.rung is None else stop_price(fill.asset, fill.entry, -1, fill.rung),
            "observed_hold_minutes": (ms(fill.closed) - ms(fill.opened)) / MINUTE,
            "observed_price_profit_pct": 100 * (1 - fill.exit / fill.entry),
            "raw_tick_replay": tick_exit(fill, tape, opened), "three_second_replay": live,
            "three_second_uncapped_replay": tick_exit(fill, tape, opened, seconds=3, cap=None),
            "bar_open_proxy_entry_three_second_exit": None if proxy_touch is None else tick_exit(
                fill, tape, proxy_touch, seconds=3, entry=order["limit_using_next_bar_open"]),
            "official_candle_checks": {
                k: {f"{policy}_{path}": candle_exit(fill, v, favorable_first=(path == "favorable_first"), policy=policy)
                    for policy in ("fixed", "uncapped") for path in ("adverse_first", "favorable_first")}
                for k, v in candles.items()
            },
            "observed_hold_quote_extremes_including_boundary_minutes": {k: quote_extremes(fill, v) for k, v in candles.items()},
            "sources": {k: v["sources"] for k, v in sources.items()}, "extended_archive_validation": archive_check,
        }
        checks.append(row)

    for asset in SCALES:
        fills = [fill for fill in FILLS if fill.asset == asset]
        for previous, following in zip(fills, fills[1:]):
            assert ms(previous.closed) // BAR * BAR + BAR == ms(following.signal_time)
    phases = {}
    for period in next(iter(poll_results.values())):
        phases[period] = [phase for phase in range(int(period)) if all(
            (r := poll_results[f.key][period][phase]) is not None and r["rung"] == f.rung
            and r["trigger_local"][:16] == f.closed[:16] for f in FILLS if f.key in poll_results
        )]
    validation_fill, validation_prices, validation_open = validation_tape
    validation = [
        {"period_seconds": int(period), "phase_seconds": phase,
         "result": tick_exit(validation_fill, validation_prices, validation_open, seconds=int(period), phase=phase)}
        for period, matches in phases.items() for phase in matches
    ]
    return {
        "rules": {"bar_minutes": BAR // MINUTE, "use_closed_candles": True, "moving_average_periods": [20, 60, 120],
                  "moving_average_types": ["SMA", "EMA"], "slope_bars": 3, "squeeze_lookback_bars": settings.lookback,
                  "squeeze_threshold_pct": settings.squeeze_threshold, "minimum_aligned_slopes": settings.aligned_lines,
                  "condition": "V1: close outside the entire band and DIF on the same side of DEA as the signal",
                  "resubmit_when_flat_and_conditions_still_hold": True, "require_current_bar_to_widen": False,
                  "max_entry_bandwidth_multiple": 0,
                  "limit_offset_pct_proxy": 100 * LIMIT_OFFSET, "order_expiry_minutes": ORDER_LIFETIME // MINUTE,
                  "hard_stop_pct": 100 * INITIAL_STOP_DISTANCE, "ladder_trigger_initial_profit_pct": 2,
                  "ladder_first_lock_profit_pct": 1, "ladder_step_pct": 1, "ladder_cap_candidate": LADDER_CAP},
        "fills": checks,
        "same_minute_and_rung_poll_phases_by_period_seconds": phases,
        "new_trade_replay_for_periods_compatible_with_first_four": validation,
        "archived_trade_sources": [f"https://public.bybit.com/trading/{asset}USDT/{asset}USDT{day}.csv.gz"
                                   for asset in SCALES for day in ("2026-11-08", "2026-11-09", "2026-11-10")],
        "scope": "Four full-sized short fills used to compare rules and one later BTC closure for frozen-rule validation. "
                 "The early BTC signal time is inferred. The later BTC screenshot shows fill prices but no ladder label. "
                 "Exit reproduction starts from the observed filled entry; the bar-open order proxy is evaluated separately. "
                 "Sampling starts on a wall-clock grid. A sampled quote is a trigger proxy, not the actual market execution. "
                 "The archive provides prints, not the bot's quote subscription or exchange configuration.",
    }
