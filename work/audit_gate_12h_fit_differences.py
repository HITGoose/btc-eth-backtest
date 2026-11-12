import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from math import fsum

from audit_gate_october import SEPTEMBER
from backtest_squeeze_short import HOUR
from combined_crypto_portfolio import WORK, close_enough, ms
from compare_gate_strategies_by_year import OUTPUTS, summarize_gate_books
from extended_crypto_portfolio import local
from fit_gate_entry_overlay import BASELINE, OCTOBER_WINDOW, SEED, RegimeOverlay, price_books, stacked_signals
from fit_squeeze_ladder_bot import build
from gate_annual_market import EARLIEST_START, MARKET_CACHE, PRICE_FILES, WINDOWS
from gate_october_regime_entries import DATA_END, DIRECTIONS, market_schedules
from gate_public_data import save_json
from gate_v13_targets import MONTHLY
from replay_gate_annual import PATH_ORDERS, replay_annual_asset
from replay_gate_bot import PATHS
from replay_gate_regime_october import replay_with_refinement
from replay_gate_selected_3x import PRIOR_ALIGNMENT_RESULT as SELECTED_REPORT


RESULT = WORK / "gate_12h_fit_difference_checks.json"
BASE_METRICS = ("opens", "return_pct", "mdd_15m_pct", "mdd_1m_pct", "wins", "losses", "hard_stops",
                "pnl_by_asset_usdt", "pnl_by_side_usdt", "pnl_by_regime_usdt", "fills_by_regime", "quote_resolution_fallbacks")
OCTOBER_CASES = ("dense_core", "six_lines", "selected", "five_lines_instead", "resume_in_transition",
                 "remove_range_width_cap", "trend_direction_only", "fast_er_020")


def prepare(files, start, end, pair, policy):
    prepared, fast_020_contexts = {}, {}
    for asset, path in files.items():
        leg = build(path, start, end)
        core, context = market_schedules(asset, leg, price_file=WORK / path, include_gate_confirmation=True,
                                        regime_thresholds=pair)
        base = core[BASELINE]
        six = {t: s for t, s in base.items() if context[t]["gate_confirmation"]["aligned_lines"] == 6}
        pause = {t: s for t, s in six.items() if context[t]["regime"] != "transition"}
        width = {t: s for t, s in pause.items() if context[t]["regime"] != "range" or
                 context[t]["gate_confirmation"]["entry_bandwidth_pct"] <= policy.range_entry_bandwidth_pct}
        direction = {t: s for t, s in width.items() if context[t]["regime"] == "range" or DIRECTIONS[context[t]["regime"]] == s}
        chosen = stacked_signals(base, context, policy)
        assert chosen.items() <= direction.items() <= width.items() <= pause.items() <= six.items() <= base.items()
        _, fast_020 = market_schedules(asset, leg, price_file=WORK / path, include_gate_confirmation=True,
                                       regime_thresholds=((pair[0][0], 0.20), pair[1]))
        schedules = {"dense_core": base, "six_lines": six, "six_then_pause": pause, "six_pause_range_width": width,
                     "trend_direction_only": direction, "selected": chosen,
                     "five_lines_instead": stacked_signals(base, context, policy, min_aligned_lines=5),
                     "resume_in_transition": stacked_signals(base, context, replace(policy, pause_transition=False)),
                     "remove_range_width_cap": stacked_signals(base, context, replace(policy, range_entry_bandwidth_pct=None)),
                     "fast_er_020": stacked_signals(base, fast_020, policy)}
        assert all(s.items() <= base.items() for s in schedules.values())
        prepared[asset] = leg, schedules, context
        fast_020_contexts[asset] = fast_020
    return prepared, fast_020_contexts


def monthly_results(raw, start, end):
    previous = dict(SEED)
    months = []
    cursor = start
    while cursor < end:
        date = datetime.fromisoformat(local(cursor))
        y, m = (date.year + 1, 1) if date.month == 12 else (date.year, date.month + 1)
        next_month = min(end, ms(datetime(y, m, 1, tzinfo=date.tzinfo).isoformat()))
        index = (next_month - start) // 60_000 - 1
        values = {asset: result["marks"][index] for asset, result in raw.items()}
        months.append({"month": date.month, "return_pct": 100 * (fsum(values.values()) / fsum(previous.values()) - 1),
                       "net_usdt_by_asset": {asset: values[asset] - previous[asset] for asset in values}})
        previous = values
        cursor = next_month
    return months


def metrics(stats, prepared, mode, start, end):
    return {**{k: stats[k] for k in BASE_METRICS},
            "eligible_15m_signals": {a: sum(start <= t < end for t in s[mode]) for a, (_, s, _) in prepared.items()}}


def run_2020(pair, policy, reference, pool):
    year = 2020
    start, end = WINDOWS[year]
    market = json.loads((MARKET_CACHE / "prepared_market.json").read_text(encoding="utf-8"))
    prepared, fast_context = prepare(PRICE_FILES, max(EARLIEST_START, start - 30 * 24 * HOUR), end, pair, policy)
    cases = {}
    for mode in next(iter(prepared.values()))[1]:
        cases[mode] = {}
        for order in PATH_ORDERS:
            jobs = {a: pool.submit(replay_annual_asset, a, year, leg, s[mode], market[a]["years"][str(year)], order,
                                  use_cached_prints=False) for a, (leg, s, _) in prepared.items()}
            raw = {a: job.result() for a, job in jobs.items()}
            contexts = fast_context if mode == "fast_er_020" else {a: p[2] for a, p in prepared.items()}
            stats = summarize_gate_books(raw, contexts, start, end, SEED)
            assert not any(stats["quote_resolution_fallbacks"].values())
            if mode == "selected":
                expected = reference["annual"]["2020"]["execution"][order]
                close_enough(stats["return_pct"], expected["return_pct"])
                assert stats["opens"] == expected["opens"]
            row = metrics(stats, prepared, mode, start, end)
            row["monthly"] = monthly_results(raw, start, end)
            close_enough(fsum(fsum(m["net_usdt_by_asset"].values()) for m in row["monthly"]), stats["ending_usdt"] - fsum(SEED.values()))
            cases[mode][order] = row
        print("2020", mode, [(o, round(q["return_pct"], 2), round(q["mdd_15m_pct"], 2), q["opens"],
                             {s: round(n, 2) for s, n in q["pnl_by_regime_usdt"].items()}) for o, q in cases[mode].items()], flush=True)
    return cases


def run_october(pair, policy, reference, pool):
    start, end = OCTOBER_WINDOW
    prepared, fast_context = prepare(PATHS, SEPTEMBER, DATA_END, pair, policy)
    books = dict(zip(PATHS, pool.map(price_books, PATHS), strict=True))
    raw, refinement = replay_with_refinement({a: (*p, books[a][0]) for a, p in prepared.items()}, OCTOBER_CASES)
    cases = {}
    for mode in OCTOBER_CASES:
        contexts = fast_context if mode == "fast_er_020" else {a: p[2] for a, p in prepared.items()}
        stats = summarize_gate_books({a: b[mode] for a, b in raw.items()}, contexts, start, end, SEED)
        if mode == "selected":
            close_enough(stats["return_pct"], reference["october_exact"]["strategy"]["return_pct"])
            assert stats["opens"] == reference["october_exact"]["strategy"]["opens"]
        cases[mode] = metrics(stats, prepared, mode, start, end)
        print("OCT", mode, round(stats["return_pct"], 2), stats["opens"],
              {a: len(x) for a, x in stats["quote_resolution_fallbacks"].items()}, flush=True)
    return {"cases": cases, "refinement": refinement}


def main():
    reference = json.loads(SELECTED_REPORT.read_text(encoding="utf-8"))
    policy = RegimeOverlay(**reference["policy"])
    pair = tuple(tuple(x) for x in reference["er_windows_and_thresholds"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        annual = run_2020(pair, policy, reference, pool)
        october = run_october(pair, policy, reference, pool)
    save_json(RESULT, {"2020_cases": annual, "reported_2020_months_pct": MONTHLY[2020], "october": october})


if __name__ == "__main__":
    main()
