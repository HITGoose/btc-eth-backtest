import json
from concurrent.futures import ThreadPoolExecutor
from combined_crypto_portfolio import WORK, ms
from fit_squeeze_ladder_bot import LIMIT_OFFSET, SCALES, Settings, ladder_rung, limit_price, stop_price, tick_time
from gate_public_data import API, CACHE, candles, save_json, trades
from replay_formal_bot_trades import FILLS, candle_exit, quote_extremes, signal_checks


OUTPUTS = WORK.parent / "outputs"
POLL_SECONDS = 5
SIGNAL_TO_ORDER_SECONDS = (5, 15)
ENTRY = Settings(96, 5, 0.25, "uncapped")
PATHS = {a: f"{a}USDT_Gate_2026SepNov_replay.csv" for a in SCALES}


def polled_events(minute, phase, prices, previous_close, *, poll_seconds=POLL_SECONDS):
    """Market prints, with periodic quote observations after same-time prints."""
    next_poll = minute + (phase - minute) % poll_seconds if phase is not None else float("inf")
    last = previous_close
    for stamp, price in prices:
        while next_poll < stamp:
            yield next_poll, last, True
            next_poll += poll_seconds
        yield stamp, price, False
        last = price
    while next_poll < minute + 60:
        yield next_poll, last, True
        next_poll += poll_seconds


class GateMinutes:
    def __init__(self, asset, market, *, download_missing=True):
        self.asset = asset
        self.contract = f"{asset}_USDT"
        self.market = market
        self.download_missing = download_missing
        self._tapes = {}
        self.close_discrepancies = {}

    def tape(self, minute):
        if minute in self._tapes:
            return self._tapes[minute]
        rows = trades(self.contract, minute, minute + 60, download=self.download_missing)
        o, h, low, close, volume = self.market[minute]
        prices = [p for _, _, p, _ in rows]
        if not prices:
            if volume or o != h or h != low or low != close:
                raise ValueError(f"Gate prints missing from a nonempty minute {self.contract} {tick_time(minute)}")
        else:
            previous = self.market[minute - 60][3]
            if o not in (prices[0], previous) or (max(o, max(prices)), min(o, min(prices))) != (h, low):
                raise ValueError(f"Gate tape OHLC differs from minute candle {self.contract} {tick_time(minute)}: "
                                 f"{(prices[0], max(prices), min(prices), prices[-1])} vs {(o, h, low, close)}")
            if prices[-1] != close:
                earlier_close = next((stamp for stamp, _, p, _ in reversed(rows) if p == close), None)
                if earlier_close is None or minute + 60 - earlier_close > 0.05:
                    raise ValueError(f"Gate tape does not corroborate close {self.contract} {tick_time(minute)}")
                self.close_discrepancies[minute] = {"minute_local": tick_time(minute), "candle_close": close,
                                                    "candle_close_seen_on_tape_local": tick_time(earlier_close),
                                                    "last_print": prices[-1], "last_print_local": tick_time(rows[-1][0])}
        self._tapes[minute] = rows
        return rows

    def events(self, minute, phase, *, side=None, poll_seconds=POLL_SECONDS):
        last = self.market[minute - 60][3]
        previous_tape = self._tapes.get(minute - 60)
        if previous_tape:
            last = previous_tape[-1][2]
        yield from polled_events(minute, phase, ((stamp, price) for stamp, _, price, _ in self.tape(minute)), last,
                                 poll_seconds=poll_seconds)


def short_ladder(fill, market, *, phase, filled_at, poll_seconds=POLL_SECONDS):
    stop = stop_price(fill.asset, fill.entry, -1, 0)
    initial_stop = stop
    start, observed = int(filled_at), ms(fill.closed) // 1000
    rung = 0
    first_armed = None
    for t in range(start // 60 * 60, (observed // 60 + 2) * 60, 60):
        _, high, low, *_ = market.market[t]
        quote_low = min(low, market.market[t - 60][3]) if phase is not None else low
        if high < stop and ladder_rung(100 * (1 - quote_low / fill.entry), "uncapped") <= rung:
            continue
        for stamp, price, poll in market.events(t, phase, poll_seconds=poll_seconds):
            if stamp < filled_at:
                continue
            if not poll and price >= stop:
                return {"armed_local": first_armed, "trigger_local": tick_time(stamp), "rung": rung,
                        "stop_price": stop, "trigger_print": price, "seconds_after_recorded_close": round(stamp - observed, 3),
                        "initial_stop": initial_stop}
            if poll or phase is None:
                reached = ladder_rung(100 * (1 - price / fill.entry), "uncapped")
                if reached > rung:
                    if first_armed is None:
                        first_armed = tick_time(stamp)
                    rung = reached
                    stop = stop_price(fill.asset, fill.entry, -1, rung)
    return None


def matching_prints(market, second, price, lots):
    data = trades(market.contract, second - 4, second + 5)
    same = [r for r in data if second <= r[0] < second + 1 and r[2] == price]
    return {"matches_in_recorded_second": len(same),
            "first_local": tick_time(same[0][0]) if same else None,
            "same_lot_prints_local": [tick_time(r[0]) for r in same if abs(r[3]) == lots],
            "combined_public_volume_contracts": sum(abs(r[3]) for r in same)}, same


def limit_reference_audit(fill, market, prior_close):
    signal = ms(fill.signal_time) // 1000
    rows = trades(market.contract, signal - 10, signal + 16)
    opened = market.market[signal][0]
    quote_laws = {"floor": lambda p: limit_price(fill.asset, p, -1),
                  "nearest": lambda p: round(p * (1 + LIMIT_OFFSET) * SCALES[fill.asset]) / SCALES[fill.asset]}
    out = {"last_closed_15m_price": prior_close, "next_bar_open": opened}
    for name, to_limit in quote_laws.items():
        matches = [t - signal for t, _, p, _ in rows if to_limit(p) == fill.entry]
        matching_in_window = [t for t in matches if SIGNAL_TO_ORDER_SECONDS[0] <= t <= SIGNAL_TO_ORDER_SECONDS[1]]
        out[name] = {"limit_from_last_closed_15m": to_limit(prior_close), "limit_from_next_open": to_limit(opened),
                     "exact_matches_within_5_to_15s": len(matching_in_window),
                     "first_and_last_match_delay_in_examined_window_seconds": [round(matches[0], 3), round(matches[-1], 3)]
                     if matches else None}
    return out


def gate_quotes(asset):
    rows = [fill for fill in FILLS if fill.asset == asset]
    start = min(ms(fill.signal_time) for fill in rows) // 1000 - 60
    end = max(ms(fill.closed) for fill in rows) // 60_000 * 60 + 180
    return {kind: candles(prefix + asset + "_USDT", start, end, "1m")
            for kind, prefix in (("last", ""), ("mark", "mark_"), ("index", "index_"))}


def audit_fill(fill, conditions, contracts, quotes):
    market = GateMinutes(fill.asset, quotes["last"])
    lots = round(fill.quantity / float(contracts[fill.asset]["quanto_multiplier"]))
    entry_prints, matched = matching_prints(market, ms(fill.opened) // 1000, fill.entry, lots)
    exit_prints, _ = matching_prints(market, ms(fill.closed) // 1000, fill.exit, lots)
    # Public trades corroborate the report's market, time and price. Account attribution is unavailable.
    exact_size = [r[0] for r in matched if abs(r[3]) == lots]
    filled_at = exact_size[0] if exact_size else matched[0][0] if matched else ms(fill.opened) / 1000
    row = {"fill": vars(fill), "signal": conditions, "contracts": lots,
           "entry_same_second_same_price": entry_prints, "exit_same_second_same_price": exit_prints,
           "limit_reference": limit_reference_audit(fill, market, conditions["last_closed_15m_price"]),
           "price_for_next_rung_after_observed": fill.entry * (1 - ((fill.rung or 1) + 2) / 100)}
    row["minute_quote_comparisons"] = {}
    for kind, source in quotes.items():
        series = {t * 1000: row[:4] for t, row in source.items()}
        row["minute_quote_comparisons"][kind] = {
            "extremes_through_reported_close_minute": quote_extremes(fill, series),
            "replay_without_cap": candle_exit(fill, series, favorable_first=False, policy="uncapped"),
        }
    row["tick_replay"] = short_ladder(fill, market, phase=None, filled_at=filled_at)
    row["five_second_quote_exchange_stop"] = {str(phase): short_ladder(fill, market, phase=phase, filled_at=filled_at)
                                               for phase in range(POLL_SECONDS)}
    row["trade_minutes_verified_against_candles"] = len(market._tapes)
    row["tape_close_discrepancies"] = list(market.close_discrepancies.values())
    row["skipped_trade_ids_inside_verified_windows"] = sum(max(0, nxt[1] - prev[1] - 1)
                                                          for tape in market._tapes.values()
                                                          for prev, nxt in zip(tape, tape[1:]))
    print(fill.key, "Gate closes", row["tick_replay"], row["five_second_quote_exchange_stop"], flush=True)
    return row


def main():
    conditions = signal_checks(ENTRY, paths=PATHS)
    contracts = json.loads((CACHE / "contracts.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=5) as pool:
        quotes = dict(zip(SCALES, pool.map(gate_quotes, SCALES)))
        results = list(pool.map(lambda f: audit_fill(f, conditions[f.key], contracts, quotes[f.asset]), FILLS))
    compatible = []
    for phase in range(POLL_SECONDS):
        matches = [row["five_second_quote_exchange_stop"][str(phase)] for row in results]
        if all(match and match["rung"] == (row["fill"]["rung"] or 1) and abs(match["seconds_after_recorded_close"]) <= 2
               for row, match in zip(results, matches)):
            compatible.append(phase)
    report = {
        "live_description_from_slide": {"venue": "Gate", "poll_interval_seconds": POLL_SECONDS,
                                        "submit_after_close_seconds": list(SIGNAL_TO_ORDER_SECONDS),
                                        "exchange_hosted_stops": True, "pending_order_disconnect_timeout_seconds": 60},
        "replay_hypothesis": "Observe last trade each 5s on a fixed phase. Evaluate an active stop on each exchange print. "
                             "The ladder is extended beyond rung 5 as a sensitivity, with no assumed terminal rung.",
        "contract_metadata": contracts, "api_base": API, "signals": "Gate closed 15m candles", "fills": results,
        "five_second_phases_matching_all_observed_rungs_within_two_seconds": compatible,
    }
    save_json(OUTPUTS / "BTC_ETH_Gate_live_v13_audit.json", report)


if __name__ == "__main__":
    main()
