import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

import requests

WORK = Path(__file__).resolve().parent
BAR = 900_000
PAGE = 1000


def ms(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def fetch_window(venue, first, end, symbol="ETHUSDT", *, minutes=15):
    step = minutes * 60_000
    if venue == "bybit":
        url = "https://api.bybit.com/v5/market/kline"
        params = dict(category="linear", symbol=symbol, interval=minutes, start=first, end=end-1, limit=PAGE)
    else:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = dict(symbol=symbol, interval=f"{minutes}m", startTime=first, endTime=end-1, limit=PAGE)
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, timeout=14)
            r.raise_for_status()
            doc = r.json()
            if venue == "bybit":
                assert doc["retCode"] == 0, doc
                result = doc["result"]
                assert (result["category"], result["symbol"]) == ("linear", symbol)
                records = list(reversed(result["list"]))
            else:
                records = doc
            rows = [(int(x[0]), *map(float, x[1:6])) for x in records]
            assert [x[0] for x in rows] == list(range(first, end, step)), (venue, first, end, len(rows))
            assert all(0 < l <= min(o, c) <= max(o, c) <= h and v >= 0 for _, o, h, l, c, v in rows)
            return rows
        except (requests.RequestException, ValueError, AssertionError) as error:
            if attempt == 4:
                raise
            sleep(0.25 * (2 ** attempt))


def download(venue, first, end, name, symbol="ETHUSDT"):
    def get(t):
        return fetch_window(venue, t, min(end, t+PAGE*BAR), symbol)

    rows = []
    with ThreadPoolExecutor(max_workers=7) as pool:
        for batch in pool.map(get, range(first, end, PAGE*BAR)):
            rows.extend(batch)
    assert len(rows) == (end-first)//BAR
    print(venue, len(rows), datetime.fromtimestamp(first/1000, tz=timezone.utc), datetime.fromtimestamp((end-BAR)/1000, tz=timezone.utc), flush=True)
    with (WORK / name).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
        writer.writerows(rows)


if __name__ == "__main__":
    from sys import argv

    if argv[1] == "bybit":
        download("bybit", ms("2021-03-15T00:00:00Z"), ms("2024-12-31T16:00:00Z"), "ETHUSDT_Bybit_2021_2024_verified.csv")
    elif argv[1] == "binance":
        download("binance", ms("2020-12-16T16:00:00Z"), ms("2021-12-31T16:00:00Z"), "ETHUSDT_Binance_2021_verified.csv")
