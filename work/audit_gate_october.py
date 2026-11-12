import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from math import fsum

from backtest_squeeze_short import HOUR
from combined_crypto_portfolio import BAR, WORK, ms
from extended_crypto_portfolio import local
from fit_bot_execution_audit import ExecutionReplay, trend_regimes
from fit_squeeze_ladder_bot import Settings, Sizing, build, simulate
from gate_public_data import ARCHIVE, archived_minutes, save_json
from gate_v13_targets import OCTOBER_BARS
from replay_gate_bot import ENTRY, PATHS
from run_original_ladder_compare import aggregate


SEPTEMBER = ms("2026-09-01T00:00:00+08:00")
OCTOBER = ms("2026-10-01T00:00:00+08:00")
END = ms("2026-11-01T00:00:00+08:00")
MINUTE = 60_000


def archived_months(asset):
    rows = {}
    for month in (8, 9, 10):
        rows.update(archived_minutes(asset, 2026, month, start=SEPTEMBER // 1000 - 60, end=END // 1000))
    assert sorted(rows) == list(range(SEPTEMBER // 1000 - 60, END // 1000, 60))
    return rows


def checked_minutes(legs):
    cache = {}
    discrepancies = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        markets = dict(zip(legs, pool.map(archived_months, legs)))
    for asset, segments in legs.items():
        source = markets[asset]
        by_bar = {}
        mismatches = []
        for t, b in segments[0].bars.items():
            block = [source[s][:4] for s in range(t // 1000, (t + BAR) // 1000, 60)]
            observed = aggregate(block)
            expected = (b.o, b.h, b.l, b.c)
            if observed == expected:
                by_bar[str(t)] = block
            else:
                mismatches.append({"time": local(t), "archive_ohlc": observed, "gate_15m_ohlc": expected})
        cache[asset] = by_bar
        discrepancies[asset] = mismatches
    return cache, discrepancies


def summarise(result, start):
    trace = result["equity_trace"]
    equity_open = 1000 if start == OCTOBER else next(eq for t, eq in trace if t == OCTOBER)
    month = [(t, value) for t, value in trace if t > OCTOBER]
    peak = equity_open
    drawdown = 0.0
    for _, equity in month:
        peak = max(peak, equity)
        drawdown = max(drawdown, 100 * (1 - equity / peak))
    rows = [{"asset": asset, **trade} for asset, trades in result["trades"].items() for trade in trades]
    closed = sorted((r for r in rows if OCTOBER <= r["closed_ms"] < END), key=lambda r: (r["closed_ms"], r["opened_ms"]))
    opened = Counter(r["asset"] for r in rows if OCTOBER <= r["opened_ms"] < END)
    for asset, row in result["open_positions"].items():
        opened[asset] += OCTOBER <= ms(row["opened_local"]) < END
    return {"opening_equity_usdt": equity_open, "ending_equity_usdt": month[-1][1],
            "return_pct": 100 * (month[-1][1] / equity_open - 1), "mdd_pct_at_15m_closes": drawdown,
            "opens": dict(opened), "closes": dict(Counter(r["asset"] for r in closed)),
            "wins": sum(r["net"] > 0 for r in closed), "losses": sum(r["net"] < 0 for r in closed),
            "closed_net_usdt": fsum(r["net"] for r in closed),
            "closed_sequence": [{"asset": r["asset"], "opened_local_approx": local(r["opened_ms"]),
                                 "closed_local_approx": local(r["closed_ms"]), "side": r["side"], "rung": r["rung"],
                                 "reason": r["reason"], "net_pct_of_sleeve_before_fill": 100 * r["net"] / r["opening_sleeve_cash_usdt"]}
                                for r in closed], "open_positions_at_end": result["open_positions"]}


def main():
    legs = {asset: [build(path, SEPTEMBER, END)] for asset, path in PATHS.items()}
    cache, discrepancies = checked_minutes(legs)
    regimes = trend_regimes(legs)

    def trade_with_confirmed_trend(asset, time, side):
        state, *_ = regimes[asset].get(time // HOUR * HOUR, ("transition",))
        return (state, side) not in (("up", -1), ("down", 1))

    tests = {}
    for key, settings, gate in (("visible_entry_uncapped_ladder", ENTRY, None),
                                ("visible_entry_cap5_ladder", replace(ENTRY, exit_policy="fixed"), None),
                                ("older_tighter_entry_uncapped_ladder", Settings(96, 6, 0.15, "uncapped"), None),
                                ("visible_entry_with_causal_direction_filter", ENTRY, trade_with_confirmed_trend)):
        tests[key] = {}
        for label, start, rebalance in (("fresh_october", OCTOBER, False), ("carry_from_september_rebalanced", SEPTEMBER, True),
                                        ("carry_from_september_no_rebalance", SEPTEMBER, False)):
            variants = {}
            for favorable_first in (False, True):
                replay = ExecutionReplay(cache, favorable_first=favorable_first)
                r = simulate(legs, settings, END, start=start, rebalance=rebalance, sizing=Sizing(3, 0.0001, False),
                             replay=replay, signal_gate=gate, capture_trades=True, capture_equity=True)
                case = summarise(r, start)
                case["uncertain_1m_windows"] = len(replay.uncertain_minutes)
                case["uncertain_15m_windows"] = len(replay.uncertain_bars)
                variants["favorable_first" if favorable_first else "adverse_first"] = case
            tests[key][label] = variants
            a, f = variants.values()
            print(key, label, a["opens"], f["opens"], a["wins"], a["losses"], round(a["return_pct"], 2), round(f["return_pct"], 2),
                  round(a["mdd_pct_at_15m_closes"], 2), flush=True)
    report = {"month_utc8": [local(OCTOBER), local(END)],
              "targets_from_slide": {"opens": dict(Counter(a for a, *_ in OCTOBER_BARS)), "wins": 13, "losses": 6,
                                     "return_pct": 14.9, "mdd_pct": 10.9, "ordered_bars": OCTOBER_BARS},
              "market": {"15m_gate_api": True, "monthly_1m_archive_base": ARCHIVE,
                         "verified_1m_blocks": {asset: len(blocks) for asset, blocks in cache.items()},
                         "rejected_1m_blocks": {asset: {"count": len(diffs), "examples": diffs[:10]}
                                                for asset, diffs in discrepancies.items()}},
              "execution_assumptions": "Gate 15m signals and Gate archived 1m bars where validated. "
                                       "Limit references next 15m open with 0.2% offset. No submission delay or 5s poll "
                                       "in these historical approximations. Fees 0.05% per fill, exit slippage 0.02%, "
                                       "no funding. Starts at 500 USDT per sleeve, each sized up to 3x.",
              "tests": tests}
    save_json(WORK.parent / "outputs" / "BTC_ETH_Gate_v13_October_2026_replay.json", report)


if __name__ == "__main__":
    main()
