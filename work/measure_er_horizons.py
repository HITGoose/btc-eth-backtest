import json

import pandas as pd

from combined_crypto_portfolio import BYBIT_DIR, WORK


SOURCE = BYBIT_DIR / "bybit_2025_completed_scratch.csv"
PRICE = ["open", "high", "low", "close"]
STEP = 900_000
TZ = "Asia/Kuala_Lumpur"
YEARS = range(2021, 2026)


def ms(text):
    return pd.Timestamp(text, tz=TZ).value // 1_000_000


def measure_market():
    start, end = ms("2021-01-01"), ms("2026-01-01")
    bars = pd.read_csv(SOURCE, usecols=["timestamp", *PRICE]).set_index("timestamp")
    bars = bars.loc[start - 15 * 96 * STEP : end - STEP]
    assert bars.index.equals(pd.RangeIndex(start - 15 * 96 * STEP, end, STEP))
    close = bars.close
    change = close.diff()

    def er(n):
        path = change.abs().rolling(n).sum()
        return (close.diff(n).abs() / path).mask(path.eq(0), 0)

    forward_5 = er(20).shift(-20)
    forward_24 = er(96).shift(-96)
    forward_move = close.shift(-96).div(close).sub(1).abs().mul(100)
    sample = (bars.index >= start) & forward_24.notna()
    forward_5 = forward_5[sample].lt(0.25)
    forward_24 = forward_24[sample].lt(0.25)
    forward_move = forward_move[sample]
    five_hour_prevalence = er(20)[sample].lt(0.25).mean()
    rows = []
    for hours in range(1, 25):
        values = er(4 * hours)[sample]
        assert values.notna().all()
        fixed = values.lt(0.25)
        matched = values.le(values.quantile(five_hour_prevalence))
        rows.append({
            "hours": hours,
            "low_er_pct": fixed.mean() * 100,
            "next_5h_low_er_pct": forward_5[fixed].mean() * 100,
            "next_24h_low_er_pct": forward_24[fixed].mean() * 100,
            "next_24h_median_abs_move_pct": forward_move[fixed].median(),
            "matched_prevalence_threshold": values.quantile(five_hour_prevalence),
            "matched_prevalence_next_5h_low_er_pct": forward_5[matched].mean() * 100,
            "matched_prevalence_next_24h_low_er_pct": forward_24[matched].mean() * 100,
        })
    market = {
        "observations": int(sample.sum()),
        "unconditional_next_5h_low_er_pct": forward_5.mean() * 100,
        "unconditional_next_24h_low_er_pct": forward_24.mean() * 100,
        "unconditional_next_24h_median_abs_move_pct": forward_move.median(),
        "by_horizon": rows,
    }
    (WORK / "er_horizons_market.json").write_text(json.dumps(market, indent=2))
    print(json.dumps({k: v for k, v in market.items() if k != "by_horizon"}))


if __name__ == "__main__":
    measure_market()
