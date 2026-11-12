import argparse
from calendar import monthrange
import csv
import gzip
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

from backtest_squeeze_short import WARMUP
from combined_crypto_portfolio import BAR, WORK, ms
from gate_public_data import ARCHIVE, save_json
from replay_gate_bot import PATHS as VERIFIED_GATE_15M


ASSETS = ("BTC", "ETH")
MARKET_CACHE = WORK / "gate_annual_market"
MANIFEST = MARKET_CACHE / "archives.json"
EARLIEST_START = ms("2019-12-06T00:00:00+08:00")
END = ms("2026-11-01T00:00:00+08:00")
WINDOWS = {
    year: (EARLIEST_START if year == 2019 else ms(f"{year}-01-01T00:00:00+08:00"),
           END if year == 2026 else ms(f"{year + 1}-01-01T00:00:00+08:00"))
    for year in range(2019, 2027)
}
PRICE_FILES = {a: WORK / f"{a}USDT_Gate_2019_2026_annual.csv" for a in ASSETS}


def stamp_list(first=201911, last=202610):
    stamps = []
    year, month = divmod(first, 100)
    while year * 100 + month <= last:
        stamps.append(f"{year}{month:02}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return stamps


def path_for(asset, kind, stamp):
    return MARKET_CACHE / f"{asset}_{kind}_{stamp}.csv.gz"


def archive_url(asset, kind, stamp):
    return f"{ARCHIVE}/{kind}/{stamp}/{asset}_USDT-{stamp}.csv.gz"


def download(task):
    asset, kind, stamp = task
    path = path_for(asset, kind, stamp)
    url = archive_url(asset, kind, stamp)
    result = {"asset": asset, "resolution": kind, "utc_month": stamp, "source": url}
    if path.exists():
        return {**result, "bytes": path.stat().st_size}
    part = path.with_suffix(".part")
    for attempt in range(4):
        try:
            offset = part.stat().st_size if part.exists() else 0
            request = Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
            with urlopen(request, timeout=25) as response:
                resumed = offset and response.status == 206
                if resumed:
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise OSError(f"unexpected range for {path.name}: {content_range}")
                    expected = int(content_range.rsplit("/", 1)[-1])
                else:
                    expected = response.headers.get("Content-Length")
                with part.open("ab" if resumed else "wb") as stream:
                    shutil.copyfileobj(response, stream, 1024 * 128)
            actual = part.stat().st_size
            if not actual or (expected and int(expected) != actual):
                raise OSError(f"Incomplete download of {path.name}: {actual} bytes (expected {expected})")
            if resumed:
                try:
                    with gzip.open(part, "rb") as archive:
                        while archive.read(1024 * 1024):
                            pass
                except (OSError, EOFError):
                    part.write_bytes(b"")
                    raise
            part.replace(path)
            return {**result, "bytes": actual}
        except (URLError, TimeoutError, OSError, EOFError) as error:
            if isinstance(error, HTTPError) and error.code == 404:
                return {**result, "status": "unavailable"}
            if attempt == 3:
                return {**result, "status": "failed", "error": str(error)}
            sleep(0.4 * (attempt + 1))


def download_archives():
    MARKET_CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(a, k, month) for month in stamp_list() for a in ASSETS
            for k in (("trades",) if month == "201912" else ("candlesticks_1m", "candlesticks_10s"))]
    # Store the smaller 1m product first so fallback data is ready for each year.
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = []
        for row in pool.map(download, jobs):
            results.append(row)
            if len(results) % 24 == 0 or len(results) == len(jobs):
                print(f"Gate archives {len(results)}/{len(jobs)}", flush=True)
    save_json(MANIFEST, results)
    unavailable = [r for r in results if "status" in r]
    print(f"Archive bytes {sum(r.get('bytes', 0) for r in results):,}; unavailable {unavailable}", flush=True)


def load_archive_candles(asset, stamp, step):
    kind = "candlesticks_1m" if step == 60 else "candlesticks_10s"
    path = path_for(asset, kind, stamp)
    if not path.exists():
        return np.empty((0, 6)), 0
    with gzip.open(path, "rb") as stream:
        raw = np.loadtxt(stream, delimiter=",", ndmin=2)
    if not len(raw):
        return np.empty((0, 6)), 0
    # Archive columns are timestamp, volume, close, high, low, open.
    data = raw[:, (0, 5, 3, 4, 2, 1)]
    t, o, high, low, c, v = data.T
    valid = np.isfinite(data).all(axis=1) & (t % step == 0) & (low > 0) & (v >= 0)
    valid &= (low <= np.minimum(o, c)) & (np.maximum(o, c) <= high)
    data = data[valid]
    if not np.all(np.diff(data[:, 0]) > 0):
        data = data[np.argsort(data[:, 0], kind="stable")]
        repeated = np.flatnonzero(np.diff(data[:, 0]) == 0)
        if not np.array_equal(data[repeated], data[repeated + 1]):
            raise ValueError(f"conflicting archive rows: {path}")
        data = data[np.r_[True, np.diff(data[:, 0]) > 0]]
    return data, len(raw) - int(valid.sum())


def aggregate(rows, step):
    if not len(rows):
        return rows
    grouped_time = rows[:, 0].astype(np.int64) // step * step
    starts = np.r_[0, np.flatnonzero(np.diff(grouped_time)) + 1]
    ends = np.r_[starts[1:] - 1, len(rows) - 1]
    return np.column_stack((grouped_time[starts], rows[starts, 1], np.maximum.reduceat(rows[:, 2], starts),
                            np.minimum.reduceat(rows[:, 3], starts), rows[ends, 4], np.add.reduceat(rows[:, 5], starts)))


@lru_cache(maxsize=2)
def read_december_trades(asset):
    path = path_for(asset, "trades", "201912")
    with gzip.open(path, "rb") as stream:
        raw = np.loadtxt(stream, delimiter=",", usecols=(0, 1, 2, 3), ndmin=2)
    t, trade_id, price, size = raw.T
    assert len(t) and np.isfinite(raw).all() and np.all(price > 0), path
    order = np.lexsort((trade_id, t))
    assert len(np.unique(trade_id)) == len(trade_id), path
    return np.column_stack((t[order], price[order], abs(size[order])))


def rebuild_december(asset):
    t, price, size = read_december_trades(asset).T
    ticks = np.column_stack((t, price, price, price, price, size))
    return aggregate(ticks, 60), aggregate(ticks, 10)


def months_in_range(lower, upper):
    first = int(datetime.fromtimestamp(lower, timezone.utc).strftime("%Y%m"))
    last = int(datetime.fromtimestamp(upper - 1, timezone.utc).strftime("%Y%m"))
    return stamp_list(first, last)


def month_sources(asset, lower, upper):
    minutes = []
    tens = []
    audit = {}
    for stamp in months_in_range(lower, upper):
        if stamp == "201912":
            one, ten = rebuild_december(asset)
            one_bad = ten_bad = 0
        else:
            one, one_bad = load_archive_candles(asset, stamp, 60)
            ten, ten_bad = load_archive_candles(asset, stamp, 10)
        y, m = divmod(int(stamp), 100)
        first = int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp())
        last = first + monthrange(y, m)[1] * 86400
        lo, hi = max(lower, first), min(upper, last)
        one = one[(one[:, 0] >= lo) & (one[:, 0] < hi)]
        ten = ten[(ten[:, 0] >= lo) & (ten[:, 0] < hi)]
        minutes.append(one)
        tens.append(ten)
        audit[stamp] = {"one_minute_rows": len(one), "ten_second_rows": len(ten), "one_minute_invalid_in_archive": one_bad,
                        "ten_second_invalid_in_archive": ten_bad, "rebuilt_from_trades": stamp == "201912"}
    return np.concatenate(minutes), np.concatenate(tens), audit


def checked_minutes(one, ten, first, last):
    """Use 1m OHLC as the parent check for every minute of 10s execution."""
    n = (last - first) // 60
    dense = np.zeros((n, 5))
    resolution = np.zeros(n, dtype=np.uint8)
    from_ten = aggregate(ten, 60)
    ten_slots = (from_ten[:, 0].astype(np.int64) - first) // 60
    assert np.all(np.diff(ten_slots) > 0)
    dense[ten_slots] = from_ten[:, 1:]
    resolution[ten_slots] = 10
    one_slots = (one[:, 0].astype(np.int64) - first) // 60
    assert np.all(np.diff(one_slots) > 0)
    equal_ohlc = (dense[one_slots, :4] == one[:, 1:5]).all(axis=1)
    fallback = ~equal_ohlc | (resolution[one_slots] == 0)
    resolution[one_slots[fallback]] = 60
    dense[one_slots] = one[:, 1:]
    observed = resolution > 0
    last_quote = np.maximum.accumulate(np.where(observed, np.arange(n), -1))
    missing = (last_quote >= 0) & ~observed
    dense[missing, :4] = dense[last_quote[missing], 3][:, None]
    return dense, resolution


def prepared_prefix(asset, year):
    return MARKET_CACHE / f"{asset}_{year}"


def prepare_year(asset, year):
    start, end = WINDOWS[year]
    first = (start - (WARMUP if year == 2019 else 0)) // 1000
    last = end // 1000
    seed_first = first - 3600
    path = prepared_prefix(asset, year)
    metadata = path.with_name(path.name + "_meta.json")
    sources = [path_for(asset, kind, stamp) for stamp in months_in_range(seed_first, last)
               for kind in (("trades",) if stamp == "201912" else ("candlesticks_1m", "candlesticks_10s"))]
    file_sizes = {p.name: p.stat().st_size for p in sources if p.exists()}
    if metadata.exists():
        cached = json.loads(metadata.read_text(encoding="utf-8"))
        if cached.get("source_file_sizes") == file_sizes:
            return cached
    raw_one, raw_ten, audit = month_sources(asset, seed_first, last)
    dense, resolution = checked_minutes(raw_one, raw_ten, seed_first, last)
    dense, resolution = dense[60:], resolution[60:]
    if not np.all(dense[:, :4] > 0):
        raise ValueError(f"missing initial price seed for {asset} {year}")
    active = raw_ten[raw_ten[:, 0] >= first]
    ten_time = active[:, 0].astype(np.int64) - first
    assert np.all(np.diff(ten_time) > 0)
    for name, data in (("minutes", dense), ("resolution", resolution), ("ten_time", ten_time.astype(np.int32)),
                       ("ten_prices", active[:, 1:5])):
        np.save(path.with_name(path.name + f"_{name}.npy"), data, allow_pickle=False)
    missing = resolution == 0
    boundary = np.flatnonzero(np.diff(np.r_[False, missing, False]))
    durations = boundary[1::2] - boundary[::2]
    result = {"asset": asset, "year": year, "start_epoch_s": first, "end_epoch_s": last,
              "execution_minutes": {"10s": int((resolution == 10).sum()), "1m": int((resolution == 60).sum()),
                                    "unobserved": int(missing.sum())},
              "longest_unobserved_minutes": int(durations.max()) if len(durations) else 0,
              "source_months": audit, "source_file_sizes": file_sizes}
    save_json(metadata, result)
    print(asset, year, result["execution_minutes"], "longest gap", result["longest_unobserved_minutes"], flush=True)
    return result


def load_prepared(asset, year):
    path = prepared_prefix(asset, year)
    return tuple(np.load(path.with_name(path.name + f"_{name}.npy"), mmap_mode="r", allow_pickle=False)
                 for name in ("minutes", "resolution", "ten_time", "ten_prices"))


def build_15m(asset, coverage):
    with (WORK / VERIFIED_GATE_15M[asset]).open(encoding="utf-8", newline="") as stream:
        verified = {int(row[0]): tuple(map(float, row[1:])) for row in list(csv.reader(stream))[1:]}
    overlap_count = same = empty_bars = 0
    with PRICE_FILES[asset].open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
        for y, meta in coverage.items():
            data, resolution, *_ = load_prepared(asset, y)
            blocks = data.reshape(-1, 15, 5)
            observed = resolution.reshape(-1, 15) != 0
            empty = ~observed.any(axis=1)
            empty_bars += int(empty.sum())
            close = blocks[:, -1, 3]
            opening = blocks[np.arange(len(blocks)), observed.argmax(axis=1), 0]
            high = np.max(np.where(observed, blocks[:, :, 1], -np.inf), axis=1)
            low = np.min(np.where(observed, blocks[:, :, 2], np.inf), axis=1)
            prices = np.stack((opening, np.where(empty, close, high), np.where(empty, close, low),
                               blocks[:, -1, 3], blocks[:, :, 4].sum(axis=1)), axis=1)
            for t, price in zip(range(meta["start_epoch_s"] * 1000, meta["end_epoch_s"] * 1000, BAR), prices, strict=True):
                if official := verified.get(t):
                    overlap_count += 1
                    same += tuple(price[:4]) == official[:4]
                    price = official
                writer.writerow([t, *price])
    return {"overlap_with_frozen_api_15m": overlap_count, "exact_ohlc_matches": same,
            "entire_15m_bars_unobserved": empty_bars,
            "frozen_api_15m_used_in_overlap": True}


def prepare_market():
    coverage = {a: {} for a in ASSETS}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {(a, y): pool.submit(prepare_year, a, y) for y in WINDOWS for a in ASSETS}
        for (a, y), job in jobs.items():
            coverage[a][y] = job.result()
    audit = {a: {"years": years, "api_overlap": build_15m(a, years)} for a, years in coverage.items()}
    save_json(MARKET_CACHE / "prepared_market.json", audit)
    print("Completed Gate market assembly", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("download", "prepare"))
    args = parser.parse_args()
    if args.action == "download":
        download_archives()
    else:
        prepare_market()
