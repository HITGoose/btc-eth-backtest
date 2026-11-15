import csv
from dataclasses import dataclass

import numpy as np

from audit_gate_october import SEPTEMBER
from backtest_squeeze_short import HOUR, TREND_THRESHOLDS, WARMUP, hourly_regimes, sma
from combined_crypto_portfolio import BAR, WORK, ms, read_market
from fit_squeeze_ladder_bot import SCALES
from replay_gate_bot import ENTRY, PATHS


DATA_END = ms("2026-11-11T02:45:00+08:00")
SWING_SPACING = 32
SWING_VALIDITY = 32
RETEST_WAIT = 32
RETEST_CONFIRMATION = 4
DIRECTIONS = {"up": 1, "down": -1}

RULES = {
    "baseline": "The prior Gate compression-expansion entry in all regimes.",
    "range_double_trend_retest": "Range: double divergence with MA5/MA20 and MACD direction. Trend: break and retest the confirmed hourly level. Transition: wait.",
    "range_triple_trend_retest": "Range: triple divergence with MA5/MA20 and MACD direction. Trend: same break and retest. Transition: wait.",
    "range_double_trend_level_or_volume": "Range: double divergence. Trend: MA5/MA20 cross within 1% of confirmed hourly support/resistance, or a directional 8-hour breakout on at least 1.5x the past 20-bar median volume. Transition: wait.",
    "range_double_trend_retest_transition_original": "Same range and trend rules as range_double_trend_retest. Transition: use the original compression-expansion entry.",
    "range_original_trend_level_or_volume": "Range: original compression-expansion entry, with same-direction divergence recorded as confluence. Trend: level or volume entry. Transition: wait.",
}


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    energy: float
    leg_start: int


@dataclass(frozen=True)
class Divergence:
    swings: tuple[Swing, ...]
    confirmed: int


@dataclass
class Retest:
    level: float
    breakout_index: int
    touch_index: int | None = None


def pivot(values, index):
    return all(values[index] > values[j] for j in (index - 2, index - 1, index + 1, index + 2))


def diverging_pair(older, newer):
    return (newer.leg_start > older.index and newer.index - older.index <= SWING_SPACING
            and newer.price > older.price and newer.energy <= older.energy)


def top_divergences(highs, lows, histogram):
    """Port the previously tested swing-leg comparison; mirror it for bottoms."""
    result = [(None, None)] * 4
    recent_swings = []
    active = [None, None]
    latest_low = None
    negative_lows = -lows
    for i in range(4, len(highs)):
        j = i - 2
        for k, pattern in enumerate(active):
            if pattern and (i - pattern.confirmed > SWING_VALIDITY or highs[i] > pattern.swings[-1].price):
                active[k] = None
        if latest_low is not None and pivot(highs, j):
            swing = Swing(j, float(highs[j]), float(max(histogram[latest_low:j + 1])), latest_low)
            if recent_swings and diverging_pair(recent_swings[-1], swing):
                active[0] = Divergence((recent_swings[-1], swing), i)
                if len(recent_swings) == 2 and diverging_pair(*recent_swings):
                    active[1] = Divergence((*recent_swings, swing), i)
            recent_swings = [*recent_swings[-1:], swing]
        if pivot(negative_lows, j):
            latest_low = j
        result.append(tuple(active))
    return result


def hourly_context(first, closes, highs, lows, *, regime_thresholds=TREND_THRESHOLDS):
    assert first % HOUR == 0
    size = len(closes) // 4 * 4
    first_close = first + HOUR
    h = highs[:size].reshape(-1, 4).max(axis=1)
    l = -lows[:size].reshape(-1, 4).min(axis=1)
    regimes = hourly_regimes(closes[3:size:4], first_close, thresholds=regime_thresholds)
    levels = {}
    last_top = last_bottom = None
    for i in range(len(h)):
        j = i - 2
        if i >= 4:
            if pivot(h, j):
                last_top = float(h[j])
            if pivot(l, j):
                last_bottom = -float(l[j])
        levels[first_close + i * HOUR] = {1: last_top, -1: last_bottom}
    return regimes, levels


def advance_retest(setup, level, side, i, close, previous, bar_edge):
    if setup:
        crossed_back = (close - setup.level) * side <= 0
        expired = (i - setup.breakout_index > RETEST_WAIT if setup.touch_index is None
                   else i - setup.touch_index > RETEST_CONFIRMATION)
        if crossed_back or expired:
            setup = None
    if setup:
        if setup.touch_index is None and (bar_edge - setup.level) * side <= 0:
            setup.touch_index = i
        return setup
    if level is not None and (previous - level) * side <= 0 < (close - level) * side:
        return Retest(level, i)
    return None


def strict_crosses(values):
    direction = np.zeros(len(values), dtype=np.int8)
    previous, current = values[:-1], values[1:]
    direction[1:] = np.select(((previous < 0) & (current > 0), (previous > 0) & (current < 0)), (1, -1))
    return direction


def ma7_ma10_spread(closes, price_scale):
    # Sum integer price ticks so equal moving averages stay equal.
    ticks = np.rint(closes * price_scale).astype(np.int64)
    total = np.r_[0, ticks.cumsum()]
    sum7 = total[10:] - total[3:-7]
    sum10 = total[10:] - total[:-10]
    spread = np.full(len(closes), np.nan)
    spread[9:] = (10 * sum7 - 7 * sum10) / (70 * price_scale)
    return spread


def market_schedules(asset, leg, *, price_file=None, include_gate_confirmation=False, regime_thresholds=TREND_THRESHOLDS,
                     use_entry_crosses=False, entry_confirmation=None):
    file = WORK / PATHS[asset] if price_file is None else price_file
    bars = read_market(file, leg.start - WARMUP, leg.end)
    first = next(iter(bars))
    assert first == leg.first
    with file.open(encoding="utf-8", newline="") as stream:
        volume = {int(row["timestamp"]): float(row["volume"]) for row in csv.DictReader(stream)}
    opens, highs, lows, closes = np.array([(b.o, b.h, b.l, b.c) for b in bars.values()]).T
    volumes = np.array([volume[t] for t in bars])
    histogram = leg.histogram
    ma_diff = ma7_ma10_spread(closes, SCALES[asset]) if use_entry_crosses else sma(closes, 5) - sma(closes, 20)
    ma_crosses = strict_crosses(ma_diff) if use_entry_crosses else None
    macd_crosses = strict_crosses(histogram) if use_entry_crosses else None
    patterns = {-1: top_divergences(highs, lows, histogram), 1: top_divergences(-lows, -highs, -histogram)}
    regimes, levels = hourly_context(first, closes, highs, lows, regime_thresholds=regime_thresholds)
    baseline = leg.signals(ENTRY, macd_crosses=macd_crosses)
    split = {name: {} for name in RULES if name != "baseline"}
    used = set()
    retests = {-1: None, 1: None}
    context = {}

    for i in range(32, len(closes) - 1):
        bar_open = first + i * BAR
        time = bar_open + BAR
        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))
        market_side = DIRECTIONS.get(state)
        known_levels = levels.get(bar_open // HOUR * HOUR, {})
        for side, edge in ((1, lows[i]), (-1, highs[i])):
            retests[side] = advance_retest(retests[side], known_levels.get(side), side, i, closes[i], closes[i - 1], edge)

        if time < leg.start:
            continue
        context[time] = {"regime": state, "active_top_legs": 3 if patterns[-1][i][1] else 2 if patterns[-1][i][0] else 0,
                         "active_bottom_legs": 3 if patterns[1][i][1] else 2 if patterns[1][i][0] else 0}
        if use_entry_crosses:
            confirmation = int(ma_crosses[i]) if ma_crosses[i] == macd_crosses[i] else 0
        elif entry_confirmation is not None:
            confirmation = entry_confirmation.get(time)
        else:
            confirmation = next((side for side in (1, -1) if ma_diff[i] * side > 0 and histogram[i] * side > 0), None)
        gate = None
        if include_gate_confirmation and (original_side := baseline.get(time)):
            level = known_levels.get(original_side)
            double, triple = patterns[original_side][i]
            gate = {"aligned_lines": int((leg.up if original_side == 1 else leg.down)[i]),
                    "minimum_bandwidth_pct": float(leg.squeeze[ENTRY.lookback][i]),
                    "entry_bandwidth_pct": float(leg.width[i]),
                    "short_term_alignment": confirmation == original_side,
                    "confirmed_divergence_legs": (3 if triple else 2 if double else 0) if confirmation == original_side else 0,
                    "distance_to_confirmed_hourly_level_pct": float(100 * abs(closes[i] - level) / closes[i]) if level is not None else None,
                    "directional_volume_breakout": False, "confirmed_retest": False}
            context[time]["gate_confirmation"] = gate
        if state == "range" and confirmation:
            for pattern_index, pattern in enumerate(patterns[confirmation][i]):
                if not pattern:
                    continue
                signature = (confirmation, pattern_index, pattern.confirmed)
                if signature in used:
                    continue
                used.add(signature)
                if pattern_index == 0:
                    split["range_double_trend_retest"][time] = confirmation
                    split["range_double_trend_level_or_volume"][time] = confirmation
                else:
                    split["range_triple_trend_retest"][time] = confirmation

        if market_side:
            setup = retests[market_side]
            confirmed_retest = bool(setup and setup.touch_index is not None and confirmation == market_side)
            if confirmed_retest:
                split["range_double_trend_retest"][time] = market_side
                split["range_triple_trend_retest"][time] = market_side
                retests[market_side] = None

            level = known_levels.get(market_side)
            crossed_ma = (ma_crosses[i] == market_side if use_entry_crosses
                          else ma_diff[i - 1] * market_side <= 0 < ma_diff[i] * market_side)
            near_level = level is not None and abs(closes[i] - level) / closes[i] <= 0.01
            edge = max(highs[i - 32:i]) if market_side == 1 else min(lows[i - 32:i])
            median = np.median(volumes[i - 20:i])
            volume_breakout = ((closes[i] - edge) * market_side > 0 and (closes[i] - opens[i]) * market_side > 0
                               and (closes[i] - closes[i - 1]) * market_side > 0 and median > 0 and volumes[i] >= 1.5 * median)
            if gate is not None and market_side == original_side:
                gate["directional_volume_breakout"] = bool(volume_breakout)
                gate["confirmed_retest"] = confirmed_retest
            if (crossed_ma and near_level) or volume_breakout:
                split["range_double_trend_level_or_volume"][time] = market_side

    split["range_double_trend_retest_transition_original"] = {
        **split["range_double_trend_retest"],
        **{t: side for t, side in baseline.items() if context[t]["regime"] == "transition"},
    }
    split["range_original_trend_level_or_volume"] = {
        **{t: side for t, side in baseline.items() if context[t]["regime"] == "range"},
        **{t: side for t, side in split["range_double_trend_level_or_volume"].items() if context[t]["regime"] in DIRECTIONS},
    }
    return {"baseline": baseline, **split}, context
