import json
from collections import Counter, defaultdict
from math import fsum
from statistics import median

from backtest_squeeze_short import HOUR
from combined_crypto_portfolio import WORK, ms, year
from fit_bot_execution_audit import CACHE, ExecutionReplay, fit_legs, trend_regimes
from fit_squeeze_ladder_bot import END, Settings, Sizing, simulate
from summarize_ladder_overlay_2019_2025 import TAG, journal


def direction_context(regime, side):
    if regime not in ("up", "down"):
        return regime
    return "with_trend" if (regime == "up") == (side == "LONG") else "against_trend"


def stats(rows):
    rates = [100 * r["net"] / r["notional"] for r in rows]
    return {"trades": len(rows), "net_usdt": fsum(r["net"] for r in rows),
            "mean_net_pct_of_notional": fsum(rates) / len(rates), "median_net_pct_of_notional": median(rates),
            "winners": sum(rate > 0 for rate in rates), "exits": dict(Counter(r["reason"] for r in rows))}


def original_trades():
    return [(r["scenario"], {"signal_ms": ms(r["signal"]), "opened_ms": ms(r["opened"]), "closed_ms": ms(r["closed"]),
                             "side": r["side"], "notional": float(r["first_entry"]) * float(r["first_qty"]),
                             "reason": r["reason"], "net": float(r["net"])})
            for r in journal(f"{TAG}_control_bybit")]


def attribute(trades, regimes):
    asset_side, regime_side, combined = defaultdict(list), defaultdict(list), defaultdict(list)
    for asset, row in trades:
        t = row["signal_ms"]
        y = year(t)
        if y < 2022:
            continue
        regime = regimes[asset].get(t // HOUR * HOUR, ("transition",))[0]
        side = row["side"]
        context = direction_context(regime, side)
        asset_side[y, asset, side].append(row)
        regime_side[y, context].append(row)
        combined[y, asset, side, context].append(row)
    return {key: {"/".join(map(str, k)): stats(rows) for k, rows in sorted(groups.items())}
            for key, groups in (("by_year_asset_side", asset_side), ("by_year_regime", regime_side),
                                ("by_year_asset_side_regime", combined))}


def diagnose():
    legs = fit_legs()
    regimes = trend_regimes(legs)
    replay = ExecutionReplay(json.loads(CACHE.read_text(encoding="utf-8")))
    clone = simulate(legs, Settings(96, 6, 0.15, "time_72h"), END, rebalance=True, sizing=Sizing(5, 0.0001, False),
                     replay=replay, capture_trades=True)
    prior = json.loads((WORK.parent / "outputs" / "BTC_ETH_bot_report_fit_audit_2020_2025.json").read_text(encoding="utf-8"))
    assert clone["ending_equity_usdt"] == prior["tests"]["live_lots_5x"]["backtest"]["ending_equity_usdt"]
    trades = [(asset, r) for asset, rows in clone["trades"].items() for r in rows]
    result = {"original": attribute(original_trades(), regimes), "bot_approximation": attribute(trades, regimes)}
    (WORK / "original_bot_regime_diagnostics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, groups in result.items():
        print(name)
        for grouping in ("by_year_asset_side", "by_year_regime"):
            for key, r in groups[grouping].items():
                print(key, r["trades"], round(r["net_usdt"], 2), round(r["mean_net_pct_of_notional"], 3), r["exits"])
    return result


if __name__ == "__main__":
    diagnose()
