import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from combined_crypto_portfolio import BAR, WORK, read_market
from extended_crypto_portfolio import ETH_START, START, SWITCH, local
from fetch_eth_2021_2024 import fetch_window
from original_ladder_tick_data import MINUTE, refine_ticks


ASOF = json.loads((WORK / "btc_eth_extended_asof.json").read_text())["end_exclusive_ms"]
BTC_EARLY = "BTCUSDT_Binance_2019_2020_continuous.csv"
BTC_LATE = "BTCUSDT_Bybit_2020_2026_continuous.csv"
ETH_LATE = "ETHUSDT_Bybit_2021_2026_continuous.csv"
CACHE = WORK / "our_ladder_verified_minutes.json"
AUDIT = WORK / "our_ladder_refinement_audit.json"
TICK_ERRORS = WORK / "our_ladder_tick_errors.json"
VARIANTS = [(mode, order) for mode in ("ladder", "ladder_72h") for order in ("adverse", "favorable")]


def utc(time):
    return datetime.fromtimestamp(time / 1000, timezone.utc).isoformat()


def launch(file, prefix, start, end, venue, scenario, cash, paired=False, order=None, *, eth_start=ETH_START, entry_policy=None):
    args = ["node", str(WORK / "btc_eth_side_review.mjs"), str(WORK / file), str(WORK / prefix),
            utc(start), utc(end), venue, scenario, repr(cash)]
    if paired:
        args.extend((str(WORK / ETH_LATE), utc(eth_start)))
    if order or entry_policy:
        if not paired:
            args.extend(("", ""))
        args.extend((str(CACHE) if order else "", order or "adverse"))
    if entry_policy:
        args.append(str(entry_policy))
    subprocess.run(args, cwd=WORK.parent, check=True, stdout=subprocess.DEVNULL)
    doc = json.loads((WORK / f"{prefix}_summary.json").read_text())
    assert doc["continuous"], prefix
    return doc["summaries"]


def prefixes(mode, order, tag="our"):
    name = f"{tag}_{mode}_{order}"
    return f"{name}_binance", f"{name}_bybit"


def run_variant(mode, order, end=ASOF, tag="our"):
    early_prefix, late_prefix = prefixes(mode, order, tag)
    early = launch(BTC_EARLY, early_prefix, START, SWITCH, "binance", f"btc_{mode}", 500, order=order)
    seed = early["BTC"]["endingEquity"]
    late = launch(BTC_LATE, late_prefix, SWITCH, end, "bybit", f"btc_eth_shared_{mode}", seed, paired=True, order=order)
    return early, late


def check_baseline():
    early = launch(BTC_EARLY, "our_ladder_control_binance", START, SWITCH, "binance", "btc_rsi_4h_control", 500)
    launch(BTC_LATE, "our_ladder_control_bybit", SWITCH, ASOF, "bybit", "btc_eth_shared_control",
           early["original"]["endingEquity"], paired=True)
    for actual, previous in (("our_ladder_control_binance", "rsi4h_control_binance"),
                             ("our_ladder_control_bybit", "rsi4h_shared_control_bybit")):
        assert (WORK / f"{actual}_trades.csv").read_bytes() == (WORK / f"{previous}_trades.csv").read_bytes(), actual
    print("Original exit journals match the previous replay byte for byte", flush=True)


def markets(end=ASOF):
    return ({"BTC": read_market(WORK / BTC_EARLY, START, SWITCH)},
            {"BTC": read_market(WORK / BTC_LATE, SWITCH, end), "ETH": read_market(WORK / ETH_LATE, ETH_START, end)})


def aggregate(rows):
    return rows[0][0], max(r[1] for r in rows), min(r[2] for r in rows), rows[-1][3]


def venue_at(t):
    return "binance" if t < SWITCH else "bybit"


def refine(end=ASOF, variants=VARIANTS, tag="our", audit_file=AUDIT):
    market_sets = markets(end)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {"BTC": {}, "ETH": {}}

    def parent(asset, t):
        return market_sets[t >= SWITCH][asset][t]

    for asset in ("BTC", "ETH"):
        for t, minutes in cache[asset].items():
            t = int(t)
            if t >= end:
                continue
            b = parent(asset, t)
            assert len(minutes) == 15 and aggregate(minutes) == (b.o, b.h, b.l, b.c), (asset, t)
    CACHE.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    failed = {}
    failed_ticks = {(r["asset"], r["t"], r["duration"]): r["error"]
                    for r in json.loads(TICK_ERRORS.read_text())} if TICK_ERRORS.exists() else {}

    def download(task):
        asset, t = task
        try:
            raw = fetch_window(venue_at(t), t, t + BAR, asset + "USDT", minutes=1)
            minutes = [r[1:5] for r in raw]
            b = parent(asset, t)
            assert aggregate(minutes) == (b.o, b.h, b.l, b.c), (aggregate(minutes), (b.o, b.h, b.l, b.c))
            return asset, t, minutes, None
        except Exception as e:
            return asset, t, None, str(e)

    max_passes = 9
    for pass_index in range(max_passes):
        with ThreadPoolExecutor(max_workers=2) as pool:
            runs = list(pool.map(lambda item: run_variant(*item, end, tag), variants))
        candidates, minute = set(), set()
        for segments in runs:
            for doc in segments:
                for asset, summary in doc.items():
                    audit = summary["ladderAudit"]
                    candidates.update((asset, t) for t in audit["uncertain15m"])
                    minute.update((asset, t) for t in audit["uncertain1m"])
        pending = sorted(candidates - failed.keys())
        print(f"Pass {pass_index + 1}: {len(candidates)} uncertain 15m bars and {len(minute)} uncertain 1m bars", flush=True)
        if pass_index == max_passes - 1:
            break
        if pending:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for asset, t, rows, error in pool.map(download, pending):
                    if error is None:
                        cache[asset][str(t)] = rows
                    else:
                        failed[asset, t] = error
        else:
            tasks = {(a, t, span) for span, windows in ((BAR, candidates), (MINUTE, minute)) for a, t in windows}
            tasks = sorted(tasks - failed_ticks.keys())
            if not tasks:
                break
            added, failures = refine_ticks(cache, tasks, parent, venue_at)
            failed_ticks.update(failures)
            TICK_ERRORS.write_text(json.dumps([{"asset": a, "t": t, "duration": d, "error": err}
                                               for (a, t, d), err in failed_ticks.items()], indent=2), encoding="utf-8")
            print(f"Reconciled {added}/{len(tasks)} intervals against official trade archives", flush=True)
            if not added:
                break
        CACHE.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")

    audit = {"verified_1m_parent_bars": {a: sum(int(t) < end for t in cache[a]) for a in ("BTC", "ETH")},
             "verified_public_trade_windows": {k: {a: sum(int(t) < end for t in rows)
                                                    for a, rows in cache.get(k, {}).items()} for k in ("ticks", "fullBars")},
             "public_trade_sources": {a: {key: meta for key, meta in rows.items() if int(key.split("_")[0]) < end}
                                      for a, rows in cache.get("tick_metadata", {}).items()},
             "passes": pass_index + 1, "unresolved_15m": [{"asset": a, "time_local": local(t)} for a, t in sorted(candidates)],
             "unresolved_1m": [{"asset": a, "time_local": local(t)} for a, t in sorted(minute)],
             "failed_1m_downloads": [{"asset": a, "time_local": local(t), "error": err} for (a, t), err in failed.items()],
             "failed_trade_downloads": [{"asset": a, "time_local": local(t), "duration_ms": d, "error": err}
                                        for (a, t, d), err in failed_ticks.items()]}
    audit_file.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k != "public_trade_sources"}), flush=True)
    return audit


if __name__ == "__main__":
    check_baseline()
    refine()
