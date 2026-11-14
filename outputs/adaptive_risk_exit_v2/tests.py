"""Independent financial checks of V2 using its real book and event generator.

Synthetic prices prove modeled execution behavior, not archive completeness or
profitability. Only this file and test_results.json are written by this suite.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import importlib.util
import json
import math
import traceback

import numpy as np

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('adaptive_risk_exit_v2_under_test', OUT / 'worker.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
e = w.e
BASE = 1704067200
DURATION = 5400
CHECKS = []


def weak(leg, j, side, ma=True, macd=True):
    (leg.up if side == 1 else leg.down)[j] = 5 if ma else 6
    leg.histogram[j] = -side * .2 if macd else side * .2


def leg_for(side, close=100.):
    first = (BASE - 1800) * 1000
    count = 16
    return SimpleNamespace(
        first=first, up=np.full(count, 6.), down=np.full(count, 6.),
        histogram=np.full(count, side * .2),
        bars={first + j * 900000: SimpleNamespace(c=float(close)) for j in range(count)},
    )


def at(book, second):
    book.audit_timestamp = second
    book.observing_event = True


def opened(asset, side, *, cash=500., ref=100.):
    leg = leg_for(side, ref)
    b = w.new_book(asset, 'DYNAMIC', leg)
    b.cash = cash
    at(b, BASE + 10)
    b.place((BASE + 10) * 1000, ref, side, nearest_tick=True)
    assert b.order is not None
    entry = b.order.price
    at(b, BASE + 10.123)
    b.visit(entry, round((BASE + 10.123) * 1000), True, advance_ladder=False)
    assert b.position is not None
    return b, leg


def requests(book):
    return [x for x in book.events if x['event'] == 'adaptive_v2_request']


def partials(book):
    return [x for x in book.events if x['event'] == 'partial_exit']


def confirm(book, leg, side, t=BASE + 1800, close=None):
    i = (t * 1000 - leg.first) // 900000 - 1
    weak(leg, i - 1, side)
    weak(leg, i, side)
    if close is not None:
        leg.bars[t * 1000 - 900000].c = close
    at(book, t)
    w.check(book, t)


def case(name, fn):
    try:
        detail = fn()
        CHECKS.append(dict(name=name, passed=True, detail=detail))
    except Exception as error:
        CHECKS.append(dict(name=name, passed=False, error=repr(error), traceback=traceback.format_exc()))


def budget_cap_growth(asset, side):
    b, leg = opened(asset, side)
    p = b.position
    initial = p.initial_quantity
    b.credit(500.)
    # Increased realized balance changes the budget, while the cap remains tied
    # to the position's original quantity, not the enlarged account balance.
    close = p.stop + side * 4.
    confirm(b, leg, side, close=close)
    request = requests(b)[-1]
    assert request['realized_balance'] == 1000.
    assert request['budget'] == 30. and request['budget_rate'] == .03
    step = b.sizing.btc_step if asset == 'BTC' else e.r.model.RULES[asset][0]
    expected_cap = math.floor(round(initial / step) * .25 + 1e-12) * step
    assert abs(request['requested_quantity'] - expected_cap) < 1e-10
    assert request['requested_quantity'] <= .25 * initial + 1e-10
    assert not partials(b), 'A request must not execute at the signal close'
    actual = p.order.price + side * .1
    t = BASE + 1800.321
    at(b, t)
    b.visit(actual, round(t * 1000), True, advance_ladder=False)
    fill = partials(b)[-1]
    assert fill['time_us'] == round(t * 1e6)
    assert abs(fill['execution_price'] - actual * (1 - side * .0002)) < 1e-10
    assert abs(fill['quantity'] - expected_cap) < 1e-10
    assert abs(b.position.order.qty + fill['quantity'] - initial) < 1e-10
    assert abs(b.cash - (1000. + fill['net_usdt'])) < 1e-9
    return dict(asset=asset, side=side, initial_quantity=initial, budget=request['budget'], filled_quantity=fill['quantity'])


def two_closed_bars_and_both_indicators(side):
    outcomes = []
    for description, flags in (
        ('only_one_weak_bar', [(2, True, True)]),
        ('MA_weak_MACD_supportive', [(2, True, False), (3, True, False)]),
        ('MACD_weak_MA_aligned', [(2, False, True), (3, False, True)]),
        ('nonconsecutive_weak', [(1, True, True), (3, True, True)]),
    ):
        b, leg = opened('BTC', side)
        for j, ma, macd in flags:
            weak(leg, j, side, ma, macd)
        at(b, BASE + 1800)
        w.check(b, BASE + 1800)
        assert not requests(b), description
        assert not getattr(b.position, 'adaptive_v2_used', False)
        outcomes.append(description)
    b, leg = opened('BTC', side)
    # A weak forming bar is invisible until it closes. At +900 only one weak
    # completed bar exists; +1799 is not a closed15m checkpoint at all.
    weak(leg, 2, side)
    weak(leg, 3, side)
    for t in (BASE + 900, BASE + 1799):
        at(b, t)
        w.check(b, t)
        assert not requests(b)
    at(b, BASE + 1800)
    w.check(b, BASE + 1800)
    assert len(requests(b)) == 1
    # The currently forming next bar cannot affect this closed-bar decision.
    before = len(requests(b))
    weak(leg, 4, side)
    at(b, BASE + 1801)
    w.check(b, BASE + 1801)
    assert len(requests(b)) == before
    return dict(side=side, rejected_conditions=outcomes, confirmed_closed_bars=2)


def no_quantity_keeps_opportunity(side):
    b, leg = opened('BTC', side)
    p = b.position
    # The stop-distance risk fits the budget, so nothing may be requested.
    confirm(b, leg, side, close=p.stop + side * .1)
    assert not requests(b) and not p.partial_queue
    assert not getattr(p, 'adaptive_v2_used', False)
    # Later genuinely larger risk may use the still-available opportunity.
    confirm(b, leg, side, t=BASE + 2700, close=p.stop + side * 4.)
    assert len(requests(b)) == 1 and p.adaptive_v2_used
    return dict(side=side, first_check_no_quantity=True, later_request_accepted=True)


def rounding_zero_keeps_opportunity(side):
    b, leg = opened('ETH', side, cash=10.05, ref=1000.)
    p = b.position
    lots = round(p.initial_quantity / .01)
    assert lots in (2, 3)
    confirm(b, leg, side, close=p.stop + side * 30.)
    assert math.floor(lots * .25) == 0
    assert not requests(b) and not p.partial_queue and not partials(b)
    assert not getattr(p, 'adaptive_v2_used', False)
    return dict(side=side, initial_lots=lots, cap_lots=0, opportunity_preserved=True)


def rebound_never_adds_or_reduces_twice(side):
    b, leg = opened('BTC', side)
    confirm(b, leg, side)
    t = BASE + 1800.125
    at(b, t)
    b.visit(b.position.order.price, round(t * 1000), True, advance_ladder=False)
    remaining = b.position.order.qty
    stop = b.position.stop
    for j, offset in enumerate((2700, 3600, 4500)):
        if j == 0:
            i = (BASE + offset - leg.first // 1000) // 900 - 1
            (leg.up if side == 1 else leg.down)[i] = 6
            leg.histogram[i] = side * .2
            at(b, BASE + offset)
            w.check(b, BASE + offset)
        else:
            confirm(b, leg, side, t=BASE + offset)
        at(b, BASE + offset + .125)
        quote = b.position.order.price * (1 + side * (.015 if j == 0 else -.005))
        b.update_ladder(quote)
        b.visit(quote, round((BASE + offset + .125) * 1000), True, advance_ladder=False)
        assert b.position.order.qty == remaining
        assert side * (b.position.stop - stop) >= -1e-10
    assert len(requests(b)) == len(partials(b)) == 1
    return dict(side=side, requests=1, actual_reductions=1, remaining_quantity=remaining)


def gap_stop_has_priority(side, trailing=False):
    b, leg = opened('BTC', side)
    initial = b.position.initial_quantity
    if trailing:
        at(b, BASE + 1200.002)
        b.update_ladder(b.position.order.price * (1 + side * .035))
        assert b.position.rung > 0
    confirm(b, leg, side, close=b.position.stop + side * 4.)
    assert b.position.partial_queue
    old_stop = b.position.stop
    gap = old_stop - side * 3.
    t = BASE + 1800.111
    at(b, t)
    b.visit(gap, round(t * 1000), True, advance_ladder=False)
    assert b.position is None and not partials(b)
    trade = b.journal[-1]
    assert trade['reason'] == ('ladder_exit' if trailing else 'hard_stop')
    assert abs(trade['final_exit_quantity'] - initial) < 1e-10
    assert abs(trade['exit'] - gap * (1 - side * .0002)) < 1e-10
    assert abs(trade['exit'] - old_stop) > 2.
    return dict(side=side, stop_reason=trade['reason'], queued_reduction_cancelled_by_stop=True, gap_print=gap, execution_price=trade['exit'])


class Native:
    def __init__(self):
        self.first = BASE - 60
        self.end = BASE + DURATION
        # Deliberately wrong/narrow candle bounds: selected events must use raw
        # prints, never infer execution or prune risk from these envelopes.
        self.rows = np.tile([100., 100.001, 99.999, 100., 1.], ((DURATION + 60) // 60, 1))

    def __getitem__(self, second):
        return self.rows[(second - self.first) // 60]


class Cache:
    def __init__(self, rows):
        self.rows = rows

    def load(self, second):
        return self.rows


def synthetic_tape(seed, side):
    rng = np.random.default_rng(seed)
    offset = np.sort(np.r_[np.arange(0., DURATION, .73), 2., 7., 10., 10., 10.001,
                           12., 17., 1800.123, 2700.123, 3600.123, 4500.123, 5100.123])
    prices = 100. + rng.normal(0., .015, len(offset))
    prices[offset == 10.001] = 100. - side * .31
    # Recovery remains below the original 2% ladder activation and cannot
    # justify another adaptive reduction or a quantity increase.
    prices[(offset >= 2700) & (offset < 2900)] = 100. + side * 1.1
    if seed == 3:
        prices[offset == 1800.123] = 100. - side * 5.
    else:
        prices[offset == 5100.123] = 100. - side * 5.
    return np.column_stack((np.r_[BASE - 1., BASE + offset], np.arange(len(offset) + 1), np.r_[100., prices]))


def execute_tape(rows, seed, side, profile, optimized):
    leg = leg_for(side)
    if seed == 2:
        for j in (2, 4, 6):
            weak(leg, j, side)
    else:
        for j in (2, 3, 5, 6):
            weak(leg, j, side)
    book = e.new_book('BTC', profile, leg)
    market = e.Market(Native(), Cache(rows), book, optimized)
    generator = e.generator(book)(
        'BTC', leg=leg, signals={BASE * 1000: side}, market=market,
        start=BASE * 1000, end=(BASE + DURATION) * 1000,
        print_progress=False, poll_seconds=5, poll_phase=2,
        starting_cash=500., leverage=3.,
    )
    for minute in range(BASE, BASE + DURATION, 60):
        assert next(generator) == minute
    try:
        next(generator)
        raise AssertionError('Generator overshot')
    except StopIteration as stop:
        result = stop.value
    assert not result['approximated_minutes']
    assert len(book.journal) == 1 and book.position is None
    return book, result


def full_raw_vs_selected(seed, side, profile):
    rows = synthetic_tape(seed, side)
    full, a = execute_tape(rows, seed, side, profile, False)
    selected, b = execute_tape(rows, seed, side, profile, True)
    assert full.journal == selected.journal
    assert full.events == selected.events
    assert full.cash == selected.cash and a['marks'] == b['marks']
    count = len(partials(full))
    if profile == 'CONTROL':
        assert not requests(full) and count == 0
    elif seed == 2:
        assert not requests(full) and count == 0
    elif seed == 3:
        assert len(requests(full)) == 1 and count == 0
    else:
        assert len(requests(full)) == count == 1
        request, fill = requests(full)[0], partials(full)[0]
        assert request['time_us'] == (BASE + 1800) * 1000000
        assert fill['time_us'] == round((BASE + 1800.123) * 1e6)
        assert fill['quantity'] <= .25 * request['initial_quantity'] + 1e-10
    trade = full.journal[0]
    trade_partials = trade.get('partial_fills', [])
    assert len(trade_partials) <= 1
    assert abs(sum(f['quantity'] for f in trade_partials) + trade.get('final_exit_quantity', trade['quantity']) - trade['quantity']) < 1e-9
    assert abs(full.cash - 500. - sum(t['net'] for t in full.journal)) < 1e-8
    return dict(seed=seed, side=side, profile=profile, duration_seconds=DURATION,
                raw_prints=len(rows), requests=len(requests(full)), reductions=count,
                exact_journal_events_cash_and_minute_equity=True)


def main():
    for side in (1, -1):
        for asset in ('BTC', 'ETH'):
            case(f'cash_budget_and_initial_cap_{asset}_{side}', lambda asset=asset, side=side: budget_cap_growth(asset, side))
        for name, fn in (
            ('two_closed_bars_both_indicators', two_closed_bars_and_both_indicators),
            ('zero_need_keeps_opportunity', no_quantity_keeps_opportunity),
            ('rounding_zero_keeps_opportunity', rounding_zero_keeps_opportunity),
            ('rebound_never_adds_or_reduces_twice', rebound_never_adds_or_reduces_twice),
            ('gap_stop_priority_over_queue', gap_stop_has_priority),
        ):
            case(f'{name}_{side}', lambda fn=fn, side=side: fn(side))
        case(f'gap_trailing_stop_priority_over_queue_{side}', lambda side=side: gap_stop_has_priority(side, trailing=True))
    for seed in range(4):
        for side in (1, -1):
            for profile in ('CONTROL', 'DYNAMIC'):
                case(f'full_raw_vs_selected_seed{seed}_{side}_{profile}',
                     lambda seed=seed, side=side, profile=profile: full_raw_vs_selected(seed, side, profile))
    report = dict(
        synthetic_only=True, historical_data_completeness_validated=False,
        created_utc=datetime.now(timezone.utc).isoformat(),
        uses_real_VariantSleeve_financial_parent=True,
        uses_real_original_generator_and_raw_Market=True,
        configuration=dict(budget_rate=w.BUDGET_RATE, maximum_initial_reduction=w.MAX_REDUCTION,
                           max_reductions_per_position=1, confirmation='two completed15m, each MA weak AND MACD nonsupportive',
                           execution='next actual print; original hard/ladder stop first'),
        total=len(CHECKS), passed=sum(c['passed'] for c in CHECKS),
        failed=sum(not c['passed'] for c in CHECKS), checks=CHECKS,
    )
    (OUT / 'test_results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for c in CHECKS:
        if not c['passed']:
            print('FAIL', c['name'], c['error'])
    print('RESULT', report['passed'], '/', report['total'], 'passed')
    if report['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
