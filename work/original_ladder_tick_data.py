import csv
import gzip
import io
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import chain

import requests

from combined_crypto_portfolio import BAR


MINUTE = 60_000
DAY = 86_400_000


def bybit_ticks(response):
    with gzip.GzipFile(fileobj=response.raw) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        time_column, price_column = (header.index(key) for key in ("timestamp", "price"))
        for row in reader:
            if row:
                yield float(row[time_column]) * 1000, float(row[price_column])


def binance_ticks(response):
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        files = archive.namelist()
        assert len(files) == 1, files
        with archive.open(files[0]) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if row and row[0].isdigit():
                    yield int(row[4]), float(row[1])


def download_group(venue, asset, day, windows):
    symbol = asset + "USDT"
    if venue == "bybit":
        url = f"https://public.bybit.com/trading/{symbol}/{symbol}{day}.csv.gz"
        parser = bybit_ticks
    else:
        url = f"https://data.binance.vision/data/futures/um/daily/trades/{symbol}/{symbol}-trades-{day}.zip"
        parser = binance_ticks
    tapes = dict((window, []) for window in windows)
    starts_by_duration = {length: {t for t, span in windows if span == length} for length in (MINUTE, BAR)}
    low = min(t for t, _ in windows)
    high = max(t + length for t, length in windows)
    seen_later = False
    with requests.get(url, stream=venue == "bybit", timeout=(12, 30)) as response:
        response.raise_for_status()
        stream = parser(response)
        try:
            first = next(stream)
            # Some of the early Bybit trade archives are newest first.
            ascending = first[0] % DAY < DAY / 2
            for t, price in chain((first,), stream):
                passed = t >= high + 10_000 if ascending else t < low - 10_000
                if passed:
                    if seen_later:
                        break
                    seen_later = True
                for length, starts in starts_by_duration.items():
                    if starts and (start := int(t // length) * length) in starts:
                        tapes[(start, length)].append((t, price))
        finally:
            stream.close()
    if not ascending:
        for prints in tapes.values():
            prints.reverse()
    return url, tapes


def load_windows(tasks, venue_at):
    grouped = defaultdict(list)
    for asset, start, duration in tasks:
        day = datetime.fromtimestamp(start / 1000, timezone.utc).date().isoformat()
        grouped[venue_at(start), asset, day].append((start, duration))

    def worker(item):
        (venue, asset, day), windows = item
        try:
            url, tapes = download_group(venue, asset, day, windows)
            result = []
            for (start, duration), prints in tapes.items():
                prints.sort(key=lambda trade: trade[0])
                result.append((asset, start, duration, url, prints, None if prints else "No trades in this interval"))
            return result
        except Exception as error:
            return [(asset, start, duration, None, [], str(error)) for start, duration in windows]

    with ThreadPoolExecutor(max_workers=5) as pool:
        return [item for group in pool.map(worker, grouped.items()) for item in group]


def validate_window(start, duration, prints, expected):
    prices = [p for _, p in prints]
    observed = (prices[0], max(prices), min(prices), prices[-1])
    if observed == expected:
        return prices, None
    opening = expected[0]
    if observed[0] != opening:
        reconstructed = (max(opening, observed[1]), min(opening, observed[2]), observed[3])
        if reconstructed == expected[1:]:
            # Keep the checked candle open, then follow the archived prints.
            return [opening, *prices], {"frozen_open": opening, "archive_open": observed[0]}
    # A frozen 15-minute close can differ from the final archive print. Keep its
    # indicator/valuation close and use the tape only for exits if the frozen
    # price appears among prints at the end and the O/H/L agree exactly.
    if duration == BAR and observed[:3] == expected[:3] and any(
        p == expected[3] and t >= start + duration - 10_000 for t, p in prints
    ):
        return prices, {"frozen_close": expected[3], "archive_close": observed[3]}
    raise ValueError(f"Public trade OHLC {observed} differs from the verified candle {expected}")


def refine_ticks(cache, tasks, parent_bar, venue_at):
    failures = {}
    count = 0
    for asset, start, duration, url, prints, error in load_windows(tasks, venue_at):
        key = (asset, start, duration)
        if error is not None:
            failures[key] = error
            continue
        if duration == BAR:
            b = parent_bar(asset, start)
            expected = (b.o, b.h, b.l, b.c)
        else:
            block = start // BAR * BAR
            expected = tuple(cache[asset][str(block)][(start - block) // MINUTE])
        try:
            prices, close_delta = validate_window(start, duration, prints, expected)
        except ValueError as error:
            failures[key] = str(error)
            continue
        bucket = "fullBars" if duration == BAR else "ticks"
        cache.setdefault(bucket, {}).setdefault(asset, {})[str(start)] = prices
        metadata = cache.setdefault("tick_metadata", {}).setdefault(asset, {})
        metadata[f"{start}_{duration}"] = {"source": url, **(close_delta or {})}
        count += 1
    return count, failures
