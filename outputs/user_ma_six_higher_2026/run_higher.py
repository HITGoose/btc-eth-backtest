"""Fixed comparisons requested by user: new six SMAs +1h/+4h and original ER.

All use SMA5/10/30/60/120/250 entry lines. Single15m new-SMA control is replayed
unchanged. ER uses its original price-efficiency formula, not old six MA lines.
No threshold search, parameter selection or current-day fitting is performed.
"""
import argparse
from dataclasses import asdict
import inspect
import json
from pathlib import Path
import sys
import traceback

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/user_ma_six_2026'))
import experiment as u
assert u.PERIODS==(5,10,30,60,120,250)
p=u.p;r=u.r;d=u.d
OUT=Path(__file__).resolve().parent
OUT.mkdir(parents=True,exist_ok=True)
HOURLY=ROOT/'outputs/ma_multitimeframe_2026/data'
HIGHER={'USER_MA15_1H':1,'USER_MA15_4H':4}
PROFILES=('USER_MA15_CONTROL','USER_MA15_ER',*HIGHER)


def dump(name,value):d.dump(OUT/name,value)


def write(name,rows):p.csv_out(OUT/name,rows)


def config():
    c=u.config();c.update(name='USER_MA5_10_30_60_120_250_HIGHER_AND_ER_V1',profiles=list(PROFILES),
        higher_profiles=HIGHER,control='Same new six-SMA single15m profile as previous run',
        higher_source=str(HOURLY),higher_official_manifest=str(HOURLY.parent/'hourly_sources.json'),
        higher_classifier='All six requested SMAs on complete1h or4h bars vs each own3bars ago',
        high_bar_lookup='Latest fully closed higher candle at or before15m signal close, UTC alignment',
        original_ER_profile='New six-SMA15m entries, original12h/120h signed price-efficiency classification',
        fast_ER_N_hours=12,fast_ER_threshold=.28284271247461906,slow_ER_N_hours=120,slow_ER_threshold=.10,
        no_ER_veto_on_MA_higher_profiles=True,
        current_day_example_used_to_fit_parameters=False,
        single_year_performance_not_used_to_change_defaults=True)
    return c


def higher(asset,hours):
    assert hours in (1,4)
    raw=np.load(HOURLY/f'{asset}_1h.npy')
    n=len(raw)//hours;blocks=raw[:n*hours].reshape(n,hours,6)
    assert np.all(blocks[:,0,0]%(hours*3600)==0)
    closes=blocks[:,-1,4]
    values=np.stack([r.model.sma(closes,n) for n in u.PERIODS])
    return (blocks[:,-1,0]+3600).astype(np.int64)*1000,u.directions(values),closes,values


def schedules(asset,leg,file,pair,hours):
    closed,states,_,_=higher(asset,hours)
    def combined_state(time,up,down):
        low=1 if up==6 else -1 if down==6 else 0
        high,_=u.state_at(closed,states,time)
        return {1:'up',-1:'down',0:'range'}[low] if low==high else 'transition'
    source=inspect.getsource(r.regime.market_schedules)
    needle='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n';assert source.count(needle)==1
    scope=dict(r.regime.__dict__);scope['combined_state']=combined_state
    exec(compile(source.replace(needle,'        state = combined_state(time, leg.up[i], leg.down[i])\n'),
        '<new six SMA15m plus closed higher classification>','exec'),scope)
    return scope['market_schedules'](asset,leg,price_file=file,include_gate_confirmation=True,
         regime_thresholds=pair,use_entry_crosses=False)


def prepare(asset):
    file=d.DATA/f'{asset}_15m.csv'
    leg=u.user_build(file,(d.START-30*86400)*1000,d.END*1000)
    prior=json.loads(r.selected.FAST_WINDOW_REPORT.read_text());policy=r.RegimeOverlay(**prior['policy'])
    pair=tuple(tuple(x) for x in prior['cases'][r.selected.MODE]['er_windows_and_thresholds'])
    assert pair==((12,.28284271247461906),(120,.1)),pair
    assert policy.pause_transition and policy.trend_level_distance_pct==2.
    source={
        'USER_MA15_CONTROL':r.ma_schedules(asset,leg,price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False),
        'USER_MA15_ER':r.regime.market_schedules(asset,leg,price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False),
        **{name:schedules(asset,leg,file,pair,h) for name,h in HIGHER.items()}}
    base=None;signals={};audit=[];counts=[]
    for name,(schedule,ctx) in source.items():
        if base is None:base=schedule['baseline']
        else:assert base==schedule['baseline']
        signals[name]=r.stacked_signals(schedule['baseline'],ctx,policy,min_aligned_lines=6)
        chosen={t:s for t,s in signals[name].items() if d.START*1000<=t<d.END*1000}
        counts.append(dict(asset=asset,profile=name,candidate_signals=len(chosen),long=sum(s==1 for s in chosen.values()),short=sum(s==-1 for s in chosen.values())))
        high_data=higher(asset,HIGHER[name]) if name in HIGHER else None
        for t,side in base.items():
            if not d.START*1000<=t<d.END*1000:continue
            i=int((t-r.regime.BAR-leg.first)//r.regime.BAR);current=1 if leg.up[i]==6 else -1 if leg.down[i]==6 else 0
            row=dict(asset=asset,profile=name,signal_ms=t,signal_beijing=r.local_s(t/1000),base_side=side,
                eligible_side=chosen.get(t,0),low_state={1:'up',-1:'down',0:'range'}[current],regime=ctx[t]['regime'],
                current_width_pct=float(leg.width[i]),min96_width_pct=float(leg.squeeze[96][i]),
                gate_reason=p.reason(side,ctx[t],policy),gate_confirmation=json.dumps(ctx[t].get('gate_confirmation'),ensure_ascii=False))
            if high_data:
                closed,states,_,_=high_data;high,hi=u.state_at(closed,states,t)
                row.update(higher_state={1:'up',-1:'down',0:'range',9:'unavailable'}[high],
                    last_higher_close=r.local_s(closed[hi]/1000) if hi>=0 else '')
                if row['eligible_side']:assert high==current==side and closed[hi]<=t
            audit.append(row)
        dump(f'{asset}_{name}_signals.json',chosen)
    write(f'{asset}_signal_audit.csv',audit);dump(f'{asset}_signal_counts.json',counts)
    print(asset,'NEW_SIX_MA_HIGHER_SIGNALS_READY',counts,flush=True)
    return leg,signals,policy,pair


def validate():
    checks=[]
    for asset in ('BTC','ETH'):
        raw=np.load(HOURLY/f'{asset}_1h.npy')
        assert np.array_equal(raw[:,0],np.arange(raw[0,0],d.END,3600))
        assert np.isfinite(raw).all() and (raw[:,3]>0).all() and (raw[:,5]>=0).all()
        for h in HIGHER.values():
            closed,states,closes,values=higher(asset,h)
            index=int(np.searchsorted(closed,d.START*1000))+100
            for offset in (0,900000,h*3600*1000-1):
                t=int(closed[index]+offset);state,i=u.state_at(closed,states,t)
                prefix=np.stack([r.model.sma(closes[:i+1],n) for n in u.PERIODS])
                assert np.array_equal(prefix[:,-4:],values[:,i-3:i+1],equal_nan=True)
                assert state==int(u.directions(prefix)[-1]) and closed[i]<=t<closed[i]+h*3600*1000
            i=int(np.searchsorted(closed,d.START*1000,side='right'))-1
            altered=closes.copy();altered[i+1:]*=1000
            modified=np.stack([r.model.sma(altered,n) for n in u.PERIODS])
            assert np.array_equal(u.directions(modified)[:i+1],states[:i+1])
            assert (np.isfinite(values[:,closed<=d.START*1000]).all(axis=0)).sum()>250
            checks.append(dict(asset=asset,hours=h,six_requested_SMAs=True,closed_higher_only=True,
                prefix_and_future_price_perturbation_pass=True,pretest_high_bars=int((closed<=d.START*1000).sum())))
        prepare(asset)
    dump('validation.json',dict(passed=True,checks=checks,config=config()))
    dump('config.json',config());print('HIGHER_SIX_SMA_VALIDATION_PASS',checks,flush=True)


def replay(asset):
    leg,signals,policy,pair=prepare(asset);p.OUT=OUT
    native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
    books={name:p.new_book(asset,name) for name in signals}
    generators={name:p.paired_generator(books[name])(asset,leg=leg,signals=signal,market=market,
         start=d.START*1000,end=d.END*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
         for name,signal in signals.items()}
    for t in range(d.START,d.END,60):
        for name,g in generators.items():assert next(g)==t
        if t%86400==0:dump(f'{asset}_progress.json',dict(time_beijing=r.local_s(t),
            books={name:dict(cash=b.cash,opens=b.stats['long']+b.stats['short'],closed=len(b.journal)) for name,b in books.items()}))
    summary=[]
    for name,g in generators.items():
        try:next(g);raise RuntimeError('Executor overshot end')
        except StopIteration as stop:q=stop.value
        assert not q['approximated_minutes']
        book=books[name];mark=float(native[d.END-60][3]);equity=book.equity(mark)
        result=dict(asset=asset,profile=name,period_beijing=[r.local_s(d.START),r.local_s(d.END)],
            starting_equity=500.,ending_equity=equity,return_pct=100*(equity/500-1),opens=q['opens'],
            trades=book.journal,events=book.events,stats=dict(book.stats),state_at_end=p.state(book),
            final_mark_price=mark,boundary_probes=book.boundary_probes,no_OHLC_fallback=True,
            fee=0.,leverage=3.,slippage=.0002,policy=asdict(policy),config=config(),original_ER=pair)
        dump(f'{asset}_{name}_result.json',result);np.save(OUT/f'{asset}_{name}_equity.npy',q['marks'])
        if name=='USER_MA15_CONTROL':
            old=json.loads((u.OUT/f'{asset}_USER_MA15_result.json').read_text());keys=('opened_us','closed_us','side','entry','exit','quantity','net','rung','reason')
            same=equity==old['ending_equity'] and [[t[k] for k in keys] for t in result['trades']]==[[t[k] for k in keys] for t in old['trades']]
            dump(f'{asset}_control_regression.json',dict(passed=same,expected=old['ending_equity'],actual=equity))
            assert same,'New six-SMA single15m control changed unexpectedly'
        summary.append(dict(asset=asset,profile=name,return_pct=result['return_pct'],opens=q['opens']))
        print(asset,name,'COMPLETE',summary[-1],flush=True)
    dump(f'{asset}_status.json',dict(completed=True,validated_tick_source_days=len(cache.sources),results=summary))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['validate','replay']);parser.add_argument('--asset',choices=['BTC','ETH']);args=parser.parse_args()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    if args.mode=='validate':validate()
    else:
        assert args.asset is not None
        replay(args.asset)


if __name__=='__main__':
    try:main()
    except Exception:
        print(traceback.format_exc(),flush=True);raise
