import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from math import fsum

from backtest_squeeze_short import HOUR
from combined_crypto_portfolio import WORK, ms
from extended_crypto_portfolio import local
from fit_bot_execution_audit import CACHE, ExecutionReplay, compare, fetch_minutes, fit_legs, targets, trend_regimes
from fit_squeeze_ladder_bot import END, START, Settings, Sizing, simulate


OUTPUTS = WORK.parent / "outputs"
EXTRA_MINUTES = WORK / "formal_bot_history_verified_minutes.json"
SCREEN_ENTRY = Settings(96, 5, 0.25)
REPORT_SIZING = Sizing(5, 0.0001, False)


def by_regime(result, regimes):
    rows = defaultdict(lambda: {"trades": 0, "hard_stops": 0, "net_usdt": [], "return_on_notional_pct": []})
    for asset, trades in result["trades"].items():
        for trade in trades:
            t = trade["signal_ms"]
            state, *_ = regimes[asset].get(t // HOUR * HOUR, ("transition",))
            row = rows[(local(t)[:4], state, trade["side"])]
            row["trades"] += 1
            row["hard_stops"] += trade["reason"] == "hard_stop"
            row["net_usdt"].append(trade["net"])
            row["return_on_notional_pct"].append(100 * trade["net"] / trade["notional"])
    years = defaultdict(dict)
    for (year, state, side), row in sorted(rows.items()):
        years[year].setdefault(state, {})[side] = {
            "closed_trades": row["trades"], "hard_stops": row["hard_stops"],
            "net_usdt": fsum(row["net_usdt"]),
            "mean_net_pct_of_notional": fsum(row["return_on_notional_pct"]) / row["trades"],
        }
    return dict(years)


def history_replay():
    legs = fit_legs()
    regimes = trend_regimes(legs)
    market = {a: {t: b for leg in ls for t, b in leg.bars.items()} for a, ls in legs.items()}

    def direction_allowed(asset, time, side):
        regime, *_ = regimes[asset].get(time // HOUR * HOUR, ("transition",))
        return (regime, side) not in (("up", -1), ("down", 1))

    uncapped = replace(SCREEN_ENTRY, exit_policy="uncapped")
    trail_from_8pct = replace(SCREEN_ENTRY, exit_policy="trail_from_8pct")
    cases = {
        "cap5": (SCREEN_ENTRY, None),
        "uncapped": (uncapped, None),
        "trail_from_8pct": (trail_from_8pct, None),
        "cap5_direction_filter": (SCREEN_ENTRY, direction_allowed),
        "uncapped_direction_filter": (uncapped, direction_allowed),
        "trail_from_8pct_direction_filter": (trail_from_8pct, direction_allowed),
    }
    target = targets()
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    extra = json.loads(EXTRA_MINUTES.read_text(encoding="utf-8")) if EXTRA_MINUTES.exists() else {"BTC": {}, "ETH": {}}
    for asset in market:
        cache[asset].update(extra[asset])
    tried = set()
    failed = {}
    refined = 0

    # Refine new 15m ambiguities only. Preserve the prior execution cache and
    # disclose remaining within-minute path differences in both replays.
    for pass_number in range(3):
        results = {}
        unresolved = set()
        for name, (settings, gate) in cases.items():
            branches = {}
            for favorable_first in (False, True):
                replay = ExecutionReplay(cache, favorable_first=favorable_first)
                result = simulate(legs, settings, END, rebalance=True, sizing=REPORT_SIZING,
                                  replay=replay, signal_gate=gate, capture_trades=True)
                result["closed_trades_by_signal_year_regime"] = by_regime(result, regimes)
                result["longest_closed_trade_hours"] = max((r["closed_ms"] - r["opened_ms"]) / HOUR
                                                          for rows in result["trades"].values() for r in rows)
                del result["trades"]
                result["report_error"] = compare(result, target)
                result["unresolved_15m_count"] = len(replay.uncertain_bars)
                result["unresolved_1m_count"] = len(replay.uncertain_minutes)
                branches["favorable_first" if favorable_first else "adverse_first"] = result
                unresolved.update(replay.uncertain_bars)
            results[name] = branches
            print(f"Pass {pass_number + 1} {name}: "
                  f"{branches['adverse_first']['ending_equity_usdt']:.2f} / "
                  f"{branches['favorable_first']['ending_equity_usdt']:.2f}", flush=True)

        pending = sorted(unresolved - tried)
        if not pending or pass_number == 2:
            break
        tried.update(pending)
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = {task: pool.submit(fetch_minutes, task, market) for task in pending}
            for (asset, time, _), job in jobs.items():
                try:
                    prices = job.result()
                    cache[asset][str(time)] = extra[asset][str(time)] = prices
                    refined += 1
                except (ValueError, RuntimeError, AssertionError, OSError) as error:
                    failed[f"{asset} {local(time)}"] = str(error)
        EXTRA_MINUTES.write_text(json.dumps(extra, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"New verified minute windows: {refined}; rejected windows: {len(failed)}", flush=True)

    return {
        "window_local": [local(START), local(END)], "target": target,
        "execution": "Verified archived trade sequences or verified 1m bars where cached, otherwise 15m OHLC. "
                     "Both high/low order conventions are tested. Historical mark prices and fixed-interval "
                     "polling are unavailable for this replay. Equity marked at the 15m close.",
        "capital_assumptions": "1000 USDT initially split 500/500, max 5x per sleeve, monthly 50/50 marked "
                               "rebalance, 0.05% per fill, 0.02% adverse exit slippage; no funding or liquidation model.",
        "data": "Existing continuous BTC and ETH USDT perpetual series. Binance early, Bybit after each venue switch.",
        "exit_policies": {"cap5": "2% initial stop and 1% profit locks through rung 5.",
                          "uncapped": "Keep stepping by 1% as favorable movement increases.",
                          "trail_from_8pct": "Keep the fifth rung until 8% favorable movement, then resume the ladder. "
                                             "This is a sensitivity case past the range of the four live fills."},
        "regimes": "Closed 1h signed efficiency ratios, 24h threshold 0.20 and 120h threshold 0.10. "
                   "Report both directions in each state. The filter only blocks trades against a confirmed up or down state.",
        "new_verified_minute_windows": refined, "failed_new_minute_windows": failed,
        "profiles": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", choices=("live", "history", "all"), default="all", nargs="?")
    section = parser.parse_args().section
    if section in ("live", "all"):
        from replay_formal_bot_trades import audit_live_fills

        live = audit_live_fills(SCREEN_ENTRY)
        (OUTPUTS / "BTC_ETH_bot_formal_fills_audit.json").write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")
    if section in ("history", "all"):
        history = history_replay()
        (OUTPUTS / "BTC_ETH_bot_rules_2020_2025.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
