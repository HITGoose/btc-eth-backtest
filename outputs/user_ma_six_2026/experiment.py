"""User-confirmed SMA5/10/30/60/120/250, independent of all older versions.

Change only the six entry/classification averages. MACD, auxiliary SMA5/SMA20,
2% ABS support/resistance, 96-bar squeeze threshold and execution stay frozen.
Profiles: single15m and15m+closed30m; old-six-line book is a financial control.
No fresh mixed-to-aligned or width-expansion condition is invented.
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
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
r=p.r;d=p.d
OUT=Path(__file__).resolve().parent
OUT.mkdir(parents=True,exist_ok=True)
DATA=OUT/'data';DATA.mkdir(exist_ok=True)
PERIODS=(5,10,30,60,120,250)
PROFILES=('USER_MA15','USER_MA15_30M')
OLD_NEEDLE='    lines = np.stack([sma(c, n) for n in (20, 60, 120)] + [ema(c, n) for n in (20, 60, 120)])\n'
BUILD_SOURCE=inspect.getsource(r.model.build)
assert BUILD_SOURCE.count(OLD_NEEDLE)==1
BUILD_SCOPE=dict(r.model.__dict__)
exec(compile(BUILD_SOURCE.replace(OLD_NEEDLE,
        '    lines = np.stack([sma(c, n) for n in (5, 10, 30, 60, 120, 250)])\n'),
        '<user-authorized six SMA periods, original build otherwise unchanged>','exec'),BUILD_SCOPE)
user_build=BUILD_SCOPE['build']


def dump(name,data):d.dump(OUT/name,data)


def write(name,rows):p.csv_out(OUT/name,rows)


def config():
    return dict(name='USER_MA5_10_30_60_120_250_V1',experimental=True,
        six_averages=['SMA'+str(n) for n in PERIODS],required_aligned_lines=6,
        slope_comparison_bars=3,continuous_monotonic_last3_bars_required=False,
        previous_state_required_to_be_mixed=False,
        squeeze_pct=.25,squeeze_lookback_15m_bars=96,squeeze_includes_signal_bar=True,
        previous_bar_required_to_be_compressed=False,bandwidth_required_to_be_expanding=False,
        profiles=list(PROFILES),single15m_classifier='Six current MAs vs their values three15m bars earlier',
        higher_classifier='Same six SMAs on complete30m bars vs their values three30m bars earlier',
        MTF_rule='Only same direction allows that direction; conflicts pause; both range keeps original range branch',
        high_bar_lookup='Latest complete30m at or before15m signal close; UTCxx:00/xx:30',
        auxiliary_trend_confirmation='Original SMA5 vs SMA20 and MACD histogram sign retained',
        MACD='Original EMA12-EMA26; DEA EMA9 retained',use_entry_crosses=False,
        SR_absolute_distance_pct=2.,fee=0.,slippage=.0002,leverage=3.,initial_each_asset=500.,
        pending_expiry_minutes=60,poll_seconds=5,poll_phase=2,
        conflict_cancels_pending=False,conflict_closes_position=False,
        test_period_beijing=[r.local_s(d.START),r.local_s(d.END)],
        source='Same checksum-verified Binance USD-M15m/1m and actual aggTrades archives',
        original_files_unchanged=True,old_results_do_not_describe_this_definition=True,
        original_known_submit_boundary='stamp > submit_at preserved',
        limit_execution='Full-size touch proxy; queue/partial fills unverified',funding='omitted')


def prepare30():
    info=[]
    for asset in ('BTC','ETH'):
        file=d.DATA/f'{asset}_15m.csv';raw=np.loadtxt(file,delimiter=',',skiprows=1);raw[:,0]/=1000
        assert np.array_equal(raw[:,0],np.arange(d.FIRST15,d.END,900))
        assert len(raw)%2==0 and raw[0,0]%1800==0
        blocks=raw.reshape(-1,2,6)
        rows=np.column_stack((blocks[:,0,0],blocks[:,0,1],blocks[:,:,2].max(axis=1),
                 blocks[:,:,3].min(axis=1),blocks[:,-1,4],blocks[:,:,5].sum(axis=1)))
        assert np.array_equal(rows[:,0],np.arange(d.FIRST15,d.END,1800))
        minute=np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r')
        minute=minute[(d.START-d.FIRST1)//60:(d.END-d.FIRST1)//60].reshape(-1,30,5)
        expected=np.column_stack((minute[:,0,0],minute[:,:,1].max(axis=1),minute[:,:,2].min(axis=1),minute[:,-1,3]))
        assert np.array_equal(rows[(rows[:,0]>=d.START)&(rows[:,0]<d.END),1:5],expected)
        np.save(DATA/f'{asset}_30m.npy',rows)
        info.append(dict(asset=asset,source_15m=str(file),source_15m_sha256=hashlib.file_digest(file.open('rb'),'sha256').hexdigest(),
            official_candle_manifest=str(d.OUT/'candle_sources.json'),bars=len(rows),
            pretest_bars=int(((rows[:,0]+1800)<=d.START).sum()),all_native_1m_OHLC_agree=True,
            dense_unique_closed_grid=True))
    dump('prepared_inputs.json',info);dump('config.json',config())
    print('USER_SIX_SMA_INPUTS_READY',info,flush=True)


def directions(lines):
    states=np.full(lines.shape[1],9,dtype=np.int8)
    valid=np.isfinite(lines[:,3:]).all(axis=0)&np.isfinite(lines[:,:-3]).all(axis=0)
    up=(lines[:,3:]>lines[:,:-3]).all(axis=0);down=(lines[:,3:]<lines[:,:-3]).all(axis=0)
    states[3:]=np.where(valid,np.where(up,1,np.where(down,-1,0)),9)
    return states


def higher(asset):
    rows=np.load(DATA/f'{asset}_30m.npy');closes=rows[:,4]
    lines=np.stack([r.model.sma(closes,n) for n in PERIODS])
    return (rows[:,0]+1800).astype(np.int64)*1000,directions(lines),closes,lines


def state_at(closed,states,time):
    i=int(np.searchsorted(closed,time,side='right'))-1
    return int(states[i]) if i>=0 else 9,i


def classify30(asset,leg,file,pair):
    closed,states,_,_=higher(asset)
    def combined_state(time,up,down):
        low=1 if up==6 else -1 if down==6 else 0
        high,_=state_at(closed,states,time)
        return {1:'up',-1:'down',0:'range'}[low] if low==high else 'transition'
    source=inspect.getsource(r.regime.market_schedules)
    needle='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n'
    assert source.count(needle)==1
    scope=dict(r.regime.__dict__);scope['combined_state']=combined_state
    exec(compile(source.replace(needle,'        state = combined_state(time, leg.up[i], leg.down[i])\n'),
        '<user six SMAs15m+closed30m regime experiment>','exec'),scope)
    return scope['market_schedules'](asset,leg,price_file=file,include_gate_confirmation=True,
              regime_thresholds=pair,use_entry_crosses=False)


def prepare_signals(asset):
    file=d.DATA/f'{asset}_15m.csv'
    oldleg,oldsignals,oldcontexts,oldbase,policy,pair=p.prepare(asset,file,d.START,d.END)
    assert policy.pause_transition and policy.trend_level_distance_pct==2.
    leg=user_build(file,(d.START-30*86400)*1000,d.END*1000)
    schedules={};contexts={};signals={};base=None
    for name in PROFILES:
        schedule,ctx=(r.ma_schedules(asset,leg,price_file=file,include_gate_confirmation=True,
              regime_thresholds=pair,use_entry_crosses=False) if name=='USER_MA15' else classify30(asset,leg,file,pair))
        if base is None:base=schedule['baseline']
        else:assert base==schedule['baseline']
        schedules[name]=schedule;contexts[name]=ctx
        signals[name]=r.stacked_signals(schedule['baseline'],ctx,policy,min_aligned_lines=6)
    closed,states,_,_=higher(asset);audit=[];counts=[]
    for name in PROFILES:
        selected={t:s for t,s in signals[name].items() if d.START*1000<=t<d.END*1000}
        counts.append(dict(asset=asset,profile=name,candidates=len(selected),
            long=sum(s==1 for s in selected.values()),short=sum(s==-1 for s in selected.values())))
        for t,side in base.items():
            if not d.START*1000<=t<d.END*1000:continue
            i=int((t-r.regime.BAR-leg.first)//r.regime.BAR)
            low=1 if leg.up[i]==6 else -1 if leg.down[i]==6 else 0
            high,hi=state_at(closed,states,t);eligible=selected.get(t,0)
            if eligible:
                assert low==side
                if name=='USER_MA15_30M':assert high==side and closed[hi]<=t
            prev=1 if leg.up[i-1]==6 else -1 if leg.down[i-1]==6 else 0
            recent=np.flatnonzero(leg.width[i-95:i+1]<=.25)+i-95
            last=int(recent[-1]) if len(recent) else None
            audit.append(dict(asset=asset,profile=name,signal_ms=t,signal_beijing=r.local_s(t/1000),
                core_side=side,eligible_side=eligible,MA15_state={1:'up',-1:'down',0:'range'}[low],
                previous_MA15_state={1:'up',-1:'down',0:'range'}[prev],
                MA30_state={1:'up',-1:'down',0:'range',9:'unavailable'}[high],
                higher_last_closed_beijing=r.local_s(closed[hi]/1000) if hi>=0 else '',
                combined_regime=contexts[name][t]['regime'],aligned_lines=int((leg.up if side==1 else leg.down)[i]),
                current_width_pct=float(leg.width[i]),previous_width_pct=float(leg.width[i-1]),
                min96_width_pct=float(leg.squeeze[96][i]),bars_since_last_compression=i-last if last is not None else '',
                rejection_reason=p.reason(side,contexts[name][t],policy)))
        dump(f'{asset}_{name}_signals.json',selected)
    write(f'{asset}_signal_audit.csv',audit);dump(f'{asset}_signal_counts.json',counts)
    print(asset,'USER_SIX_MA_SIGNALS_READY',counts,flush=True)
    return oldleg,oldsignals['MA'],leg,signals,policy,pair


def validate():
    checks=[]
    for asset in ('BTC','ETH'):
        file=d.DATA/f'{asset}_15m.csv';old,oldsignals,new,signals,policy,pair=prepare_signals(asset)
        raw=np.loadtxt(file,delimiter=',',skiprows=1)
        raw=raw[(raw[:,0]>=new.first)&(raw[:,0]<new.end)]
        closes=raw[:,4];lines=np.stack([r.model.sma(closes,n) for n in PERIODS])
        assert np.array_equal(new.histogram,old.histogram),'MACD changed with six-MA definition'
        expected_width=100*(lines.max(axis=0)-lines.min(axis=0))/closes
        assert np.array_equal(expected_width,new.width,equal_nan=True)
        assert np.array_equal(new.above_band,closes>lines.max(axis=0))
        assert np.array_equal(new.below_band,closes<lines.min(axis=0))
        assert np.array_equal(new.up[3:],(lines[:,3:]>lines[:,:-3]).sum(axis=0))
        assert np.array_equal(new.down[3:],(lines[:,3:]<lines[:,:-3]).sum(axis=0))
        closed,states,hc,higher_lines=higher(asset)
        index=int(np.searchsorted(closed,d.START*1000))+100
        for offset in (0,900000,1799999):
            time=int(closed[index]+offset);s,i=state_at(closed,states,time)
            prefix=np.stack([r.model.sma(hc[:i+1],n) for n in PERIODS])
            assert np.array_equal(prefix[:,-4:],higher_lines[:,i-3:i+1],equal_nan=True)
            assert s==int(directions(prefix)[-1]) and closed[i]<=time<closed[i]+1800000
        i=int(np.searchsorted(closed,d.START*1000,side='right'))-1
        altered=hc.copy();altered[i+1:]*=1000
        changed=np.stack([r.model.sma(altered,n) for n in PERIODS])
        assert np.array_equal(directions(changed)[:i+1],states[:i+1])
        checks.append(dict(asset=asset,six_requested_SMAs_used=True,MACD_unchanged=True,
             bandwidth_and_outside_all_six_use_new_SMAs=True,slope_equals_own_three_bars_ago=True,
             closed30m_prefix_and_future_perturbation=True,min_aligned_lines=6,
             current_and_previous95_density_rule_retained=True,
             no_new_previous_mixed_or_expansion_rule=True))
    dump('validation.json',dict(passed=True,checks=checks,config=config()))
    print('USER_SIX_MA_VALIDATION_PASS',checks,flush=True)


def replay(asset):
    oldleg,oldsignals,leg,signals,policy,pair=prepare_signals(asset)
    p.OUT=OUT
    native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
    profiles={'OLD_SIX_CONTROL':(oldleg,oldsignals),**{name:(leg,signals[name]) for name in PROFILES}}
    books={name:p.new_book(asset,name) for name in profiles}
    generators={name:p.paired_generator(books[name])(asset,leg=data[0],signals=data[1],market=market,
        start=d.START*1000,end=d.END*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,
        print_progress=False) for name,data in profiles.items()}
    for t in range(d.START,d.END,60):
        for name,g in generators.items():assert next(g)==t
        if t%86400==0:
            dump(f'{asset}_progress.json',dict(time_beijing=r.local_s(t),
                books={name:dict(cash=b.cash,opens=b.stats['long']+b.stats['short'],closed=len(b.journal)) for name,b in books.items()}))
    summary=[]
    for name,g in generators.items():
        try:next(g);raise RuntimeError('Executor overshot end')
        except StopIteration as stop:q=stop.value
        assert not q['approximated_minutes']
        book=books[name];mark=float(native[d.END-60][3]);value=book.equity(mark)
        result=dict(asset=asset,profile=name,period_beijing=[r.local_s(d.START),r.local_s(d.END)],
            starting_equity=500.,ending_equity=value,return_pct=100*(value/500-1),opens=q['opens'],
            trades=book.journal,events=book.events,stats=dict(book.stats),state_at_end=p.state(book),
            final_mark_price=mark,boundary_probes=book.boundary_probes,no_OHLC_fallback=True,
            fee=0.,leverage=3.,slippage=.0002,policy=asdict(policy),
            config=config() if name!='OLD_SIX_CONTROL' else dict(control_only=True,definition='SMA/EMA20,60,120'),
            original_ER_parameters_for_provenance_only=pair)
        dump(f'{asset}_{name}_result.json',result);np.save(OUT/f'{asset}_{name}_equity.npy',q['marks'])
        if name=='OLD_SIX_CONTROL':
            old=json.loads((d.OUT/f'{asset}_MA_result.json').read_text());keys=('opened_us','closed_us','side','entry','exit','quantity','net','rung','reason')
            same=value==old['ending_equity'] and [[t[k] for k in keys] for t in result['trades']]==[[t[k] for k in keys] for t in old['trades']]
            dump(f'{asset}_control_regression.json',dict(passed=same,expected=old['ending_equity'],actual=value))
            assert same,'Old six-line financial control unexpectedly changed'
        summary.append(dict(asset=asset,profile=name,return_pct=result['return_pct'],opens=q['opens']))
        print(asset,name,'COMPLETE',summary[-1],flush=True)
    dump(f'{asset}_status.json',dict(completed=True,validated_tick_source_days=len(cache.sources),results=summary))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','validate','replay']);parser.add_argument('--asset',choices=['BTC','ETH']);args=parser.parse_args()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    if args.mode=='prepare':prepare30()
    elif args.mode=='validate':validate()
    else:
        assert args.asset is not None
        replay(args.asset)


if __name__=='__main__':
    try:main()
    except Exception:
        print(traceback.format_exc(),flush=True);raise
