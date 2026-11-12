from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from audit_gate_october import END, OCTOBER, SEPTEMBER, archived_months
from combined_crypto_portfolio import BAR, WORK
from extended_crypto_portfolio import local
from fit_squeeze_ladder_bot import ORDER_LIFETIME, Sizing, Sleeve, build, ladder_rung, tick_time
from gate_public_data import save_json
from gate_v13_targets import OCTOBER_BARS
from replay_gate_bot import ENTRY, PATHS, POLL_SECONDS, GateMinutes


ORDER_DELAY_SECONDS = 10
POLL_PHASE_SECONDS = 2


def expiry(book):
    return float("inf") if book.order is None else (book.order.time + ORDER_LIFETIME) / 1000


def expire(book, second):
    if book.order and second >= expiry(book):
        book.order = None
        book.stats["expired"] += 1


def has_price_event(book, high, low, previous_close):
    if position := book.position:
        order = position.order
        best, worst = (max(high, previous_close), low) if order.side == 1 else (min(low, previous_close), high)
        return (order.side * (worst - position.stop) <= 0 or
                ladder_rung(order.side * (best / order.price - 1) * 100, book.exit_policy) > position.rung)
    if order := book.order:
        price = low if order.side == 1 else high
        return order.side * (price - order.price) <= 0
    return False


def replay_asset(asset, *, leg=None, signals=None, market=None, print_progress=True, start=OCTOBER, end=END,
                 poll_seconds=POLL_SECONDS, poll_phase=POLL_PHASE_SECONDS, starting_cash=500.0, size_multipliers=None,
                 leverage=3.0):
    if leg is None:
        leg = build(PATHS[asset], SEPTEMBER, END)
    if signals is None:
        signals = leg.signals(ENTRY)
    if market is None:
        market = GateMinutes(asset, archived_months(asset))
    book = Sleeve(asset, ENTRY.exit_policy, cash=starting_cash, sizing=Sizing(leverage, 0.0001, False), journal=[])
    size_multipliers = {} if size_multipliers is None else size_multipliers
    marks = []
    approximated_minutes = {}
    missing_minutes = []
    verified_minutes = set()
    stop_at_level = getattr(market, "modeled_stop_at_level", None)

    for t in range(start // 1000, end // 1000, 60):
        expire(book, t)
        side = signals.get(t * 1000)
        if not side and not book.order and not book.position:
            marks.append(book.cash)
            continue
        o, high, low, close, _ = market.market[t]
        submit_at = t + ORDER_DELAY_SECONDS
        prior_close = market.market[t - 60][3]

        def submit():
            expire(book, submit_at)
            if side and not book.order and not book.position:
                ref = leg.bars[t * 1000 - BAR].c
                book.place(int(submit_at * 1000), ref, side, nearest_tick=True,
                           size_multiplier=size_multipliers.get(t * 1000, 1.0))

        can_move = has_price_event(book, high, low, prior_close)
        pending_submission = bool(side and can_move)
        if not can_move and not book.position and expiry(book) <= submit_at:
            expire(book, submit_at)
        if not can_move and not book.position and not book.order and side:
            submit()
            can_move = has_price_event(book, high, low, prior_close)
        if can_move:
            use_tape = True
            order = book.order or book.position.order
            try:
                events = list(market.events(t, poll_phase, side=order.side, poll_seconds=poll_seconds))
                verified_minutes.add(t)
            except (ValueError, OSError) as error:
                use_tape = False
                approximated_minutes[tick_time(t)] = str(error)
                if isinstance(error, FileNotFoundError):
                    missing_minutes.append(t)
                adverse, favorable = (low, high) if order.side == 1 else (high, low)
                events = zip((t, t + 20, t + 40, t + 59.999), (o, adverse, favorable, close), (False,) * 4)
            for stamp, price, poll in events:
                if pending_submission and stamp > submit_at:
                    submit()
                    pending_submission = False
                expire(book, stamp)
                if poll:
                    book.update_ladder(price)
                elif not book.order or stamp * 1000 >= book.order.time:
                    intrabar_stop = use_tape and stop_at_level is not None and stop_at_level(stamp)
                    book.visit(price, round(stamp * 1000), True, advance_ladder=not use_tape, stop_at_level=intrabar_stop)
                if not pending_submission and not book.order and not book.position:
                    break
            if pending_submission:
                submit()
        marks.append(book.equity(close))

    fills = book.stats["long"] + book.stats["short"]
    assert fills == len(book.journal) + bool(book.position)
    assert book.stats["submitted"] == fills + book.stats["expired"] + bool(book.order)
    if print_progress:
        print(asset, "open", fills, "closed", len(book.journal), "verified trade minutes", len(verified_minutes),
              "approximations", len(approximated_minutes), flush=True)
    return {"opens": fills, "closed": book.journal, "marks": marks, "stats": dict(book.stats),
            "window_mark_price": float(market.market[end // 1000 - 60][3]),
            "open_position_at_month_end": vars(book.position.order) if book.position else None,
            **({"open_position_time_ms": book.position.opened} if book.position else {}),
            "verified_minutes_with_trade_prints": len(verified_minutes), "approximated_minutes": approximated_minutes,
            "tape_close_discrepancies": [market.close_discrepancies[t] for t in sorted(verified_minutes & market.close_discrepancies.keys())],
            **({"missing_trade_minutes": missing_minutes} if missing_minutes else {})}


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        symbols = ("BTC", "ETH")
        results = dict(zip(symbols, pool.map(replay_asset, symbols)))
    marks = [sum(equity) for equity in zip(*(r.pop("marks") for r in results.values()))]
    drawdown, peak = 0.0, 1000.0
    for equity in marks:
        peak = max(peak, equity)
        drawdown = max(drawdown, 100 * (1 - equity / peak))
    rows = [{"asset": a, **r} for a, book in results.items() for r in book["closed"]]
    rows.sort(key=lambda r: (r["closed_ms"], r["opened_ms"]))
    report = {
        "window_utc8": [local(OCTOBER), local(END)],
        "target": {"opens": dict(Counter(a for a, *_ in OCTOBER_BARS)), "wins": 13, "losses": 6,
                   "return_pct": 14.9, "mdd_pct": 10.9, "ordered_bars": OCTOBER_BARS},
        "inputs": {"starting_usdt": 1000, "each_sleeve_start_usdt": 500, "effective_leverage": 3,
                   "signals": ENTRY.key, "limit_reference": "last closed Gate 15m close plus/minus 0.20%, nearest price tick",
                   "submission_delay_s_assumption": ORDER_DELAY_SECONDS, "last_price_poll_every_s": 5,
                   "clock_phase_s_assumption": POLL_PHASE_SECONDS, "stop_trigger": "each last-price print",
                   "mark": "minute last trade", "funding": "omitted", "fees_pct_per_fill": 0.05, "exit_slippage_pct": 0.02},
        "month": {"opens": {a: r["opens"] for a, r in results.items()}, "closes": dict(Counter(r["asset"] for r in rows)),
                  "wins": sum(r["net"] > 0 for r in rows), "losses": sum(r["net"] < 0 for r in rows),
                  "return_pct": 100 * (marks[-1] / 1000 - 1), "mdd_pct_at_minute_closes": drawdown,
                  "ending_usdt": marks[-1], "closing_sequence": [{"asset": r["asset"], "rung": r["rung"],
                                                                   "reason": r["reason"]} for r in rows]},
        "assets": results,
    }
    save_json(WORK.parent / "outputs" / "BTC_ETH_Gate_v13_October_2026_seconds.json", report)
    print("October", report["month"], flush=True)


if __name__ == "__main__":
    main()
