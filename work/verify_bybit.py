from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time

import pandas as pd
import requests

from combined_crypto_portfolio import BYBIT_DIR, WORK


API = "https://api.bybit.com/v5/market/kline"
STEP = 900_000
COLS = ["open", "high", "low", "close"]


def ms(value):
    return pd.Timestamp(value).value // 1_000_000


def fetch(page):
    times = list(page)
    params = {
        "category": "linear", "symbol": "BTCUSDT", "interval": "15",
        "start": times[0], "end": times[-1], "limit": len(times),
    }
    for attempt in range(4):
        try:
            response = requests.get(API, params=params, timeout=15)
            response.raise_for_status()
            body = response.json()
            if body["retCode"] != 0:
                raise ValueError(body["retMsg"])
            result = body["result"]
            rows = sorted(result["list"], key=lambda row: int(row[0]))
            if (result["symbol"], result["category"]) != ("BTCUSDT", "linear"):
                raise ValueError("unexpected contract")
            if [int(row[0]) for row in rows] != times:
                raise ValueError(f"wrong timestamp coverage, got {len(rows)} rows")
            return [[int(row[0]), *map(float, row[1:5])] for row in rows]
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"Page {times[0]} attempt {attempt + 1}: {exc}", flush=True)
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def audit(left, right, index):
    assert index.isin(left.index).all() and index.isin(right.index).all()
    delta = (left.loc[index] - right.loc[index]).abs()
    assert delta.notna().to_numpy().all()
    return {
        "candles": len(index),
        "different_candles": int(delta.ne(0).any(axis=1).sum()),
        "max_abs_difference_usdt": delta.max().to_dict(),
    }


def main():
    prior = ms("2024-12-31T16:00:00Z")
    start = ms("2025-12-31T16:00:00Z")
    stop = ms("2026-09-30T16:00:00Z")
    warm = start - 15 * 96 * STEP
    old_year = pd.RangeIndex(prior, start, STEP)
    warmup = pd.RangeIndex(warm, start, STEP)
    window = pd.RangeIndex(start, stop, STEP)
    assert len(old_year) == 35040 and len(warmup) == 1440 and len(window) == 26208
    archive = pd.read_parquet(BYBIT_DIR / "bybit_BTCUSDT_15m_source_scratch.parquet")
    archive["timestamp"] = archive["date"].dt.as_unit("ms").astype("int64")
    archive = archive.set_index("timestamp")[COLS].sort_index()
    old = pd.read_csv(BYBIT_DIR / "bybit_2025_completed_scratch.csv", float_precision="round_trip")
    old = old.set_index("timestamp")[COLS].sort_index()
    assert archive.index.is_unique and old.index.is_unique
    checks = {"old_csv_vs_parquet_2025": audit(old, archive, old_year)}
    print(checks, flush=True)

    # Fetch the old year as well so the official check covers the entire overlap.
    pages = [range(t, min(t + 1000 * STEP, stop), STEP) for t in range(prior, stop, 1000 * STEP)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(fetch, pages))
    official = pd.DataFrame([row for batch in batches for row in batch], columns=["timestamp", *COLS])
    official = official.set_index("timestamp")
    assert official.index.equals(pd.RangeIndex(prior, stop, STEP))
    assert (official > 0).to_numpy().all()
    assert (official.low <= official[["open", "close"]].min(axis=1)).all()
    assert (official.high >= official[["open", "close"]].max(axis=1)).all()
    checks.update({
        "old_csv_vs_official_2025": audit(old, official, old_year),
        "parquet_vs_official_warmup": audit(archive, official, warmup),
        "parquet_vs_official_test": audit(archive, official, window),
    })
    print(json.dumps(checks, indent=2), flush=True)
    # The official series is authoritative throughout the input, including warmup.
    data = official.loc[warm:stop - STEP]
    assert data.index.equals(pd.RangeIndex(warm, stop, STEP))
    path = WORK / "bybit_BTCUSDT_15m_2026_JanSep_scratch.csv"
    data.to_csv(path)
    report = {
        "source": API,
        "category": "linear",
        "symbol": "BTCUSDT",
        "interval_minutes": 15,
        "official_pages": len(pages),
        "warmup_start_utc": pd.Timestamp(warm, unit="ms", tz="UTC").isoformat(),
        "test_start_utc": pd.Timestamp(start, unit="ms", tz="UTC").isoformat(),
        "test_end_exclusive_utc": pd.Timestamp(stop, unit="ms", tz="UTC").isoformat(),
        "warmup_candles": len(warmup),
        "test_candles": len(window),
        "input_missing_candles": 0,
        "input_duplicate_timestamps": 0,
        "last_warmup_close": float(data.at[start - STEP, "close"]),
        "first_test_open": float(data.at[start, "open"]),
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "comparisons": checks,
    }
    (WORK.parent / "outputs" / "BTCUSDT_2026_JanSep_data_audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
