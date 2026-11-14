"""User-requested isolated 0.50% recent96-bar squeeze experiment.

Only one conceptual threshold changes: original core ENTRY.squeeze_threshold
and the matching overlay range_squeeze_pct become0.50. Current range bandwidth
cap stays0.50; ABS support/resistance distance stays2.00. All six SMAs, 3-bar
directions, execution and fees stay fixed. Old0.25 files are read-only controls.
"""
import argparse
from dataclasses import asdict,replace
from datetime import datetime
from pathlib import Path
import inspect
import json
import shutil
import sys
import traceback

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/user_ma_six_higher_2026'))
import run_higher as h
u=h.u;p=h.p;r=h.r;d=h.d
OUT=Path(__file__).resolve().parent
THRESHOLD=.50
PROFILES=('MA15','M30','H1','H4','ER')
LABELS={'MA15':'单15分钟','M30':'15分钟＋30分钟','H1':'15分钟＋1小时',
        'H4':'15分钟＋4小时','ER':'新六MA入场＋ER'}
ANNUAL=OUT/'annual2026';RECENT=OUT/'recent'
for folder in (OUT,ANNUAL,RECENT):folder.mkdir(parents=True,exist_ok=True)


def dump(folder,name,value):d.dump(folder/name,value)


def write(folder,name,rows):p.csv_out(folder/name,rows)


def original_policy():
    prior=json.loads(r.selected.FAST_WINDOW_REPORT.read_text())
    policy=r.RegimeOverlay(**prior['policy'])
    pair=tuple(tuple(x) for x in prior['cases'][r.selected.MODE]['er_windows_and_thresholds'])
    assert policy.range_squeeze_pct==.25 and policy.range_entry_bandwidth_pct==.50
    assert policy.trend_level_distance_pct==2. and policy.pause_transition
    return policy,pair


def config():
    c=u.config();c.update(name='USER_SIX_SMA_SQUEEZE_050',squeeze_pct=THRESHOLD,
        profiles=list(PROFILES),baseline_squeeze_pct=.25,range_entry_bandwidth_cap_unchanged=.50,
        higher_classifier='Same six requested SMAs on complete30m/1h/4h candles respectively, vs each own3bars ago',
        high_bar_lookup='Latest complete higher candle at or before15m signal close; UTC aligned',
        test_period_beijing='See each result.period_beijing; annual and recent are separate windows',
        support_resistance_absolute_distance_unchanged_pct=2.,
        core_and_overlay_density_threshold_both_updated=True,
        old_025_financial_results_reused_not_rerun=True,automated_parameter_search=False,
        recent_simulations_start_nov9_no_nov12_reset=True)
    return c


def set_runtime(folder):
    p.OUT=folder;r.OUT=folder;r.DATA=folder/'data';r.DATA.mkdir(exist_ok=True)
    r.RESPONSES=r.DATA/'responses';r.RESPONSES.mkdir(exist_ok=True);r.public.CACHE=r.DATA
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.


def classify(asset,leg,file,pair,kind,threshold,series):
    source=inspect.getsource(r.regime.market_schedules)
    needle='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n'
    assert source.count(needle)==1
    scope=dict(r.regime.__dict__)
    entry=replace(r.regime.ENTRY,squeeze_threshold=threshold)
    assert entry.lookback==96 and entry.exit_policy==r.regime.ENTRY.exit_policy
    scope['ENTRY']=entry
    if kind=='MA15':
        source=source.replace(needle,'        state = "up" if leg.up[i] == 6 else "down" if leg.down[i] == 6 else "range"\n')
    elif kind!='ER':
        closed,states=series[kind]
        def combined_state(time,up,down):
            low=1 if up==6 else -1 if down==6 else 0;high,_=u.state_at(closed,states,time)
            return {1:'up',-1:'down',0:'range'}[low] if low==high else 'transition'
        scope['combined_state']=combined_state
        source=source.replace(needle,'        state = combined_state(time, leg.up[i], leg.down[i])\n')
    exec(compile(source,'<isolated recent96 squeeze threshold and existing classifier>','exec'),scope)
    return scope['market_schedules'](asset,leg,price_file=file,include_gate_confirmation=True,
        regime_thresholds=pair,use_entry_crosses=False)


def annual_series(asset):
    rows=np.load(u.DATA/f'{asset}_30m.npy')
    lines=np.stack([r.model.sma(rows[:,4],n) for n in u.PERIODS])
    series={'M30':((rows[:,0]+1800).astype(np.int64)*1000,u.directions(lines))}
    for key,hours in [('H1',1),('H4',4)]:
        closed,states,_,_=h.higher(asset,hours);series[key]=(closed,states)
    return series


def recent_info(asset):
    if asset=='BTC':
        file=ROOT/'outputs/btc_nov12_nov13_comparison/data/BTC_Gate_extended_15m.csv'
        cutoff=int(datetime(2026,11,13,12,tzinfo=r.TZ).timestamp())
    else:
        file=ROOT/'outputs/eth_today_20261113/data/ETH_Gate_15m_extended.csv'
        cutoff=int(datetime(2026,11,13,11,30,tzinfo=r.TZ).timestamp())
    return file,cutoff


def recent_series(file,cutoff):
    raw=np.loadtxt(file,delimiter=',',skiprows=1);raw[:,0]/=1000
    raw=raw[raw[:,0]+900<=cutoff];series={}
    for key,size in [('M30',2),('H1',4),('H4',16)]:
        n=len(raw)//size;blocks=raw[:n*size].reshape(n,size,6)
        assert np.all(blocks[:,0,0]%(size*900)==0)
        values=np.stack([r.model.sma(blocks[:,-1,4],n) for n in u.PERIODS])
        series[key]=((blocks[:,-1,0]+900).astype(np.int64)*1000,u.directions(values))
    return series


def prepare(asset,mode,threshold=THRESHOLD,save=True):
    oldpolicy,pair=original_policy();policy=replace(oldpolicy,range_squeeze_pct=threshold)
    assert policy.range_entry_bandwidth_pct==.50 and policy.trend_level_distance_pct==2.
    if mode=='annual':
        file=d.DATA/f'{asset}_15m.csv';start=d.START;end=d.END;build_start=start-30*86400
        series=annual_series(asset);build_end=end
    else:
        file,end=recent_info(asset);start=r.START;build_start=r.WARM;series=recent_series(file,end)
        raw=np.loadtxt(file,delimiter=',',skiprows=1);build_end=int(raw[-1,0]//1000)+900
    leg=u.user_build(file,build_start*1000,build_end*1000)
    signals={};contexts={};audit=[];core=None
    for kind in PROFILES:
        schedules,ctx=classify(asset,leg,file,pair,kind,threshold,series)
        if core is None:core=schedules['baseline']
        else:assert core==schedules['baseline']
        signals[kind]=r.stacked_signals(schedules['baseline'],ctx,policy,min_aligned_lines=6);contexts[kind]=ctx
        if save:
            chosen={t:s for t,s in signals[kind].items() if start*1000<=t<end*1000}
            folder=ANNUAL if mode=='annual' else RECENT
            dump(folder,f'{asset}_{kind}_signals.json',chosen)
            for t,side in core.items():
                if not start*1000<=t<end*1000:continue
                i=int((t-r.regime.BAR-leg.first)//r.regime.BAR)
                audit.append(dict(asset=asset,profile=kind,threshold_pct=threshold,signal_ms=t,signal_beijing=r.local_s(t/1000),
                    core_side=side,eligible_side=chosen.get(t,0),regime=ctx[t]['regime'],
                    up_lines=int(leg.up[i]),down_lines=int(leg.down[i]),current_width_pct=float(leg.width[i]),
                    minimum96_width_pct=float(leg.squeeze[96][i]),gate_reason=p.reason(side,ctx[t],policy),
                    gate_confirmation=json.dumps(ctx[t].get('gate_confirmation'),ensure_ascii=False)))
            print(mode,asset,kind,'SIGNALS',len(chosen),flush=True)
    if save:write(ANNUAL if mode=='annual' else RECENT,f'{asset}_signal_audit.csv',audit)
    return leg,signals,contexts,policy,pair,start,end


def load_baseline_signals(asset,kind,mode,start,end):
    if mode=='annual':
        mapping={'MA15':(u.OUT,'USER_MA15'),'M30':(u.OUT,'USER_MA15_30M'),
            'H1':(h.OUT,'USER_MA15_1H'),'H4':(h.OUT,'USER_MA15_4H'),'ER':(h.OUT,'USER_MA15_ER')}
        folder,profile=mapping[kind]
        raw=json.loads((folder/f'{asset}_{profile}_signals.json').read_text())
        return {int(t):s for t,s in raw.items()}
    if asset=='BTC':
        profile={'MA15':'NEW_MA','M30':'NEW_30M','H1':'NEW_1H','H4':'NEW_4H','ER':'NEW_ER'}[kind]
        raw=json.loads((ROOT/f'outputs/btc_nov12_nov13_comparison/{profile}_signals.json').read_text())
        return {x['signal_ms']:x['side'] for x in raw if start*1000<=x['signal_ms']<end*1000}
    return None


def validate():
    checks=[]
    for mode in ('recent','annual'):
        for asset in ('BTC','ETH'):
            _,baseline,_,_,_,start,end=prepare(asset,mode,.25,save=False)
            leg,new,ctx,policy,pair,_,_=prepare(asset,mode,THRESHOLD,save=True)
            for kind in PROFILES:
                old={t:s for t,s in baseline[kind].items() if start*1000<=t<end*1000}
                expected=load_baseline_signals(asset,kind,mode,start,end)
                if expected is not None:assert old==expected,('0.25 signal regression failed',mode,asset,kind)
                selected={t:s for t,s in new[kind].items() if start*1000<=t<end*1000}
                assert old.items()<=selected.items(),('Unexpected removed0.25 candidate',mode,asset,kind)
                checks.append(dict(mode=mode,asset=asset,profile=kind,old025_signals=len(old),new050_signals=len(selected),
                    matches_existing025_signal_files=expected is not None,
                    no_old_financial_replay=True,old_candidates_retained=True))
            assert policy.range_entry_bandwidth_pct==.50 and policy.trend_level_distance_pct==2.
    dump(OUT,'validation.json',dict(passed=True,checks=checks,core_ENTRY_threshold=.5,overlay_range_squeeze=.5,
        unchanged_range_current_cap=.5,unchanged_SR_ABS_distance=2.,old_code_files_not_edited=True))
    dump(OUT,'config.json',config());print('SQUEEZE050_VALIDATION_PASS',checks,flush=True)


def recent_market(asset,start,end,folder):
    old_data=ROOT/'outputs/retry_nov9_nov12/data'
    sources=[ROOT/'outputs/btc_nov12_nov13_comparison/data',old_data]
    filename=f'{asset}_1m_{start-60}_{end}_complete.json'
    rows=None
    for source in sources:
        file=source/filename
        if file.exists():rows=json.loads(file.read_text());break
    if rows is None:
        oldfile=old_data/f'{asset}_1m_{start-60}_{r.END}_complete.json'
        prefix=json.loads(oldfile.read_text())
        tail=r.complete_candles(asset,r.END,end,'1m')
        rows=prefix+[[t,*v] for t,v in tail.items()]
    assert [x[0] for x in rows]==list(range(start-60,end,60))
    for source in sources:
        for file in source.glob(f'{asset}_USDT_decimal_trades_*.json'):
            dst=r.DATA/file.name
            if not dst.exists():shutil.copy2(file,dst)
    dump(folder,f'{asset}_minute_sources.json',dict(reused_native_prefix=str(old_data),
        target_end=r.local_s(end),copied_complete_cached_prints=True,new_missing_prints_downloaded=True))
    return r.StrictMarket(asset,{t:tuple(v) for t,*v in rows})


def replay(asset,mode):
    folder=ANNUAL if mode=='annual' else RECENT
    set_runtime(folder)
    leg,signals,contexts,policy,pair,start,end=prepare(asset,mode)
    if mode=='annual':
        native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
    else:market=recent_market(asset,start,end,folder);cache=None
    books={kind:p.new_book(asset,kind) for kind in PROFILES}
    gen={kind:p.paired_generator(books[kind])(asset,leg=leg,signals=signals[kind],market=market,
       start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
       for kind in PROFILES}
    window=int(datetime(2026,11,12,tzinfo=r.TZ).timestamp());at_window={}
    for t in range(start,end,60):
        if mode=='recent' and t==window:at_window={k:p.state(b) for k,b in books.items()}
        for kind,g in gen.items():assert next(g)==t
        if t%86400==0:dump(folder,f'{asset}_progress.json',dict(time_beijing=r.local_s(t),
            books={k:dict(cash=b.cash,opens=b.stats['long']+b.stats['short'],closed=len(b.journal)) for k,b in books.items()}))
    outcomes=[]
    for kind,g in gen.items():
        try:next(g);raise RuntimeError('Executor overshot end')
        except StopIteration as stop:q=stop.value
        assert not q['approximated_minutes']
        book=books[kind];mark=float(market.market[end-60][3])
        result=dict(asset=asset,profile=kind,label=LABELS[kind],threshold_pct=THRESHOLD,
            starting_equity=500.,ending_equity=book.equity(mark),return_pct=100*(book.equity(mark)/500-1),
            period_beijing=[r.local_s(start),r.local_s(end)],opens=q['opens'],trades=book.journal,events=book.events,
            stats=dict(book.stats),state_at_end=p.state(book),final_mark_price=mark,
            boundary_probes=book.boundary_probes,no_OHLC_fallback=True,fee=0.,leverage=3.,slippage=.0002,
            policy=asdict(policy),original_ER=pair,config=config(),position_at_nov12_start=at_window.get(kind),
            verified_event_minutes=q['verified_minutes_with_trade_prints'])
        if mode=='recent':
            result['entries_since_nov12']=[dict(**v,opened_beijing=r.local_us(v['time_us']),signal_beijing=r.local_s((v['submitted_ms']-10000)/1000))
                for v in book.events if v['event']=='limit_touch_proxy_fill' and window*1e6<=v['time_us']<end*1e6]
            result['orders_since_nov12']=[v for v in book.events if v['event']=='order_sent' and window*1e6<=v['time_us']<end*1e6]
            result['floating_pnl']=book.position.marked(mark) if book.position else 0.
        dump(folder,f'{asset}_{kind}_result.json',result);np.save(folder/f'{asset}_{kind}_equity.npy',q['marks'])
        outcomes.append(dict(asset=asset,profile=kind,return_pct=result['return_pct'],opens=q['opens']))
        print(mode,asset,kind,'COMPLETE',outcomes[-1],flush=True)
    dump(folder,f'{asset}_status.json',dict(completed=True,results=outcomes,
        source='Binance official archives' if mode=='annual' else 'Gate public REST actual prints',
        validated_source_days=len(cache.sources) if cache else None))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['validate','annual','recent']);parser.add_argument('--asset',choices=['BTC','ETH']);args=parser.parse_args()
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.
    if args.mode=='validate':validate()
    else:
        assert args.asset is not None
        replay(args.asset,args.mode)


if __name__=='__main__':
    try:main()
    except Exception:
        print(traceback.format_exc(),flush=True);raise
