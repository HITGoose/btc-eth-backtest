import json
from math import prod
from statistics import fmean

from combined_crypto_portfolio import WORK


# Whole-percent labels transcribed from the v1.3 monthly heatmap.
MONTHLY = {
    2013: (-13, 18, 21, 0, 37, -31, -17, 25, -16, 18, 9, 0),
    2014: (-10, 15, 0, 31, -1, -21, -25, -11, 5, -1, 9, 3),
    2015: (9, -7, 4, 27, -3, 0, 35, 8, -14, 19, -4, 8),
    2016: (5, -14, -20, 15, -4, 32, 2, -4, -5, 2, -2, 19),
    2017: (4, 18, 9, 17, -3, 1, 14, 9, 0, 3, 9, -3),
    2018: (17, 0, 1, 4, 0, -10, -4, -2, -10, -14, 39, 0),
    2019: (-11, 3, -9, 24, 6, 18, -1, 1, -2, -3, 3, 10),
    2020: (7, 2, 4, 32, 8, 0, -4, -1, 1, 13, 17, 1),
    2021: (1, 7, -3, 11, 0, 0, 0, 3, 2, 6, -2, 1),
    2022: (37, 4, 17, 4, -1, -6, -3, 11, 5, 18, 13, -17),
    2023: (15, 3, 13, -13, -2, 25, 1, 39, -6, 23, 3, -8),
    2024: (10, 22, -2, -2, -7, 10, 3, -5, -12, 10, 3, 29),
    2025: (18, 8, 17, 2, 1, 8, -3, -2, -3, 10, 7, -11),
    2026: (21, 12, 2, 4, 8, 5, -5, 12, 1, 15),
}

# Bar heights measured against the labelled 14.7% high and 0% axis.
# The last item in each row is the underlying move implied by the ladder.
OCTOBER_BARS = (
    ("ETH", 2.7, 1), ("ETH", -6.4, -2), ("BTC", 2.7, 1), ("BTC", -6.1, -2),
    ("ETH", 2.9, 1), ("ETH", 14.7, 5), ("BTC", -6.2, -2), ("BTC", 2.8, 1),
    ("ETH", 2.8, 1), ("BTC", 5.8, 2), ("ETH", 8.8, 3), ("ETH", 2.8, 1),
    ("BTC", 2.8, 1), ("BTC", -6.1, -2), ("BTC", 2.7, 1), ("BTC", -6.3, -2),
    ("ETH", -6.1, -2), ("BTC", 5.9, 2), ("BTC", 2.7, 1),
)


def compounded(returns, *, periods_per_year=None):
    exponent = 1 if periods_per_year is None else periods_per_year / len(returns)
    return {"central_pct": 100 * (prod(1 + r / 100 for r in returns) ** exponent - 1),
            "range_if_rounded_to_whole_pct": [100 * (prod(1 + (r + error) / 100 for r in returns) ** exponent - 1)
                                              for error in (-0.5, 0.5)]}


def targets():
    early = [r for y in range(2013, 2020) for r in MONTHLY[y]]
    early_both = list(MONTHLY[2016][6:]) + [r for y in range(2017, 2020) for r in MONTHLY[y]]
    recent = [r for y in range(2020, 2027) for r in MONTHLY[y]]
    assert len(early + recent) == 166 and len(recent) == 82
    x = [r[2] for r in OCTOBER_BARS]
    y = [r[1] for r in OCTOBER_BARS]
    leverage = sum((a - fmean(x)) * (b - fmean(y)) for a, b in zip(x, y)) / sum((a - fmean(x)) ** 2 for a in x)
    intercept = fmean(y) - leverage * fmean(x)
    returns_by_asset = {a: [r for asset, r, _ in OCTOBER_BARS if asset == a] for a in ("BTC", "ETH")}
    equity_factors = {a: prod(1 + r / 100 for r in returns) for a, returns in returns_by_asset.items()}
    weight_50_50_sensitivity = []
    for error in (-0.15, 0.15):
        factors = [prod(1 + (r + error) / 100 for r in returns) for returns in returns_by_asset.values()]
        weight_50_50_sensitivity.append(100 * (fmean(factors) - 1))
    sleeve_mix = {"equal_start_weight_account_return_pct": (fmean(equity_factors.values()) - 1) * 100,
                  "equal_start_weight_if_bar_estimates_vary_by_0.15_pp": weight_50_50_sensitivity,
                  "implied_ETH_start_weight_if_only_these_trades": (1.149 - equity_factors["BTC"])
                  / (equity_factors["ETH"] - equity_factors["BTC"]),
                  "sleeve_return_pct": {a: 100 * (x - 1) for a, x in equity_factors.items()}}
    return {
        "monthly_account_return_rounded_pct": MONTHLY,
        "annual_from_rounded_months": {y: compounded(returns) for y, returns in MONTHLY.items()},
        "cagr_checks": {name: {**compounded(values, periods_per_year=12), "reported_pct": reported,
                               "reported_mark_to_market_mdd_pct": mdd, "months": len(values)}
                        for name, values, reported, mdd in (("2013_2019", early, 35.4, 52.9),
                                                            ("2016_July_2019", early_both, 44.2, 36.8),
                                                            ("2020_2026_October", recent, 84.6, 30.0))},
        "positive_months": {"headline_2013_to_October_2026": 100, "rounded_labels_positive": sum(r > 0 for r in early + recent),
                            "rounded_labels_zero": sum(r == 0 for r in early + recent), "headline_since_2020": 56,
                            "since_2020_rounded_positive": sum(r > 0 for r in recent), "since_2020_rounded_zero": sum(r == 0 for r in recent)},
        "standalone_vs_portfolio_pct": {2018: {"BTC": -34.9, "ETH": 81.3, "combined": 13.0},
                                        2022: {"BTC": 265.6, "ETH": -6.8, "combined": 103.5},
                                        2025: {"BTC": 3.2, "ETH": 110.9, "combined": 61.0}},
        "october_2026": {
            "reported_account_return_pct": 14.9, "reported_mdd_pct": 10.9, "reported_entries": 19,
            "reported_wins": 13, "reported_losses": 6,
            "approximate_ordered_bars": OCTOBER_BARS,
            "estimated_effective_leverage_if_ladder_moves_are_correct": leverage,
            "estimated_account_cost_intercept_pp": intercept,
            "conditional_sleeve_compounding_check": sleeve_mix,
            "sleeve_compounding_assumptions": "Bar height is return on its sleeve before each trade. Only the 19 trades "
                                               "affect the month; no transfers, funding or boundary position revaluation.",
        },
    }


if __name__ == "__main__":
    path = WORK.parent / "outputs" / "BTC_ETH_Gate_v13_slide_targets.json"
    path.write_text(json.dumps(targets(), indent=2) + "\n", encoding="utf-8")
