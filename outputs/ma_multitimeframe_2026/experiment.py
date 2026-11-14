"""Independent user-requested MTF classification experiment; originals unchanged.

15m and one higher timeframe each classify six original MAs vs three bars ago.
Only equal directional states permit that direction. Different states pause
new signals; both range retains the original range branch. All execution and
entry filters are delegated to original code. No timeframe is selected by ROI.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime,timezone
import csv
import hashlib
import inspect
import json
from pathlib import Path
import sys
import traceback

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/attribution_2026'))
import paired_replay as p
d=p.d;r=p.r
OUT=Path(__file__).resolve().parent
DATA=OUT/'data';DATA.mkdir(parents=True,exist_ok=True)
HOURS=(1,4,12,24)
SOURCE_BEGIN=int(datetime(2023,1,1,tzinfo=timezone.utc).timestamp())
PROFILES={f'MA15_{h}H':h for h in HOURS}


def dump(file,value):d.dump(OUT/file,value)


def write(file,rows):
    p.csv_out(OUT/file,rows)


def config():
    return dict(experimental=True,name='MA15_PLUS_ONE_HIGHER_TIMEFRAME',
        original_sources_changed=False,use_entry_crosses=False,
        compare_bars_ago=3,averages=['SMA20','SMA60','SMA120','EMA20','EMA60','EMA120'],
        profiles=PROFILES,control='MA15_CONTROL: original single15m classification',
        composition='Two matching states retained; mismatches transition/pause',
        equality_or_mixed_lines='range',incomplete_history='UNAVAILABLE_PAUSE',
        higher_candle_anchor='UTC 00:00; daily closes at Beijing08:00',
        higher_lookup='latest closed higher bar at or before signal close; never forming bar',
        signal_interval='15m',fee=0.,slippage=.0002,leverage=3.,starting_equity_each_asset=500.,
        SR_absolute_distance_pct=2.,pending_lifetime_minutes=60,
        pauses_cancel_existing_orders=False,pauses_close_existing_positions=False,
        source_begin_utc=datetime.fromtimestamp(SOURCE_BEGIN,timezone.utc).isoformat(),
        financial_test_window_beijing=[r.local_s(d.START),r.local_s(d.END)],
        execution='Original actual tick executor, 5s polls phase2; touch proxy, no funding')


def prepare_data():
    months=[f'{y}-{m:02}' for y in range(2023,2027) for m in range(1,13) if y<2026 or m<=10]
    jobs=[(asset,month) for asset in ('BTC','ETH') for month in months]
    groups={'BTC':[],'ETH':[]};sources=[]
    def job(task):
        asset,month=task;symbol=asset+'USDT';file=DATA/f'{asset}_1h_{month}.zip'
        url=f'{d.BASE}/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip'
        meta=d.acquire(url,file);rows=d.read_zip(file,list(range(6)))
        return asset,rows,dict(asset=asset,month=month,**meta)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for asset,rows,source in pool.map(job,jobs):groups[asset].append(rows);sources.append(source)
    summary=[]
    for asset,parts in groups.items():
        rows=np.concatenate(parts);scale=1e6 if rows[0,0]>1e14 else 1000
        rows[:,0]/=scale;rows=rows[(rows[:,0]>=SOURCE_BEGIN)&(rows[:,0]<d.END)]
        rows=rows[np.argsort(rows[:,0],kind='stable')]
        assert np.array_equal(rows[:,0],np.arange(SOURCE_BEGIN,d.END,3600)),asset+' hourly gaps/duplicates'
        assert np.isfinite(rows).all() and (rows[:,3]>0).all() and (rows[:,5]>=0).all()
        assert (rows[:,3]<=np.minimum(rows[:,1],rows[:,4])).all()
        assert (rows[:,2]>=np.maximum(rows[:,1],rows[:,4])).all()
        # Cross-check the execution-year hourly OHLC against the native 15m source.
        low=np.loadtxt(d.DATA/f'{asset}_15m.csv',delimiter=',',skiprows=1)
        low[:,0]/=1000;low=low[(low[:,0]>=d.START)&(low[:,0]<d.END)]
        blocks=low.reshape(-1,4,6)
        rolled=np.column_stack((blocks[:,0,0],blocks[:,0,1],blocks[:,:,2].max(axis=1),
                   blocks[:,:,3].min(axis=1),blocks[:,-1,4]))
        native=rows[(rows[:,0]>=d.START)&(rows[:,0]<d.END),:5]
        assert np.array_equal(native,rolled),asset+' native hourly / existing15m OHLC conflict'
        np.save(DATA/f'{asset}_1h.npy',rows)
        summary.append(dict(asset=asset,hourly_rows=len(rows),first=rows[0,0],last=rows[-1,0],
               dense_grid=True,existing_15m_OHLC_match=True,old_strategy_15m_source_unchanged=True))
        print(asset,'HIGHER_INPUTS_READY',summary[-1],flush=True)
    dump('hourly_sources.json',sources);dump('prepared_inputs.json',summary);dump('config.json',config())


def direction(lines):
    result=np.full(lines.shape[1],9,dtype=np.int8)
    valid=np.isfinite(lines[:,3:]).all(axis=0)&np.isfinite(lines[:,:-3]).all(axis=0)
    sameup=(lines[:,3:]>lines[:,:-3]).all(axis=0)
    samedown=(lines[:,3:]<lines[:,:-3]).all(axis=0)
    result[3:]=np.where(valid,np.where(sameup,1,np.where(samedown,-1,0)),9)
    return result


def higher(asset,hours):
    hourly=np.load(DATA/f'{asset}_1h.npy')
    # UTC-aligned complete blocks only; forming final higher candle discarded.
    n=len(hourly)//hours;blocks=hourly[:n*hours].reshape(n,hours,6)
    assert np.array_equal(blocks[:,0,0]%(hours*3600),np.zeros(n))
    closes=blocks[:,-1,4]
    values=np.stack([r.model.sma(closes,n) for n in (20,60,120)]+
                    [r.model.ema(closes,n) for n in (20,60,120)])
    states=direction(values);closed=(blocks[:,-1,0]+3600).astype(np.int64)*1000
    assert (states[closed<=d.START*1000]!=9).sum()>=900 if hours==24 else True
    return closed,states,closes,values


def state_at(closed,states,times):
    index=np.searchsorted(closed,times,side='right')-1
    return np.where(index>=0,states[np.maximum(index,0)],9)


def combine(a,b):
    if 9 in (a,b):return 'transition'
    return {1:'up',-1:'down',0:'range'}[a] if a==b else 'transition'


def schedules(asset,leg,file,hours,pair):
    closed,states,_,_=higher(asset,hours)
    def combined_state(time,up,down):
        small=1 if up==6 else -1 if down==6 else 0
        high=int(state_at(closed,states,np.array([time]))[0])
        return combine(small,high)
    source=inspect.getsource(r.regime.market_schedules)
    needle='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n'
    assert source.count(needle)==1
    source=source.replace(needle,'        state = combined_state(time, leg.up[i], leg.down[i])\n')
    ns=dict(r.regime.__dict__);ns['combined_state']=combined_state
    exec(compile(source,'<independent MTF classification experiment>','exec'),ns)
    return ns['market_schedules'](asset,leg,price_file=file,include_gate_confirmation=True,
                                 regime_thresholds=pair,use_entry_crosses=False)


def prepare_signals(asset):
    file=d.DATA/f'{asset}_15m.csv';leg,old,oldctx,base,policy,pair=p.prepare(asset,file,d.START,d.END)
    assert policy.pause_transition and policy.trend_level_distance_pct==2.
    signals={};contexts={};counts=[];audit=[]
    for name,h in PROFILES.items():
        schedule,context=schedules(asset,leg,file,h,pair)
        assert schedule['baseline']==base
        signals[name]=r.stacked_signals(schedule['baseline'],context,policy);contexts[name]=context
        closed,states,_,_=higher(asset,h)
        totals={s:0 for s in ('up','down','range','transition')}
        for t,side in base.items():
            if not d.START*1000<=t<d.END*1000:continue
            i=(t-r.regime.BAR-leg.first)//r.regime.BAR
            small=1 if leg.up[i]==6 else -1 if leg.down[i]==6 else 0
            ix=np.searchsorted(closed,t,side='right')-1;high=int(states[ix]) if ix>=0 else 9
            eligible=signals[name].get(t,0);state=context[t]['regime'];totals[state]+=1
            if eligible:
                assert small==side==high,('wrong-direction MTF signal',asset,name,t)
                assert closed[ix]<=t
            audit.append(dict(asset=asset,profile=name,signal_ms=t,signal_beijing=r.local_s(t/1000),
                core_side=side,aligned_lines=int((leg.up if side==1 else leg.down)[i]),
                MA15_state={1:'up',-1:'down',0:'range'}[small],
                higher_state={1:'up',-1:'down',0:'range',9:'unavailable'}[high],
                higher_last_close_beijing=r.local_s(closed[ix]/1000) if ix>=0 else '',
                combined_state=state,eligible_side=eligible,
                prior_MA15_eligible_side=old['MA'].get(t,0),prior_ER_eligible_side=old['ER'].get(t,0)))
        selected={t:s for t,s in signals[name].items() if d.START*1000<=t<d.END*1000}
        assert all(context[t]['regime'] in ('up','down') for t in selected)
        counts.append(dict(asset=asset,profile=name,higher_hours=h,eligible_signals=len(selected),
            eligible_long=sum(s==1 for s in selected.values()),eligible_short=sum(s==-1 for s in selected.values()),
            original_core_signal_count=sum(d.START*1000<=t<d.END*1000 for t in base),
            core_context_counts=totals))
        dump(f'{asset}_{name}_signals.json',selected)
    write(f'{asset}_signal_audit.csv',audit);dump(f'{asset}_signal_counts.json',counts)
    print(asset,'SIGNALS_READY',counts,flush=True)
    return leg,signals,contexts,policy,pair,old


def validate():
    tests=[]
    for a in (1,-1,0):
        for b in (1,-1,0):
            assert combine(a,b)==({1:'up',-1:'down',0:'range'}[a] if a==b else 'transition')
    tests.append(dict(test='all_nine_state_combinations',passed=True))
    for asset in ('BTC','ETH'):
        # Causality: future prices cannot alter the last closed-bar observation.
        for h in HOURS:
            closed,states,closes,values=higher(asset,h)
            target=int(np.searchsorted(closed,d.START*1000))+100
            for offset in (0,900000,h*3600*1000-1):
                time=int(closed[target]+offset)
                index=int(np.searchsorted(closed,time,side='right')-1)
                prefix=closes[:index+1]
                pvalues=np.stack([r.model.sma(prefix,n) for n in (20,60,120)]+
                                 [r.model.ema(prefix,n) for n in (20,60,120)])
                assert np.array_equal(pvalues[:,-4:],values[:,index-3:index+1],equal_nan=True)
                assert int(direction(pvalues)[-1])==int(state_at(closed,states,np.array([time]))[0])
                assert closed[index]<=time and (index+1==len(closed) or closed[index+1]>time)
            # Partial-bar prices, however large, must not appear in the lookup.
            index=int(np.searchsorted(closed,d.START*1000,side='right')-1)
            other=closes.copy();other[index+1:]*=1000
            newvalues=np.stack([r.model.sma(other,n) for n in (20,60,120)]+
                              [r.model.ema(other,n) for n in (20,60,120)])
            assert np.array_equal(direction(newvalues)[:index+1],states[:index+1])
            tests.append(dict(asset=asset,hours=h,test='prefix_and_future_price_perturbation',passed=True,
                high_bar_count_before_start=int((closed<=d.START*1000).sum())))
        prepare_signals(asset)
    dump('validation.json',dict(passed=True,checks=tests,new_rule_not_original=True))
    print('MTF_CLOSED_BAR_VALIDATION_PASS',len(tests),flush=True)


def replay(asset):
    leg,signals,contexts,policy,pair,old=prepare_signals(asset)
    signals={'MA15_CONTROL':old['MA'],**signals}
    # Output redirection affects only the observer/cache, never original code.
    p.OUT=OUT
    native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
    books={name:p.new_book(asset,name) for name in signals}
    generators={name:p.paired_generator(book)(asset,leg=leg,signals=signals[name],market=market,
         start=d.START*1000,end=d.END*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,
         print_progress=False) for name,book in books.items()}
    for t in range(d.START,d.END,60):
        for name,g in generators.items():assert next(g)==t
        if t%86400==0:
            dump(f'{asset}_progress.json',dict(time_beijing=r.local_s(t),
                 books={name:dict(cash=b.cash,opens=b.stats['long']+b.stats['short'],closed=len(b.journal)) for name,b in books.items()}))
    results=[]
    for name,g in generators.items():
        try:next(g);raise RuntimeError('Executor overshot end')
        except StopIteration as stop:q=stop.value
        assert not q['approximated_minutes']
        book=books[name];mark=float(native[d.END-60][3]);value=book.equity(mark)
        result=dict(asset=asset,profile=name,period_beijing=[r.local_s(d.START),r.local_s(d.END)],
            starting_equity=500.,ending_equity=value,return_pct=100*(value/500-1),
            opens=q['opens'],trades=book.journal,events=book.events,stats=dict(book.stats),
            state_at_end=p.state(book),final_mark_price=mark,boundary_probes=book.boundary_probes,
            no_OHLC_fallback=True,fee=0.,leverage=3.,slippage=.0002,policy=asdict(policy),
            config=config(),original_ER_parameters_for_provenance_only=pair)
        dump(f'{asset}_{name}_result.json',result);np.save(OUT/f'{asset}_{name}_equity.npy',q['marks'])
        if name=='MA15_CONTROL':
            previous=json.loads((d.OUT/f'{asset}_MA_result.json').read_text())
            fields=('opened_us','closed_us','side','entry','exit','quantity','net','rung','reason')
            matches=(value==previous['ending_equity'] and
                [[t[k] for k in fields] for t in result['trades']]==
                [[t[k] for k in fields] for t in previous['trades']])
            dump(f'{asset}_control_regression.json',dict(passed=matches,
                expected_equity=previous['ending_equity'],actual_equity=value))
            assert matches,'Original single15m financial control changed unexpectedly'
        results.append(dict(asset=asset,profile=name,return_pct=result['return_pct'],opens=q['opens']))
        print(asset,name,'COMPLETE',results[-1],flush=True)
    dump(f'{asset}_status.json',dict(completed=True,results=results,validated_tick_source_days=len(cache.sources)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','validate','replay'])
    parser.add_argument('--asset',choices=['BTC','ETH']);args=parser.parse_args()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    if args.mode=='prepare':prepare_data()
    elif args.mode=='validate':validate()
    else:
        if args.asset is None:raise RuntimeError('--asset is required for replay')
        replay(args.asset)


if __name__=='__main__':
    try:main()
    except Exception:
        print(traceback.format_exc(),flush=True);raise
