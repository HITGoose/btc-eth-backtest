import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import numpy as np

from audit_gate_october import SEPTEMBER
from backtest_squeeze_short import HOUR, WARMUP, hourly_regimes
from combined_crypto_portfolio import BAR, WORK, read_market
from compare_gate_fast_windows import RESULT as FAST_WINDOW_REPORT, prepare, transition_coverage
from compare_gate_strategies_by_year import OUTPUTS, add_readable_times, gate_run, summarize_gate_books
from extended_crypto_portfolio import local
from fit_gate_entry_overlay import LIVE_SEED, LIVE_WINDOW, OCTOBER_WINDOW, SEED, RegimeOverlay, matches_live, price_books, run_exact
from fit_squeeze_ladder_bot import build
from gate_annual_market import EARLIEST_START, MARKET_CACHE, PRICE_FILES, WINDOWS
from gate_october_regime_entries import DATA_END
from gate_public_data import save_json
from gate_v13_targets import targets
from replay_gate_annual import PATH_ORDERS
from replay_gate_bot import PATHS
from replay_gate_regime_october import replay_with_refinement


MODE = "12h_120h_scaled"
PRIOR_ALIGNMENT_RESULT = OUTPUTS / "BTC_ETH_Gate_12h_5d_2019_2026_3x_v13_comparison.json"
RESULT = OUTPUTS / "BTC_ETH_Gate_12h_5d_2019_2026_3x_entry_crosses.json"


def competitor_years(target):
    rows = target["annual_from_rounded_months"]
    years = {year: {"return_pct": rows[year]["central_pct"], "source": "rounded monthly heatmap compounded",
                    "range_if_rounded_to_whole_pct": rows[year]["range_if_rounded_to_whole_pct"]} for year in WINDOWS}
    years[2019]["same_window"] = False
    for year in (2022, 2025):
        years[year].update(return_pct=target["standalone_vs_portfolio_pct"][year]["combined"], source="reported portfolio return")
    return years


def run_annual(pair, policy, pool):
    market = json.loads((MARKET_CACHE / "prepared_market.json").read_text(encoding="utf-8"))
    annual = {}
    for year, (start, end) in WINDOWS.items():
        warm_start = max(EARLIEST_START, start - 30 * 24 * HOUR)
        legs = {a: build(path, warm_start, end) for a, path in PRICE_FILES.items()}
        prepared = prepare(PRICE_FILES, legs, MODE, pair, policy=policy, use_entry_crosses=True)
        execution = {}
        for order in PATH_ORDERS if year != 2019 else PATH_ORDERS[:1]:
            q = gate_run(year, MODE, order, market, prepared, pool, use_cached_prints=False)
            assert not any(q["quote_resolution_fallbacks"].values())
            execution[order] = q
        annual[year] = {"window_local": [local(start), local(end)], "transition_coverage": transition_coverage(prepared, start, end),
                        "execution": execution,
                        "unobserved_archive_minutes_by_asset": {a: v["years"][str(year)]["execution_minutes"]["unobserved"]
                                                                for a, v in market.items()}}
        print(year, [(mode, round(q["return_pct"], 2), round(q["mdd_15m_pct"], 2), q["opens"],
                      {a: round(pnl, 2) for a, pnl in q["pnl_by_asset_usdt"].items()}) for mode, q in execution.items()], flush=True)
    return annual


def run_recent(pair, policy, pool):
    legs = {a: build(path, SEPTEMBER, DATA_END) for a, path in PATHS.items()}
    prepared = prepare(PATHS, legs, MODE, pair, policy=policy, use_entry_crosses=True)
    books = dict(zip(PATHS, pool.map(price_books, PATHS), strict=True))
    october_inputs = {a: (*prepared[a], b[0]) for a, b in books.items()}
    october, refinement = replay_with_refinement(october_inputs, (MODE,))
    oct_result = summarize_gate_books({a: result[MODE] for a, result in october.items()},
                                      {a: v[2] for a, v in prepared.items()}, *OCTOBER_WINDOW, SEED)
    nov_result = run_exact(prepared, {a: b[1] for a, b in books.items()}, LIVE_WINDOW, LIVE_SEED, pool, mode=MODE)
    assert not any(oct_result["quote_resolution_fallbacks"].values()) and not any(nov_result["quote_resolution_fallbacks"].values())
    matches = matches_live(nov_result, prepared, MODE)

    btc_bars = read_market(WORK / PATHS["BTC"], SEPTEMBER - WARMUP, DATA_END)
    closes = [b.c for t, b in btc_bars.items() if (t + BAR) % HOUR == 0]
    state = hourly_regimes(np.array(closes), SEPTEMBER - WARMUP + HOUR, thresholds=pair)[LIVE_WINDOW[0]]
    return {"october_exact": {"window_local": [local(t) for t in OCTOBER_WINDOW], "strategy": oct_result, "tape_refinement": refinement},
            "november_exact": {"window_local": [local(t) for t in LIVE_WINDOW], "strategy": nov_result,
                               "entry_comparison": matches, "btc_regime_at_start": state}}


def main():
    prior = json.loads(FAST_WINDOW_REPORT.read_text(encoding="utf-8"))
    frozen = prior["cases"][MODE]
    policy = RegimeOverlay(**prior["policy"])
    pair = tuple(tuple(x) for x in frozen["er_windows_and_thresholds"])
    assert prior["nominal_leverage"] == 3 and all(v == prior["starting_usdt_per_asset"] for v in SEED.values())
    with ThreadPoolExecutor(max_workers=2) as pool:
        annual = run_annual(pair, policy, pool)
        recent = run_recent(pair, policy, pool)

    v13 = targets()
    reported = competitor_years(v13)
    actual_oct = dict(v13["october_2026"])
    actual_oct["opens_by_asset"] = dict(Counter(row[0] for row in actual_oct["approximate_ordered_bars"]))
    recent["october_exact"]["v13_reported"] = actual_oct
    for year, row in annual.items():
        row["v13_reported"] = reported[year]
        if year != 2019:
            row["return_difference_percentage_points"] = {o: q["return_pct"] - reported[year]["return_pct"]
                                                           for o, q in row["execution"].items()}
    document = {"nominal_leverage": 3.0, "starting_usdt_per_asset": prior["starting_usdt_per_asset"], "reset_each_year": True,
                "er_windows_and_thresholds": pair, "policy": asdict(policy), "annual": annual, **recent,
                "entry_confirmation": {"core_macd": "DIF crosses DEA on adjacent closed 15m bars.",
                                       "trend_short_ma": "SMA7 crosses SMA10 on the same close as the MACD cross.",
                                       "cross_equality_counts": False},
                "annual_execution": "2019 actual trade prints. Later years use both modeled Gate 10s OHLC orders. No 2026 cached print insertion in the annual tests.",
                "v13_scope": "Use the user's v1.3 slides associated with approximately 3x sizing. 2019 on the slides covers the full year. "
                             "Historical annual account weights and exact trade lists are unavailable. October 2026 has an aggregate count and per-trade return bars.",
                "v13_standalone_vs_portfolio_pct": v13["standalone_vs_portfolio_pct"]}
    add_readable_times(document)
    save_json(RESULT, document)


if __name__ == "__main__":
    main()
