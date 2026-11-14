"""Independent fixed partial-exit experiment. Original work/ files unmodified."""
from pathlib import Path
from dataclasses import asdict
from math import floor
import sys, inspect, json, argparse, traceback, hashlib
import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/attribution_2026'))
import paired_replay as p
r=p.r; d=p.d
OUT=Path(__file__).resolve().parent


class PartialSleeve(p.AuditSleeve):
    def visit(self,price,t,at_open,**kw):
        before=self.position
        super().visit(price,t,at_open,**kw)
        pos=self.position
        if pos is None:return
        if pos is not before:
            pos.initial_quantity=pos.order.qty
            pos.partial_stage=0
            pos.partial_queue=[]
            pos.partial_net=0.
            pos.partial_turnover=0.
            pos.partial_fills=[]
        # Original hard/trailing stop has priority over queued discretionary exits.
        if not pos.partial_queue:return
        for stage in pos.partial_queue:
            step=self.sizing.btc_step if self.asset=='BTC' else r.model.RULES[self.asset][0]
            initial_lots=round(pos.initial_quantity/step)
            remaining_lots=round(pos.order.qty/step)
            lots=min(initial_lots//3,remaining_lots-1)
            if lots<=0:
                self.events.append(dict(event='partial_skipped_quantity_step',stage=stage,time_us=round(self.audit_timestamp*1e6)))
                continue
            qty=lots*step;execution=price*(1-pos.order.side*r.model.SLIP)
            fee=execution*qty*r.model.FEE
            net=pos.order.side*(execution-pos.order.price)*qty-fee
            self.credit(net);self.stats['fees']+=fee;self.stats['partial_exits']+=1
            pos.partial_net+=net;pos.partial_turnover+=execution*qty
            pos.order.qty=(remaining_lots-lots)*step
            event=dict(event='partial_exit',stage=stage,trigger_gain_pct=stage+1,
                       time_us=round(self.audit_timestamp*1e6),trigger_print=float(price),
                       execution_price=float(execution),quantity=qty,remaining_quantity=pos.order.qty,
                       net_usdt=net,side=pos.order.side)
            self.events.append(event);pos.partial_fills.append(event)
        pos.partial_queue=[]

    def update_ladder(self,price):
        super().update_ladder(price)
        pos=self.position
        if pos is None:return
        gain=pos.order.side*(price/pos.order.price-1)*100
        for stage,threshold in ((1,2.),(2,3.)):
            if gain>=threshold-1e-10 and pos.partial_stage<stage:
                pos.partial_stage=stage;pos.partial_queue.append(stage)
                self.events.append(dict(event='partial_exit_requested',stage=stage,
                    time_us=round(self.audit_timestamp*1e6),last_price=float(price),gain_pct=gain))

    def close(self,price,reason,t):
        pos=self.position
        initial=getattr(pos,'initial_quantity',pos.order.qty)
        partial_net=getattr(pos,'partial_net',0.)
        fills=getattr(pos,'partial_fills',[])
        turnover=getattr(pos,'partial_turnover',0.)
        super().close(price,reason,t)
        row=self.journal[-1];remaining=row['quantity']
        row.update(final_exit_quantity=remaining,quantity=initial,
                   notional=initial*row['entry'],final_leg_net=row['net'],
                   partial_net=partial_net,net=row['net']+partial_net,partial_fills=fills,
                   exit_vwap=(turnover+row['exit']*remaining)/initial)


def new_book(asset,partial):
    cls=PartialSleeve if partial else p.AuditSleeve
    book=cls(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
    book.events=[];book.audit_timestamp=None;book.observing_event=False
    book.profile='PARTIAL' if partial else 'CONTROL';book.boundary_probes=[]
    return book


def generator(book):
    # Same original event loop, with minute suspension and pending-exit wakeup.
    source=inspect.getsource(r.seconds.replay_asset)
    patches={
        '    for t in range(start // 1000, end // 1000, 60):\n':
        '    for t in range(start // 1000, end // 1000, 60):\n        book.observing_event = False\n',
        '            for stamp, price, poll in events:\n':
        '            for stamp, price, poll in events:\n                book.audit_timestamp = stamp\n                book.observing_event = True\n',
        '            marks.append(book.cash)\n            continue\n':
        '            marks.append(book.cash)\n            yield t\n            continue\n',
        '        marks.append(book.equity(close))\n':
        '        marks.append(book.equity(close))\n        yield t\n'}
    for old,new in patches.items():
        assert source.count(old)==1
        source=source.replace(old,new)
    original_can_move=r.seconds.has_price_event
    def can_move(b,*args):
        return bool(b.position and getattr(b.position,'partial_queue',[])) or original_can_move(b,*args)
    namespace=dict(r.seconds.__dict__)
    namespace.update(Sleeve=lambda *args,**kw:book,has_price_event=can_move)
    exec(compile(source,'<original loop with pending-partial wakeup and observation>','exec'),namespace)
    return namespace['replay_asset']


def config():
    return dict(experiment='ER_FIXED_PARTIAL_2_3_THIRDS',period='2026-01-01 through 2026-11-01 exclusive, UTC+8',
        entry='Original SMA/EMA20,60,120 with original ER and BASELINE overlay; use_entry_crosses=False',
        first_exit='favorable gain >=2% at 5s phase2 poll: initial quantity/3, rounded down to quantity step',
        second_exit='favorable gain >=3% at 5s phase2 poll: initial quantity/3, rounded down to quantity step',
        execution='first subsequent actual trade print with original adverse0.02% slippage; original stop has priority',
        remainder='original uncapped monotonic trailing ladder; at least one quantity step retained',
        skipped_levels='If first observed gain >=3%, both tranches requested together and executed on next print',
        fee=0.,leverage=3.,each_initial_cash=500.,slippage=.0002,core_squeeze_pct=.25,
        support_resistance='abs(close-level)/close <=0.02 unchanged',
        funding='omitted as original',partial_fill_queue='unverified, full-size market exit proxy',
        original_files_unchanged=True,parameter_search=False,not_counterparty_original_rule=True)


def run(asset):
    folder=OUT/asset;folder.mkdir(parents=True,exist_ok=True)
    p.OUT=folder;d.TEMP=folder/'temporary';d.TEMP.mkdir(exist_ok=True)
    start,end=d.START,d.END;file=d.DATA/f'{asset}_15m.csv'
    leg,signals,contexts,base,policy,pair=p.prepare(asset,file,start,end)
    assert policy.trend_level_distance_pct==2.
    prior=json.loads((ROOT/f'outputs/attribution_2026/{asset}_ER_result.json').read_text())
    native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
    books={name:new_book(asset,name=='PARTIAL') for name in ('CONTROL','PARTIAL')}
    generators={name:generator(b)(asset,leg=leg,signals=signals['ER'],market=market,start=start*1000,end=end*1000,
        starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False) for name,b in books.items()}
    d.dump(folder/'signals.json',signals['ER']);d.dump(folder/'config.json',dict(config(),policy=asdict(policy),ER=pair))
    for t in range(start,end,60):
        for name,g in generators.items():assert next(g)==t
        if t%86400==0:d.dump(folder/'progress.json',dict(time=r.local_s(t),books={k:dict(cash=b.cash,opens=b.stats['long']+b.stats['short']) for k,b in books.items()}))
    for name,g in generators.items():
        try:next(g);raise RuntimeError('Overshot target end')
        except StopIteration as stop:q=stop.value
        assert not q['approximated_minutes']
        b=books[name];mark=float(market.market[end-60][3]);equity=b.equity(mark)
        result=dict(asset=asset,profile=name,starting_equity=500.,ending_equity=equity,return_pct=100*(equity/500-1),
            opens=q['opens'],trades=b.journal,events=b.events,stats=dict(b.stats),state_at_end=p.state(b),
            period_beijing=[r.local_s(start),r.local_s(end)],no_OHLC_fallback=True,config=config(),final_mark_price=mark)
        if b.position and name=='PARTIAL':
            pos=b.position
            result['open_position_partial_state']={k:getattr(pos,k) for k in ('initial_quantity','partial_net','partial_fills','partial_queue','partial_stage')}
        # cash is checked against every realized credit; partial profits counted once.
        realized=sum(row['net'] for row in b.journal)
        if b.position:realized+=getattr(b.position,'partial_net',0.)
        assert abs(b.cash-(500.+realized))<1e-7
        if name=='CONTROL':
            keys=('opened_us','closed_us','side','entry','exit','net','rung','quantity')
            identical=[[v[k] for k in keys] for v in result['trades']]==[[v[k] for k in keys] for v in prior['trades']]
            assert identical and abs(equity-prior['ending_equity'])<1e-8, 'Original ER regression failed'
            result['matches_prior_verified_ER']=True
        d.dump(folder/f'{name}_result.json',result);np.save(folder/f'{name}_equity.npy',q['marks'])
        print(asset,name,'COMPLETE',result['return_pct'],'opens',result['opens'],'partial exits',b.stats['partial_exits'],flush=True)
    d.dump(folder/'status.json',dict(completed=True,official_tick_days=len(cache.sources)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('asset',choices=['BTC','ETH']);args=parser.parse_args()
    try:run(args.asset)
    except Exception as error:
        d.dump(OUT/f'{args.asset}_failure.json',dict(error=repr(error),traceback=traceback.format_exc()))
        raise
