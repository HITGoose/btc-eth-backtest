"""BTC comparison Nov12 through Nov13 noon, preserve prior book states.

Old MA/ER resume the verified09:32:32 snapshot, filtering already-replayed
events in the first partial minute. New-SMA profiles start Nov9 with the same
500 seed and carry into Nov12; they are not reset at the requested window.
All use Gate public candles/prints and the original financial execution code.
"""
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import shutil
import sys
import traceback

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/user_ma_six_2026'))
import experiment as u
p=u.p;r=u.r;d=u.d
OUT=Path(__file__).resolve().parent
DATA=OUT/'data';DATA.mkdir(parents=True,exist_ok=True)
HISTORY=ROOT/'outputs/retry_nov9_nov12'
WINDOW_START=int(datetime(2026,11,12,tzinfo=r.TZ).timestamp())
CUTOFF=int(datetime(2026,11,13,12,tzinfo=r.TZ).timestamp())
END15=CUTOFF+900
LABELS={'OLD_MA':'旧均线分类版','OLD_ER':'旧ER版','NEW_MA':'新六MA：单15分钟',
    'NEW_30M':'新六MA：＋30分钟','NEW_1H':'新六MA：＋1小时',
    'NEW_4H':'新六MA：＋4小时','NEW_ER':'新六MA入场＋ER'}


def dump(name,value):d.dump(OUT/name,value)


def setup():
    r.OUT=OUT;r.DATA=DATA;r.RESPONSES=DATA/'responses';r.RESPONSES.mkdir(exist_ok=True)
    r.public.CACHE=DATA;p.OUT=OUT
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file and Path(file).resolve().is_relative_to(ROOT/'work') and hasattr(module,'FEE'):module.FEE=0.


def prepare():
    assert int(datetime.now(timezone.utc).timestamp())>=CUTOFF
    oldfile=HISTORY/'data/BTC_15m.csv'
    old=np.loadtxt(oldfile,delimiter=',',skiprows=1);old[:,0]/=1000
    first=int(old[-1,0])+900
    raw=r.audited_json('candlesticks',contract='BTC_USDT',interval='15m',**{'from':first,'to':END15-1})
    added=np.array(sorted([[int(x['t']),*(float(x[k]) for k in ('o','h','l','c','v'))]
         for x in raw if first<=int(x['t'])<END15],key=lambda x:x[0]))
    assert np.array_equal(added[:,0],np.arange(first,END15,900))
    rows=np.concatenate((old,added));assert np.array_equal(rows[:,0],np.arange(rows[0,0],END15,900))
    file=DATA/'BTC_Gate_extended_15m.csv'
    np.savetxt(file,np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,
        header='timestamp,open,high,low,close,volume',comments='')
    changed=rows.copy();price=changed[-1,4]*1.5;changed[-1,1:5]=price;changed[-1,5]*=10
    np.savetxt(DATA/'unused_padding_probe.csv',np.column_stack((changed[:,0]*1000,changed[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,
        header='timestamp,open,high,low,close,volume',comments='')
    dump('inputs.json',dict(symbol='BTC_USDT',source='Gate public REST',cutoff_beijing=r.local_s(CUTOFF),
        cutoff_end_exclusive=True,window_start_beijing=r.local_s(WINDOW_START),
        old_source=str(oldfile),old_source_sha256=hashlib.file_digest(oldfile.open('rb'),'sha256').hexdigest(),
        unused_padding_open=r.local_s(CUTOFF),forming_padding_excluded_from_signals=True,
        price_file=str(file),new_profiles_seed_beijing=r.local_s(r.START),new_profiles_seed=500.,
        old_profiles_resume_from_saved_snapshot=True,not_reset_at_nov12=True,
        screenshot_Binance_exact_results='UNVERIFIED: live Binance API returnedHTTP451 in previous check'))
    print('BTC_INPUTS_READY',r.local_s(CUTOFF),flush=True)


def high_series(rows,minutes):
    rows=rows[rows[:,0]+900<=CUTOFF]
    size=minutes//15;n=len(rows)//size;blocks=rows[:n*size].reshape(n,size,6)
    assert np.all(blocks[:,0,0]%(minutes*60)==0)
    closes=blocks[:,-1,4];values=np.stack([r.model.sma(closes,n) for n in u.PERIODS])
    return (blocks[:,-1,0]+900).astype(np.int64)*1000,u.directions(values)


def higher_schedule(leg,file,pair,closed,states):
    def combined_state(time,up,down):
        low=1 if up==6 else -1 if down==6 else 0;high,_=u.state_at(closed,states,time)
        return {1:'up',-1:'down',0:'range'}[low] if low==high else 'transition'
    source=inspect.getsource(r.regime.market_schedules)
    needle='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n';assert source.count(needle)==1
    scope=dict(r.regime.__dict__);scope['combined_state']=combined_state
    exec(compile(source.replace(needle,'        state = combined_state(time, leg.up[i], leg.down[i])\n'),
        '<same new six-SMA closed higher classification>','exec'),scope)
    return scope['market_schedules']('BTC',leg,price_file=file,include_gate_confirmation=True,
        regime_thresholds=pair,use_entry_crosses=False)


def signals_for(file):
    prior=json.loads((HISTORY/'MA_9_12_BTC_result.json').read_text())
    policy=r.RegimeOverlay(**prior['policy']);pair=tuple(tuple(x) for x in prior['original_ER'])
    assert policy.pause_transition and policy.trend_level_distance_pct==2.
    old=r.model.build(file,r.WARM*1000,END15*1000);new=u.user_build(file,r.WARM*1000,END15*1000)
    opts=dict(price_file=file,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
    sources={'OLD_MA':r.ma_schedules('BTC',old,**opts),'OLD_ER':r.regime.market_schedules('BTC',old,**opts),
       'NEW_MA':r.ma_schedules('BTC',new,**opts),'NEW_ER':r.regime.market_schedules('BTC',new,**opts)}
    raw=np.loadtxt(file,delimiter=',',skiprows=1);raw[:,0]/=1000
    for name,minutes in [('NEW_30M',30),('NEW_1H',60),('NEW_4H',240)]:
        closed,states=high_series(raw,minutes);sources[name]=higher_schedule(new,file,pair,closed,states)
    signal={name:r.stacked_signals(sch['baseline'],ctx,policy) for name,(sch,ctx) in sources.items()}
    return old,new,signal,sources,policy,pair


def validate():
    file=DATA/'BTC_Gate_extended_15m.csv'
    old,new,sig,ctx,policy,pair=signals_for(file)
    _,_,perturbed,_,_,_=signals_for(DATA/'unused_padding_probe.csv')
    for name in sig:
        usable={t:s for t,s in sig[name].items() if t<=CUTOFF*1000}
        probe={t:s for t,s in perturbed[name].items() if t<=CUTOFF*1000}
        assert usable==probe,('Unused forming padding changed signal',name)
        dump(f'{name}_signals.json',[dict(signal_ms=t,signal_beijing=r.local_s(t/1000),side=s)
               for t,s in sorted(usable.items()) if r.START*1000<=t])
    for name,label in [('OLD_MA','MA_9_12'),('OLD_ER','ER_9_12')]:
        prior=json.loads((HISTORY/f'{label}_BTC_signals.json').read_text())
        expected={x['signal_ms']:x['side'] for x in prior}
        prefix={t:s for t,s in sig[name].items() if r.START*1000<=t<r.END*1000}
        assert prefix==expected,('Old verified prefix changed',name)
    audit=[]
    for name,(sch,contexts) in ctx.items():
        leg=old if name.startswith('OLD') else new
        for t in range(WINDOW_START,CUTOFF+1,900):
            ms=t*1000;i=int((ms-r.regime.BAR-leg.first)//r.regime.BAR)
            audit.append(dict(profile=name,label=LABELS[name],signal_beijing=r.local_s(t),
                side=sig[name].get(ms,0),regime=contexts[ms]['regime'],close=leg.bars[ms-r.regime.BAR].c,
                up_lines=int(leg.up[i]),down_lines=int(leg.down[i]),MACD_hist=float(leg.histogram[i]),
                current_width_pct=float(leg.width[i]),min96_width_pct=float(leg.squeeze[96][i]),
                base_side=sch['baseline'].get(ms,0),gate_reason=p.reason(sch['baseline'].get(ms,0),contexts[ms],policy)))
    p.csv_out(OUT/'signal_audit.csv',audit)
    dump('validation.json',dict(passed=True,old_signal_prefix_unchanged=True,
        forming_padding_perturbation_all_seven_profiles=True,higher_only_uses_complete_bars=True,
        no_parameter_changes=True,signals_in_window={n:sum(WINDOW_START*1000<=t<CUTOFF*1000 for t in ss)
                                                  for n,ss in sig.items()},
        signals_from_nov9={n:sum(r.START*1000<=t<CUTOFF*1000 for t in ss) for n,ss in sig.items()}))
    print('BTC_SIGNAL_VALIDATION_PASS',json.loads((OUT/'validation.json').read_text()),flush=True)


class WindowMarket:
    def __init__(self,base,begin):
        self.base=base;self.begin=begin;self.market=base.market;self.close_discrepancies=base.close_discrepancies
    def events(self,*args,**kw):
        for t,price,poll in self.base.events(*args,**kw):
            if t>=self.begin:yield t,price,poll


def restore(name,label,latest):
    snap=json.loads((latest/f'{label}_result.json').read_text())
    earlier=json.loads((HISTORY/f'{label}_BTC_result.json').read_text())
    book=p.new_book('BTC',name);book.cash=snap['cash'];book.realized=book.cash-500.
    book.stats=Counter(snap['stats']);book.journal=[dict(x) for x in snap['trades']]
    book.events=[dict(x) for x in earlier['events']]+[dict(x) for x in snap['events_after_resume']]
    if snap['current_position']:
        pos=dict(snap['current_position']);pos['order']=r.model.Order(**pos['order'])
        book.position=r.model.Position(**pos);book.position.opened_us=snap['current_position_opened_us']
    if snap['current_order']:book.order=r.model.Order(**snap['current_order'])
    begin=datetime.fromisoformat(snap['cutoff_beijing']).timestamp()
    return book,begin,snap,earlier


def replay():
    old,new,signals,contexts,policy,pair=signals_for(DATA/'BTC_Gate_extended_15m.csv')
    newest=json.loads((ROOT/'outputs/btc_followup_20261113/latest.json').read_text())
    latest=Path(newest['directory'])
    # Reuse only completed cached trade minutes. Never reuse the former partial last minute.
    resume=datetime.fromisoformat(newest['cutoff_beijing']).timestamp();partial=int(resume)//60*60
    copied=0
    for directory in [HISTORY/'data',latest/'data']:
        for src in directory.glob('BTC_USDT_decimal_trades_*.json'):
            start=int(src.stem.split('_')[-2])
            if start>=partial:continue
            dst=DATA/src.name
            if not dst.exists():shutil.copy2(src,dst);copied+=1
    minutes=r.complete_candles('BTC',r.START-60,CUTOFF,'1m')
    base_market=r.StrictMarket('BTC',minutes)
    results=[]
    for name in LABELS:
        original=None;prior=None;initial_window=None
        if name.startswith('OLD'):
            label='MA_9_12' if name=='OLD_MA' else 'ER_9_12'
            book,begin,original,prior=restore(name,label,latest)
            leg=old
            # Both verified prior ending positions were opened on Nov11, before requested window.
            pos=prior['ending_position']
            if pos and prior['ending_position_opened_us']<WINDOW_START*1e6:
                initial_window=dict(side='SHORT' if pos['order']['side']==-1 else 'LONG',entry=pos['order']['price'],
                    opened_beijing=r.local_us(prior['ending_position_opened_us']),source='Previously verified carried position')
        else:
            book=p.new_book('BTC',name);begin=r.START;leg=new
        starting=p.state(book);starting_trade_count=len(book.journal);starting_event_count=len(book.events)
        view=WindowMarket(base_market,begin)
        start_minute=int(begin)//60*60
        gen=p.paired_generator(book)('BTC',leg=leg,signals=signals[name],market=view,
            start=start_minute*1000,end=CUTOFF*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
        for minute in range(start_minute,CUTOFF,60):
            if minute==WINDOW_START and not name.startswith('OLD'):initial_window=p.state(book)
            assert next(gen)==minute
        try:next(gen);raise RuntimeError('Executor overshot cutoff')
        except StopIteration as stop:q=stop.value
        assert not q['approximated_minutes']
        mark=float(minutes[CUTOFF-60][3])
        entries=[dict(**event,opened_beijing=r.local_us(event['time_us']),signal_beijing=r.local_s((event['submitted_ms']-10000)/1000))
           for event in book.events if event['event']=='limit_touch_proxy_fill' and WINDOW_START*1e6<=event['time_us']<CUTOFF*1e6]
        sends=[event for event in book.events if event['event']=='order_sent' and WINDOW_START*1e6<=event['time_us']<CUTOFF*1e6]
        closed=[trade for trade in book.journal if WINDOW_START*1e6<=trade['closed_us']<CUTOFF*1e6]
        result=dict(profile=name,label=LABELS[name],source='Gate public REST actual prints',
            common_model_seed_beijing=r.local_s(r.START),seed=500.,requested_window_beijing=[r.local_s(WINDOW_START),r.local_s(CUTOFF)],
            resume_beijing=r.local_s(begin),replayed_from_minute=r.local_s(start_minute),
            first_partial_minute_filters_already_processed_events=True,
            initial_resume_state=starting,position_at_window_start=initial_window,
            short_signals_in_window=[r.local_s(t/1000) for t,s in signals[name].items() if WINDOW_START*1000<=t<CUTOFF*1000 and s==-1],
            long_signals_in_window=[r.local_s(t/1000) for t,s in signals[name].items() if WINDOW_START*1000<=t<CUTOFF*1000 and s==1],
            new_entries_in_window=entries,orders_sent_in_window=sends,closed_in_window=closed,
            current_position=asdict(book.position) if book.position else None,
            current_position_opened_us=getattr(book.position,'opened_us',None) if book.position else None,
            current_order=asdict(book.order) if book.order else None,cash=book.cash,ending_equity=book.equity(mark),
            floating_pnl=book.position.marked(mark) if book.position else 0.,mark_price=mark,
            trades=book.journal,events=book.events,stats=dict(book.stats),
            event_changes_this_execution=book.events[starting_event_count:],closed_changes_this_execution=book.journal[starting_trade_count:],
            verified_tape_minutes=q['verified_minutes_with_trade_prints'],no_OHLC_fallback=True,
            fee=0.,leverage=3.,slippage=.0002,policy=asdict(policy),original_ER=pair,
            old_definition=['SMA20','SMA60','SMA120','EMA20','EMA60','EMA120'] if name.startswith('OLD') else None,
            new_definition=['SMA'+str(n) for n in u.PERIODS] if name.startswith('NEW') else None,
            original_known_submit_boundary_preserved=True,real_order_queue_partial_fills='UNVERIFIED',
            real_user_account='UNVERIFIED',screenshot_Binance_exact_execution='UNVERIFIED_HTTP451')
        dump(f'{name}_result.json',result);results.append(result)
        print(name,'COMPLETE','new_entries',len(entries),'position',result['current_position'],'floating',result['floating_pnl'],flush=True)
    dump('results.json',dict(completed=True,source='Gate BTC_USDT',cutoff_beijing=r.local_s(CUTOFF),
        requested_start_beijing=r.local_s(WINDOW_START),not_reset_at_nov12=True,reused_complete_trade_minutes=copied,results=results))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','validate','replay']);args=parser.parse_args()
    setup()
    if args.mode=='prepare':prepare()
    elif args.mode=='validate':validate()
    else:replay()


if __name__=='__main__':
    try:main()
    except Exception:
        dump('failure.json',dict(completed=False,error=traceback.format_exc()));raise
