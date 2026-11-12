import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from audit_gate_october import SEPTEMBER
from backtest_squeeze_short import HOUR, WARMUP
from combined_crypto_portfolio import BAR, WORK, close_enough, ms, read_market
from compare_gate_strategies_by_year import OUTPUTS, add_readable_times, gate_run, summarize_gate_books
from extended_crypto_portfolio import local
from fit_gate_entry_overlay import BASELINE, LIVE_SEED, LIVE_WINDOW, OCTOBER_WINDOW, SEED, RegimeOverlay, matches_live, price_books, run_exact, stacked_signals
from fit_squeeze_ladder_bot import SCALES, build
from gate_annual_market import MARKET_CACHE, PRICE_FILES, WINDOWS
from gate_october_regime_entries import DATA_END, ma7_ma10_spread, market_schedules, strict_crosses
from gate_public_data import save_json
from replay_gate_annual import PATH_ORDERS
from replay_gate_bot import PATHS
from replay_gate_regime_october import replay_with_refinement
from replay_gate_selected_3x import PRIOR_ALIGNMENT_RESULT as PRIOR_REPORT


RESULT = OUTPUTS / "BTC_ETH_Gate_MA7_MA10_MACD_cross_timing_3x.json"
CONTROL = "prior_alignment"
GAPS = {"same_close_crosses": 0, "crosses_within_four_bars": 4}


def paired_crosses(closed_at, ma, histogram, ma_cross, macd_cross, maximum_gap):
    recent_ma = recent_macd = -1
    signals = {}
    for i in np.flatnonzero((ma_cross != 0) | (macd_cross != 0)):
        if ma_cross[i]:
            recent_ma = i
        if macd_cross[i]:
            recent_macd = i
        first_cross = min(recent_ma, recent_macd)
        if first_cross < 0 or i - first_cross > maximum_gap:
            continue
        side = int(ma_cross[recent_ma])
        if side == macd_cross[recent_macd] and np.all(ma[recent_ma:i + 1] * side > 0) and np.all(histogram[recent_macd:i + 1] * side > 0):
            signals[int(closed_at[i])] = side
    return signals


def cross_series(asset, path, leg):
    bars = read_market(WORK / path, leg.start - WARMUP, leg.end)
    close_times = np.fromiter((t + BAR for t in bars), dtype=np.int64)
    closes = np.fromiter((b.c for b in bars.values()), dtype=np.float64)
    ma = ma7_ma10_spread(closes, SCALES[asset])
    histogram = leg.histogram
    return close_times, ma, histogram, strict_crosses(ma), strict_crosses(histogram)


def prepare(files, start, end, er, policy):
    all_cases = {name: {} for name in (CONTROL, *GAPS)}
    series = {}
    for asset, path in files.items():
        leg = build(path, start, end)
        series[asset] = cross_series(asset, path, leg)
        confirmations = {name: paired_crosses(*series[asset], gap) for name, gap in GAPS.items()}
        for name, confirmation in ((CONTROL, None), *confirmations.items()):
            schedules, context = market_schedules(asset, leg, price_file=WORK / path, include_gate_confirmation=True,
                                                 regime_thresholds=er, entry_confirmation=confirmation)
            signals = stacked_signals(schedules[BASELINE], context, policy)
            if confirmation is not None:
                signals = {t: side for t, side in signals.items() if confirmation.get(t) == side}
            assert signals.items() <= schedules[BASELINE].items()
            all_cases[name][asset] = leg, {name: signals}, context
    return all_cases, series


def crossed_at_or_before(data, stamp):
    times, ma, hist, ma_cross, macd_cross = data
    i = int(np.searchsorted(times, stamp))
    assert times[i] == stamp
    row = {"close_local": local(stamp), "ma7_minus_ma10": [float(ma[i - 1]), float(ma[i])],
           "dif_minus_dea": [float(hist[i - 1]), float(hist[i])], "ma_cross_side": int(ma_cross[i]), "macd_cross_side": int(macd_cross[i])}
    for key, values in (("last_ma_bearish_cross_local", ma_cross), ("last_macd_bearish_cross_local", macd_cross)):
        prior = np.flatnonzero(values[:i + 1] == -1)
        row[key] = local(int(times[prior[-1]])) if len(prior) else None
    return row


def main():
    reference = json.loads(PRIOR_REPORT.read_text(encoding="utf-8"))
    er = tuple(tuple(x) for x in reference["er_windows_and_thresholds"])
    policy = RegimeOverlay(**reference["policy"])
    market = json.loads((MARKET_CACHE / "prepared_market.json").read_text(encoding="utf-8"))
    start, end = WINDOWS[2026]
    annual_prepared, _ = prepare(PRICE_FILES, start - 30 * 24 * HOUR, end, er, policy)
    recent, series = prepare(PATHS, SEPTEMBER, DATA_END, er, policy)
    doc = {"er_windows_and_thresholds": er, "nominal_leverage": 3.0, "policy": reference["policy"],
           "crosses_gap_bars": GAPS, "annual_window_local": [local(start), local(end)], "cases": {}}

    with ThreadPoolExecutor(max_workers=2) as pool:
        for name, prepared in annual_prepared.items():
            annual = {path: gate_run(2026, name, path, market, prepared, pool, use_cached_prints=False) for path in PATH_ORDERS}
            if name == CONTROL:
                for path, stats in annual.items():
                    previous = reference["annual"]["2026"]["execution"][path]
                    close_enough(stats["return_pct"], previous["return_pct"])
                    assert stats["opens"] == previous["opens"]
            doc["cases"][name] = {"annual": annual}
            print("2026", name, [(round(v["return_pct"], 2), round(v["mdd_15m_pct"], 2), v["opens"], v["fills_by_side"]) for v in annual.values()], flush=True)

        books = dict(zip(PATHS, pool.map(price_books, PATHS), strict=True))
        oct_inputs = {a: (recent[CONTROL][a][0], {n: p[a][1][n] for n, p in recent.items()}, None, b[0]) for a, b in books.items()}
        october, refinement = replay_with_refinement(oct_inputs, recent)
        doc["october_tape_refinement"] = refinement
        for name, prepared in recent.items():
            oct_stats = summarize_gate_books({a: r[name] for a, r in october.items()}, {a: v[2] for a, v in prepared.items()}, *OCTOBER_WINDOW, SEED)
            assert not any(oct_stats["quote_resolution_fallbacks"].values())
            live = run_exact(prepared, {a: b[1] for a, b in books.items()}, LIVE_WINDOW, LIVE_SEED, pool, mode=name)
            assert not any(live["quote_resolution_fallbacks"].values())
            matches = matches_live(live, prepared, name)
            if name == CONTROL:
                close_enough(oct_stats["return_pct"], reference["october_exact"]["strategy"]["return_pct"])
                assert matches["matching_entries_price_and_second"] == 4
            doc["cases"][name].update(october=oct_stats, november={"strategy": live, "matches": matches})
            print("OCT/NOV", name, oct_stats["opens"], round(oct_stats["return_pct"], 2), live["opens"],
                  matches["matching_entries_price_and_second"], flush=True)

    doc["recorded_signal_cross_evidence"] = [
        {"asset": f["asset"], "entry": f["entry"], **crossed_at_or_before(series[f["asset"]], ms(f["signal_time"]))}
        for row in reference["november_exact"]["entry_comparison"]["comparison"] for f in (row["recorded"],)
    ]
    add_readable_times(doc)
    save_json(RESULT, doc)


if __name__ == "__main__":
    main()
