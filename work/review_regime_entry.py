import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import fsum

import numpy as np

from backtest_squeeze_short import END, HOUR, WARMUP, hourly_regimes
from combined_crypto_portfolio import BAR, WORK, close_enough, ms, read_market, year
from extended_crypto_portfolio import ETH_START, START, SWITCH, local
from fit_squeeze_ladder_bot import Settings, build
from run_original_ladder_compare import BTC_EARLY, BTC_LATE, ETH_LATE, launch, markets
from summarize_btc_eth_rsi_priority import replay_journal
from summarize_ladder_overlay_2019_2025 import journal, year_end_mark
from summarize_original_ladder_compare import describe


ENTRY_MODES = ("countertrend_gate", "confirmed_breakout", "developing_breakout", "range_breakout", "range_breakout_volume")
MODES = ("original", *ENTRY_MODES, "profit_close_lock", "profit_runner", "profit_hour_only")
FILES = {"BTC": ((BTC_EARLY, START, SWITCH), (BTC_LATE, SWITCH, END)), "ETH": ((ETH_LATE, ETH_START, END),)}
CHECK_2025 = ms("2025-01-01T00:00:00+08:00")
POLICY = WORK / "regime_entry_policy_2019_2025.json"
OUTPUT = WORK.parent / "outputs" / "BTC_ETH_regime_entry_review_2019_2025.json"
SQUEEZE = Settings(96, 5, 0.25)


def schedules():
    policies = {}
    for asset, segments in FILES.items():
        policies[asset] = policy = {name: {} for name in ENTRY_MODES}
        for file, start, end in segments:
            leg = build(file, start, end)
            market = read_market(WORK / file, start - WARMUP, end)
            hours = [(t + BAR, b.c) for t, b in market.items() if (t + BAR) % HOUR == 0 and t - 3 * BAR in market]
            assert all(b[0] - a[0] == HOUR for a, b in zip(hours, hours[1:]))
            regimes = hourly_regimes(np.array([c for _, c in hours]), hours[0][0])
            direction = {"up": 1, "down": -1}
            policy["countertrend_gate"].update({t: direction[r] for t, (r, _, _) in regimes.items()
                                                if start <= t + HOUR - BAR < end and r in direction})
            last_tight = np.maximum.accumulate(np.where(leg.width <= SQUEEZE.squeeze_threshold, np.arange(len(leg.width)), -1))
            consumed = -1
            for time, side in leg.signals(SQUEEZE).items():
                i = (time - leg.first) // BAR - 1
                episode = int(last_tight[i])
                if episode <= consumed or i == episode or leg.width[i] <= leg.width[i - 1]:
                    continue
                consumed = episode
                tag, fast, slow = regimes.get(time // HOUR * HOUR, ("transition", 0.0, 0.0))
                if direction.get(tag) == side:
                    policy["confirmed_breakout"][time] = side
                if fast * side >= 0.20 and slow * side > -0.10:
                    policy["developing_breakout"][time] = side
                    candle_open = time - BAR
                    current = market[candle_open]
                    prior = [market[candle_open - j * BAR] for j in range(1, 33)]
                    edge = max(b.h for b in prior) if side == 1 else min(b.l for b in prior)
                    if (current.c - edge) * side > 0:
                        policy["range_breakout"][time] = side
                        policy["range_breakout_volume"][time] = side
    POLICY.write_text(json.dumps(policies, separators=(",", ":")), encoding="utf-8")
    return policies


def run_mode(mode):
    original = mode == "original"
    early, late, fresh = (f"regime_entry_{mode}_{suffix}" for suffix in ("binance", "bybit", "fresh2025"))
    scenario = "btc_rsi_4h_control" if original else f"btc_{mode}"
    paired = "btc_eth_shared_control" if original else f"btc_eth_shared_{mode}"
    policy = POLICY if mode in ENTRY_MODES else None
    seed = launch(BTC_EARLY, early, START, SWITCH, "binance", scenario, 500, entry_policy=policy)
    launch(BTC_LATE, late, SWITCH, END, "bybit", paired, next(iter(seed.values()))["endingEquity"], paired=True, entry_policy=policy)
    launch(BTC_LATE, fresh, CHECK_2025, END, "bybit", paired, 500, paired=True, eth_start=CHECK_2025, entry_policy=policy)
    print("Completed", mode, flush=True)
    return early, late, fresh


def formal_fills():
    rows = (
        ("BTC", "2026-11-09T02:06:49", "2026-11-09T05:56:28", 75820.30, 74293.40, 0.002, 2.95, 2),
        ("ETH", "2026-11-09T01:43:07", "2026-11-09T05:56:02", 2229.45, 2121.89, 0.06, 6.36, 5),
        ("ETH", "2026-11-09T06:00:21", "2026-11-09T16:24:42", 2131.13, 2110.00, 0.08, 1.56, 1),
        ("ETH", "2026-11-09T16:43:18", "2026-11-10T21:36:18", 2112.07, 2069.95, 0.08, 3.27, 2),
    )
    out = []
    for asset, opened, closed, entry, exit_price, qty, net, rung in rows:
        gross = (entry - exit_price) * qty
        lock = round(entry * (1 - rung / 100), 1 if asset == "BTC" else 2)
        out.append({"asset": asset, "side": "SHORT", "opened_local": opened + "+08:00", "closed_local": closed + "+08:00",
                    "qty": qty, "entry": entry, "exit": exit_price, "reported_net_usdt": net, "gross_usdt": round(gross, 6),
                    "net_pct_of_entry_notional": 100 * net / (entry * qty), "reported_rung": rung, "model_stop_price": lock,
                    "execution_difference_from_stop_bps": 10_000 * (exit_price / lock - 1),
                    "gross_less_reported_net_usdt": round(gross - net, 6)})
    return out


def new_entry_stats(parts, policy, mode):
    groups = defaultdict(list)
    for part in parts:
        for asset, rows in part[1].items():
            for row in rows:
                if row["setup"] != "squeeze_continuation":
                    continue
                t = ms(row["signal"])
                assert policy[asset][mode][t] == (1 if row["side"] == "LONG" else -1)
                groups[year(t), asset, row["side"]].append(row)
    return {"/".join(map(str, k)): {"trades": len(rows), "net_usdt": fsum(float(r["net"]) for r in rows),
                                    "exit_reasons": dict(Counter(r["reason"] for r in rows))} for k, rows in sorted(groups.items())}


def result(parts, policy, mode):
    res = describe(parts)
    end_mark = year_end_mark(res, parts)
    annual = res["years"]
    final = annual[2025]
    final["ending_equity_usdt"] = end_mark["ending_equity_usdt"]
    final["return_pct"] = end_mark["return_2025_pct"]
    final["cumulative_return_pct"] = end_mark["return_pct"]
    final["peak_equity_usdt"] = max(final["peak_equity_usdt"], final["ending_equity_usdt"])
    for asset, cost in end_mark["synthetic_exit_cost_by_asset_usdt"].items():
        final["asset_net_usdt"][asset] += cost
    close_enough(fsum(final["asset_net_usdt"].values()), final["ending_equity_usdt"] - final["opening_equity_usdt"])
    return {**end_mark, "max_drawdown_pct": res["max_drawdown_pct"], "trades": res["total_trades"],
            "entry_counts_by_asset": res["entries"], "exit_reasons": res["exit_reasons"],
            "annual": annual,
            "new_entry_by_year_asset_side": new_entry_stats(parts, policy, mode)}


def main():
    policy = schedules()
    print("Signals", {a: {m: len(s) for m, s in p.items()} for a, p in policy.items()}, flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = dict(zip(MODES, pool.map(run_mode, MODES), strict=True))
    early_market, late_market = markets(END)
    market_2025 = {a: {t: b for t, b in m.items() if t >= CHECK_2025} for a, m in late_market.items()}
    summaries = {}
    for mode, (early, late, fresh) in runs.items():
        x = replay_journal(early, early_market, {"BTC": "original" if mode == "original" else "BTC"}, 500, START, SWITCH)
        y = replay_journal(late, late_market, {"BTC": "BTC", "ETH": "ETH"}, x[0]["ending_equity_usdt"], SWITCH, END)
        z = replay_journal(fresh, market_2025, {"BTC": "BTC", "ETH": "ETH"}, 500, CHECK_2025, END)
        summaries[mode] = {"full_2019_2025": result([x, y], policy, mode), "fresh_500_2025": result([z], policy, mode)}
        if mode == "original":
            assert journal(early) == journal("through2025_control_binance")
            assert journal(late) == journal("through2025_control_bybit")
            close_enough(summaries[mode]["full_2019_2025"]["ending_equity_usdt"], 1159.6730539650202)
        full, fresh = summaries[mode].values()
        print(mode, "full", round(full["return_pct"], 3), round(full["max_drawdown_pct"], 3), full["trades"],
              "annual", {y: round(r["return_pct"], 3) for y, r in full["annual"].items()},
              "fresh 2025", round(fresh["return_pct"], 3), round(fresh["max_drawdown_pct"], 3), fresh["trades"], flush=True)
    diagnostics = json.loads((WORK / "original_bot_regime_diagnostics.json").read_text(encoding="utf-8"))
    out = {
        "start_local": local(START), "end_exclusive_local": local(END), "eth_start_local": local(ETH_START),
        "initial_usdt": 500, "single_asset_opening_leverage_cap": 2.5, "shared_gross_cap": 5,
        "fees_pct_per_fill": 0.05, "slippage_pct_per_fill": 0.02, "funding_modeled": False,
        "regime": "Signed efficiency ratios from closed 1-hour bars, 24h >= 0.20 and 120h >= 0.10 in the same direction. "
                  "Developing variant also permits a 24h trend when the 120h ratio is not an opposing trend.",
        "entry": "Continuation supplement uses 15m SMA/EMA 20/60/120, bandwidth <=0.25% within 96 bars, "
                 "5 of 6 lines sloping with price outside the band, matching MACD sign, and first qualifying expansion "
                 "per compression episode. Existing signals have priority. Range-breakout variants require the same close "
                 "to exceed the preceding 8h extremes, with optional directional volume >=1.5x the prior 20-bar median.",
        "exit": "Original hard price stop 2%, 0.8% partial, 15m reversal and 1h range-short timeout.",
        "profit_exit_variants": "After the partial, a closed 15m bar at +2% or better moves the stop to +1% for the next bar. "
                                "Runner mode can defer a MA5/MA30 exit until the next hourly close if the last completed hour "
                                "is on the position side of its SMA30 and neither 15m nor 1h structure is opposite. "
                                "The stop and any intervening 15m structure exit still apply. "
                                "The hour-only mode tests the same bounded delay with the original 2% stop and no new profit floor.",
        "comparison": summaries, "diagnostic_attribution": diagnostics, "formal_live_fill_check": formal_fills(),
    }
    OUTPUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
