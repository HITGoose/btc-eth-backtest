"""Paired minute traversal of the unchanged executor, for trade attribution.

Suspension points only are inserted after each completed minute. Both books
therefore consume the very same real daily tape without redownloading it.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from math import floor
from pathlib import Path
from urllib.error import HTTPError
import csv
import inspect
import json
import sys
import traceback

import numpy as np

import binance_inputs as d
ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/retry_nov9_nov12'))
import replay_comparison as r
from replay_gate_bot import polled_events

OUT=Path(__file__).resolve().parent
PRIOR={'BTC':{'ER':11.799076504400885,'MA':27.908509281201745},
       'ETH':{'ER':154.20134612800095,'MA':-3.568633923999387}}


def csv_out(path,rows,fields=None):
    if fields is None:fields=list(dict.fromkeys(k for x in rows for k in x))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def state(book):
    p=book.position;o=book.order
    return dict(cash=book.cash,position=asdict(p) if p else None,
                position_opened_us=getattr(p,'opened_us',None) if p else None,
                pending_order=asdict(o) if o else None)


class AuditSleeve(r.ObservedSleeve):
    def place(self,t,ref,side,**kw):
        super().place(t,ref,side,**kw)
        if self.order:
            self.events[-1]['effective_submission_us']=round(self.audit_timestamp*1e6) if self.observing_event else t*1000

    def close(self,price,reason,t):
        p=self.position
        details=dict(quantity=p.order.qty,stop_before_exit=p.stop,signal_close_ms=p.order.time-10000)
        super().close(price,reason,t);self.journal[-1].update(details)


def new_book(asset,label):
    book=AuditSleeve(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
    book.events=[];book.audit_timestamp=None;book.observing_event=False;book.profile=label;book.boundary_probes=[]
    return book


def deadline_probe(book,asset,side,ref,stamp,price,poll):
    if poll or book.position:return
    if book.order and book.order.time+r.model.ORDER_LIFETIME>stamp*1000:return
    limit=r.model.limit_price(asset,ref,side,nearest_tick=True)
    step,minimum=r.model.RULES[asset]
    if asset=='BTC':step=book.sizing.btc_step
    qty=floor((max(0.,3*book.cash)/limit+1e-12)/step)*step
    if qty*limit>=minimum and side*(price-limit)<=0:
        book.boundary_probes.append(dict(profile=book.profile,asset=asset,time_us=round(stamp*1e6),
              side=side,potential_limit=limit,actual_price=price,
              observation='Original pending submit skips exact +10s print; economic impact not assumed'))


def paired_generator(book):
    source=inspect.getsource(r.seconds.replay_asset)
    before='    for t in range(start // 1000, end // 1000, 60):\n'
    loop='            for stamp, price, poll in events:\n'
    flat='            marks.append(book.cash)\n            continue\n'
    mark='        marks.append(book.equity(close))\n'
    for needle in (before,loop,flat,mark):
        if source.count(needle)!=1:raise RuntimeError('Unexpected original event-loop source')
    source=source.replace(before,before+'        book.observing_event = False\n')
    source=source.replace(loop,loop+'                book.audit_timestamp = stamp\n                book.observing_event = True\n'
       +'                if pending_submission and stamp == submit_at:\n'
       +'                    deadline_probe(book, asset, side, leg.bars[t * 1000 - BAR].c, stamp, price, poll)\n')
    source=source.replace(flat,'            marks.append(book.cash)\n            yield t\n            continue\n')
    source=source.replace(mark,mark+'        yield t\n')
    namespace=dict(r.seconds.__dict__);namespace.update(Sleeve=lambda *a,**kw:book,deadline_probe=deadline_probe)
    exec(compile(source,'<original executor: observation and minute-yield hooks only>','exec'),namespace)
    return namespace['replay_asset']


class Canonical:
    def __init__(self,asset):
        self.rows=np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r');self.first=d.FIRST1;self.end=d.END

    def __getitem__(self,minute):
        i=(minute-self.first)//60
        if i<0 or i>=len(self.rows):raise RuntimeError('Native minute outside available history')
        return self.rows[i]


class DayCache:
    def __init__(self,asset,canonical):
        self.asset=asset;self.canonical=canonical;self.day=None;self.rows=None;self.sources={}
        self.temp=d.TEMP/asset;self.temp.mkdir(exist_ok=True)

    def load(self,minute):
        day=datetime.fromtimestamp(minute,timezone.utc).strftime('%Y-%m-%d')
        if day==self.day:return self.rows
        symbol=self.asset+'USDT';rejections=[]
        for kind,column in (('aggTrades',5),('trades',4)):
            file=self.temp/f'{symbol}-{kind}-{day}.zip'
            url=f'{d.BASE}/daily/{kind}/{symbol}/{symbol}-{kind}-{day}.zip'
            try:
                try:meta=d.acquire(url,file)
                except HTTPError as error:
                    if error.code==404 and kind=='aggTrades':continue
                    raise
                raw=d.read_zip(file,[0,1,column]);scale=1e6 if raw[0,2]>1e14 else 1000
                rows=np.column_stack((raw[:,2]/scale,raw[:,0],raw[:,1]))
                if not np.all(np.isfinite(rows)) or np.any(rows[:,2]<=0):raise RuntimeError('Invalid tick fields')
                if np.any(np.diff(rows[:,0])<0):rows=rows[np.argsort(rows[:,0],kind='stable')]
                lower=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
                if rows[0,0]<lower or rows[-1,0]>=lower+86400:raise RuntimeError('Tick date/unit mismatch')
                used=rows[(rows[:,0]>=self.canonical.first)&(rows[:,0]<self.canonical.end)]
                index=((used[:,0]//60*60-self.canonical.first)//60).astype(np.int64)
                lows=self.canonical.rows[index,2];highs=self.canonical.rows[index,1]
                bad=(used[:,2]<lows-1e-8)|(used[:,2]>highs+1e-8)
                if np.any(bad):
                    i=int(np.flatnonzero(bad)[0]);error=dict(asset=self.asset,date=day,source=meta,kind=kind,
                          inconsistent_records=int(bad.sum()),sample=used[max(0,i-2):i+4].tolist(),
                          native_low=float(lows[i]),native_high=float(highs[i]))
                    d.dump(OUT/f'{self.asset}_{day}_{kind}_rejected.json',error);rejections.append(error)
                    if kind=='aggTrades':continue
                    raise RuntimeError('Both official trade products conflict with native candles; no prices altered')
                meta.update(asset=self.asset,date=day,kind=kind,rows=len(rows),
                            price_consistency_pass=True,min_price=float(rows[:,2].min()),max_price=float(rows[:,2].max()),
                            whole_raw_day_replacement=bool(rejections))
                self.sources[day]=meta;self.day=day;self.rows=rows
                d.dump(OUT/f'{self.asset}_tick_sources.json',self.sources)
                if len(self.sources)%20==0:print(self.asset,'VALIDATED_DAYS',len(self.sources),'LATEST',day,flush=True)
                return rows
            finally:
                if file.exists():file.unlink()
        raise RuntimeError('No complete valid actual tick product for '+day)


class ActualMarket:
    def __init__(self,native,cache):
        self.market=self;self.native=native;self.cache=cache;self.close_discrepancies={}

    def __getitem__(self,minute):return self.native[minute]

    def events(self,minute,phase,*,side=None,poll_seconds=5):
        rows=self.cache.load(minute);left,right=np.searchsorted(rows[:,0],(minute,minute+60))
        previous=float(rows[left-1,2]) if left else float(self[minute-60][3])
        yield from polled_events(minute,phase,((float(t),float(p)) for t,_,p in rows[left:right]),previous,poll_seconds=poll_seconds)


def reason(side,context,policy):
    if not side:return 'CORE_SIGNAL_ABSENT'
    gate=context.get('gate_confirmation')
    if gate is None:return 'CORE_CONTEXT_ABSENT'
    if gate['aligned_lines']<6:return 'SIX_LINE_ALIGNMENT_FAILED'
    state=context['regime']
    if state=='transition':return 'ER_TRANSITION_PAUSED' if policy.pause_transition else 'ELIGIBLE'
    if state=='range':
        if gate['minimum_bandwidth_pct']>policy.range_squeeze_pct:return 'RANGE_DENSITY_FAILED'
        if policy.range_entry_bandwidth_pct is not None and gate['entry_bandwidth_pct']>policy.range_entry_bandwidth_pct:return 'RANGE_CURRENT_WIDTH_OVER_0_50'
        return 'ELIGIBLE'
    if r.regime.DIRECTIONS.get(state)!=side:return 'ER_DIRECTION_OPPOSES_ENTRY'
    if not gate['short_term_alignment']:return 'TREND_SMA5_MACD_CONFIRM_FAILED'
    distance=gate['distance_to_confirmed_hourly_level_pct']
    if not ((distance is not None and distance<=policy.trend_level_distance_pct) or gate['directional_volume_breakout'] or gate['confirmed_retest']):
        return 'TREND_LEVEL_VOLUME_RETEST_FAILED'
    return 'ELIGIBLE'


def prepare(asset,file,start,end):
    prior=json.loads(r.selected.FAST_WINDOW_REPORT.read_text());policy=r.RegimeOverlay(**prior['policy'])
    pair=tuple(tuple(v) for v in prior['cases'][r.selected.MODE]['er_windows_and_thresholds'])
    leg=r.model.build(file,(start-30*86400)*1000,end*1000)
    candidates={};contexts={};base=None
    for name,fn in (('ER',r.regime.market_schedules),('MA',r.ma_schedules)):
        schedules,context=fn(asset,leg,price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
        candidates[name]=r.stacked_signals(schedules['baseline'],context,policy);contexts[name]=context
        if base is None:base=schedules['baseline']
        else:assert base==schedules['baseline']
    return leg,candidates,contexts,base,policy,pair


def execute(asset,file,market,start,end,save=True):
    leg,signals,contexts,base,policy,pair=prepare(asset,file,start,end)
    books={name:new_book(asset,name) for name in ('ER','MA')}
    gen={name:paired_generator(book)(asset,leg=leg,signals=signals[name],market=market,
             start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
         for name,book in books.items()}
    audit=[]
    for t in range(start,end,60):
        ms=t*1000
        if signals['ER'].get(ms) or signals['MA'].get(ms):
            row=dict(asset=asset,signal_ms=ms,signal_beijing=r.local_s(t),base_side=base.get(ms,0),
                     ER_side=signals['ER'].get(ms,0),MA_side=signals['MA'].get(ms,0),
                     ER_regime=contexts['ER'][ms]['regime'],MA_regime=contexts['MA'][ms]['regime'],
                     ER_reject_reason=reason(base.get(ms,0),contexts['ER'][ms],policy),
                     MA_reject_reason=reason(base.get(ms,0),contexts['MA'][ms],policy),
                     ER_book_before=json.dumps(state(books['ER'])),MA_book_before=json.dumps(state(books['MA'])))
            audit.append(row)
        for name,g in gen.items():
            step=next(g)
            if step!=t:raise RuntimeError('Paired executor lost its common clock')
        if save and t%86400==0:
            d.dump(OUT/f'{asset}_progress.json',dict(time_beijing=r.local_s(t),
                     states={name:dict(opens=b.stats['long']+b.stats['short'],closed=len(b.journal),cash=b.cash) for name,b in books.items()}))
    results={}
    for name,g in gen.items():
        try:next(g);raise RuntimeError('Executor did not stop at target end')
        except StopIteration as stop:q=stop.value
        if q['approximated_minutes']:raise RuntimeError('OHLC fallback is forbidden')
        book=books[name];mark=market.market[end-60][3]
        result=dict(asset=asset,profile=name,period_beijing=[r.local_s(start),r.local_s(end)],
                    starting_equity=500.,ending_equity=book.equity(mark),return_pct=100*(book.equity(mark)/500-1),
                    trades=book.journal,events=book.events,stats=dict(book.stats),state_at_end=state(book),
                    final_mark_price=float(mark),boundary_probes=book.boundary_probes,
                    no_OHLC_fallback=True,fee=0.,leverage=3.,slippage=.0002,
                    policy=asdict(policy),original_ER=pair,source='Binance official USDT-M archives',
                    instrumentation='Original executor, observation hooks and paired minute suspension only')
        results[name]=result
        if save:
            d.dump(OUT/f'{asset}_{name}_result.json',result);np.save(OUT/f'{asset}_{name}_equity.npy',q['marks'])
            print(asset,name,'COMPLETE',result['return_pct'],book.stats,flush=True)
    if save:
        csv_out(OUT/f'{asset}_signal_audit.csv',audit)
        d.dump(OUT/f'{asset}_regression.json',{name:dict(previous_return_pct=PRIOR[asset][name],
                    rerun_return_pct=results[name]['return_pct'],difference_pp=results[name]['return_pct']-PRIOR[asset][name],
                    matches_within_1e_6=abs(results[name]['return_pct']-PRIOR[asset][name])<1e-6) for name in results})
    return results


def smoke():
    checks=[]
    for asset in ('BTC','ETH'):
        # Read only cached real Gate prints from the recent successful replay.
        r.public.CACHE=ROOT/'outputs/retry_nov9_nov12/data'
        native=r.complete_candles(asset,r.START-60,r.END,'1m')
        market=r.StrictMarket(asset,native)
        results=execute(asset,ROOT/f'outputs/retry_nov9_nov12/data/{asset}_15m.csv',market,r.START,r.END,save=False)
        for name,label in (('ER','ER_9_12'),('MA','MA_9_12')):
            old=json.loads((ROOT/f'outputs/retry_nov9_nov12/{label}_{asset}_result.json').read_text())
            new=results[name]
            ok=abs(new['ending_equity']-old['ending_equity'])<1e-8
            keys=('opened_us','closed_us','side','entry','exit','net','rung')
            ok=ok and [[t[k] for k in keys] for t in new['trades']]==[[t[k] for k in keys] for t in old['trades']]
            checks.append(dict(asset=asset,profile=name,paired_executor_matches_verified_recent_replay=ok,
                               expected_equity=old['ending_equity'],actual_equity=new['ending_equity']))
    d.dump(OUT/'paired_executor_regression.json',checks)
    assert all(x['paired_executor_matches_verified_recent_replay'] for x in checks)
    print('PAIRED_EXECUTOR_REAL_TAPE_REGRESSION_PASS',checks,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--asset',choices=['BTC','ETH']);parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    if args.smoke:return smoke()
    info=json.loads((OUT/'prepared_inputs.json').read_text())[args.asset]
    native=Canonical(args.asset);cache=DayCache(args.asset,native);market=ActualMarket(native,cache)
    execute(args.asset,Path(info['price_file']),market,d.START,d.END)
    d.dump(OUT/f'{args.asset}_status.json',dict(completed=True,validated_source_days=len(cache.sources)))


if __name__=='__main__':
    try:main()
    except Exception:
        print(traceback.format_exc(),flush=True);raise
