"""Independent bounded adaptive exit, V2. Never edits original work/ sources."""
from pathlib import Path
import argparse
import json
import math
import sys
import traceback

ROOT = Path('/workspace/btc-eth-backtest')
sys.path.insert(0, str(ROOT / 'outputs/binance_perpetual_raw_execution'))
import worker as original_worker
import engine as e

OUT = Path(__file__).resolve().parent
BUDGET_RATE = .03
MAX_REDUCTION = .25
REASON = 'two closed15m both weak; 3pct realized balance reference budget; at most one reduction capped at25pct initial'


class BoundedAdaptive(e.x.v.VariantSleeve):
    def update_ladder(self, price):
        # Preserve the original full hard/ladder stop; no automatic profit tranche.
        e.p.AuditSleeve.update_ladder(self, price)

    def visit(self, *args, **kwargs):
        start = len(self.events)
        super().visit(*args, **kwargs)
        for event in self.events[start:]:
            if event.get('event') == 'partial_exit':
                event.update(trigger_gain_pct=None, trigger_reason=REASON)


def check(book, t):
    pos = book.position
    if book.profile != 'DYNAMIC' or pos is None or t % 900:
        return
    if getattr(pos, 'adaptive_v2_used', False) or pos.partial_queue:
        return
    i = (t * 1000 - book.leg.first) // 900000 - 1
    if i < 1:
        return
    side = pos.order.side

    def weak(j):
        aligned = book.leg.up[j] if side == 1 else book.leg.down[j]
        return aligned != 6 and side * book.leg.histogram[j] <= 0

    if not (weak(i) and weak(i - 1)):
        return
    price = book.leg.bars[t * 1000 - 900000].c
    distance = side * (price - pos.stop)
    if distance <= 0:
        return  # A live stop hit has priority at the next real print.
    step = book.sizing.btc_step if book.asset == 'BTC' else e.r.model.RULES[book.asset][0]
    initial_lots = round(pos.initial_quantity / step)
    remaining_lots = round(pos.order.qty / step)
    budget = max(0., book.cash) * BUDGET_RATE
    target_lots = math.floor(budget / distance / step + 1e-12)
    cap_lots = math.floor(initial_lots * MAX_REDUCTION + 1e-12)
    lots = min(max(0, remaining_lots - target_lots), cap_lots, remaining_lots - 1)
    if lots <= 0:
        return  # No actual request: the single opportunity remains available.
    # VariantSleeve fixes a requested quantity in initial-lot fractions. The tiny
    # epsilon avoids an erroneous floor from binary float division, < one lot.
    book.tranches.append((0., (lots + .000001) / initial_lots))
    stage = len(book.tranches)
    pos.partial_queue.append(stage)
    pos.partial_stage = stage
    pos.adaptive_v2_used = True
    book.events.append(dict(
        event='adaptive_v2_request', stage=stage, time_us=t * 1000000,
        realized_balance=book.cash, budget_rate=BUDGET_RATE, budget=budget,
        known_close=price, stop=pos.stop, price_stop_distance=distance,
        target_quantity=target_lots * step, requested_quantity=lots * step,
        initial_quantity=pos.initial_quantity,
        cap_quantity=cap_lots * step,
        estimated_remaining_risk=(remaining_lots - lots) * step * distance,
        budget_is_reference_not_guarantee=True,
    ))


original_new_book = e.new_book


def new_book(asset, profile, leg):
    if profile == 'CONTROL':
        return original_new_book(asset, profile, leg)
    book = BoundedAdaptive(asset, e.r.ENTRY.exit_policy, cash=500.,
                          sizing=e.r.model.Sizing(3., .0001, False), journal=[])
    book.tranches = []
    book.events = []
    book.audit_timestamp = None
    book.observing_event = False
    book.profile = 'DYNAMIC'
    book.boundary_probes = []
    book.leg = leg
    return book


e.new_book = new_book
e.x.check_trend = check
original_worker.OUT = OUT


def run(year, asset):
    original_worker.run(year, asset)
    folder = OUT / str(year) / asset
    path = folder / 'config.json'
    config = json.loads(path.read_text())
    config.update(
        experiment='ADAPTIVE_V2_BALANCE3_CAP25_ONCE', dynamic=REASON,
        risk_budget_rate=BUDGET_RATE,
        risk_budget_basis='current per-asset realized balance, excludes unrealized PnL',
        maximum_initial_quantity_reduction=MAX_REDUCTION,
        max_requests_per_position=1,
        no_quantity_request_does_not_consume_opportunity=True,
        risk_budget_is_reference_not_guarantee=True,
        risk_estimation_price='latest completed15m close',
        confirmation='two consecutive completed15m, each fails six-line alignment AND MACD support',
        profit_prerequisite=False, reentry_on_recovery=False,
        minimum_remainder='one original quantity step', never_relax_stop=True,
        parameter_search=False,
    )
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    path = folder / 'DYNAMIC_result.json'
    result = json.loads(path.read_text())
    result['experiment'] = config['experiment']
    for trade in result['trades']:
        assert len(trade['partial_fills']) <= 1
        assert sum(v['quantity'] for v in trade['partial_fills']) <= MAX_REDUCTION * trade['quantity'] + 1e-9
    path.write_text(json.dumps(result, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('year', type=int, choices=[2024, 2025])
    parser.add_argument('asset', choices=['BTC', 'ETH'])
    args = parser.parse_args()
    try:
        run(args.year, args.asset)
    except Exception as error:
        folder = OUT / str(args.year) / args.asset
        folder.mkdir(parents=True, exist_ok=True)
        e.d.dump(folder / 'failure.json', dict(completed=False, error=repr(error), traceback=traceback.format_exc()))
        raise
