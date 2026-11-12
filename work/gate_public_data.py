import csv
import gzip
import io
import json
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from combined_crypto_portfolio import BAR, WORK, ms


API = "https://api.gateio.ws/api/v4/futures/usdt/"
CACHE = WORK / "gate_replay_market"
ARCHIVE = "https://download.gatedata.org/futures_usdt"
INTERVALS = {"10s": 10, "1m": 60, "15m": BAR // 1000}
MAX_TRADES = 1000


def public_json(endpoint, **parameters):
    url = API + endpoint
    if parameters:
        url += "?" + urlencode(parameters)
    for attempt in range(3):
        try:
            request = Request(url, headers={"X-Gate-Size-Decimal": "1"})
            with urlopen(request, timeout=16) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 2 or (isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504)):
                raise
            sleep(0.5 * (attempt + 1))


def save_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def candles(contract, start, end, interval):
    """Return timestamped (O, H, L, C, volume) rows, end exclusive in epoch seconds."""
    step = INTERVALS[interval]
    if start >= end or start % step or end % step:
        raise ValueError(f"unaligned candle interval {contract} {start} {end} {interval}")
    path = CACHE / f"{contract}_{interval}_{start}_{end}.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    else:
        span = 1900 * step
        rows = []
        for begin in range(start, end, span):
            last = min(begin + span, end)
            batch = public_json("candlesticks", contract=contract, interval=interval,
                                **{"from": begin, "to": last - 1})
            rows.extend([int(r["t"]), *(float(r[k]) for k in ("o", "h", "l", "c", "v"))] for r in batch)
        rows.sort(key=lambda row: row[0])
    if [r[0] for r in rows] != list(range(start, end, step)):
        raise ValueError(f"incomplete Gate candle history: {contract} {interval} {start}:{end} ({len(rows)} rows)")
    if not all(0 < low <= min(o, c) <= max(o, c) <= high and v >= 0 for _, o, high, low, c, v in rows):
        raise ValueError(f"invalid OHLC in Gate candle history: {contract} {interval} {start}:{end}")
    if not path.exists():
        save_json(path, rows)
    return {t: (o, high, low, c, v) for t, o, high, low, c, v in rows}


def _trade_records(contract, start, end):
    params = {"contract": contract, "from": start, "to": end, "limit": MAX_TRADES}
    data = public_json("trades", **params)
    if len(data) == MAX_TRADES:
        # The endpoint supports offset pagination inside the fixed time range.
        # Fetch a few pages concurrently for liquidation bursts.
        def get_page(offset):
            return public_json("trades", **params, offset=offset)

        ids = {row["id"] for row in data}
        with ThreadPoolExecutor(max_workers=6) as pool:
            complete = False
            while not complete:
                first_offset = len(data)
                offsets = range(first_offset, first_offset + 6 * MAX_TRADES, MAX_TRADES)
                for page in pool.map(get_page, offsets):
                    if any(row["id"] in ids for row in page):
                        raise ValueError(f"Gate trade pagination repeated fills: {contract} {start}")
                    ids.update(row["id"] for row in page)
                    data.extend(page)
                    if len(page) < MAX_TRADES:
                        complete = True
                        break
    for row in data:
        if row["contract"] != contract:
            raise ValueError(f"unexpected Gate trade contract: {row['contract']}")
    return [(float(row["create_time_ms"]), int(row["id"]), float(row["price"]), float(row["size"])) for row in data
            if start <= float(row["create_time_ms"]) < end]


def trades(contract, start, end, *, download=True):
    """Read public prints for a bounded window, ordered by timestamp and trade ID."""
    path = CACHE / f"{contract}_decimal_trades_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if not download:
        raise FileNotFoundError(path.name)
    rows = sorted(_trade_records(contract, start, end), key=lambda row: row[:2])
    if len({row[1] for row in rows}) != len(rows):
        raise ValueError(f"duplicate Gate trade IDs: {contract} {start}:{end}")
    save_json(path, rows)
    return rows


def export_15m(asset, start, end, destination):
    rows = candles(f"{asset}_USDT", start, end, "15m")
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
        writer.writerows([t * 1000, *row] for t, row in rows.items())
    return destination


def archived_minutes(asset, year, month, *, start=None, end=None):
    stamp = f"{year}{month:02d}"
    contract = f"{asset}_USDT"
    path = CACHE / f"{contract}_1m_archive_{stamp}.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    else:
        url = f"{ARCHIVE}/candlesticks_1m/{stamp}/{contract}-{stamp}.csv.gz"
        with urlopen(url, timeout=22) as response, gzip.GzipFile(fileobj=response) as archive:
            with io.TextIOWrapper(archive, encoding="utf-8", newline="") as stream:
                rows = [[int(t), float(o), float(h), float(l), float(c), float(v)]
                        for t, v, c, h, l, o in csv.reader(stream) if t]
    first = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())
    last = first + monthrange(year, month)[1] * 86400
    rows.sort(key=lambda row: row[0])
    lower = first if start is None else max(start, first)
    upper = last if end is None else min(end, last)
    selected = [row for row in rows if lower <= row[0] < upper]
    if [r[0] for r in selected] != list(range(lower, upper, 60)):
        raise ValueError(f"incomplete monthly archive {asset} {stamp}: {len(selected)} rows in {lower}:{upper}")
    if not all(0 < low <= min(o, c) <= max(o, c) <= high and v >= 0 for _, o, high, low, c, v in rows):
        raise ValueError(f"invalid archive OHLC {asset} {stamp}")
    if not path.exists():
        save_json(path, rows)
    return {t: (o, h, l, c, v) for t, o, h, l, c, v in selected}
