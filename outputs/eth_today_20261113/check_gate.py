"""Check new six-MA ETH signals around08:00 using same-venue Gate candles.

Binance live futures API returned451. This is explicitly Gate evidence, not a
claim of the screenshot venue's exact fills or the user's account positions.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import inspect
import json
import sys

import numpy as np

ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'outputs/user_ma_six_2026'))
import experiment as u
r=u.r;d=u.d
DATA=OUT/'data';DATA.mkdir(exist_ok=True)


def main():
    now=int(datetime.now(timezone.utc).timestamp());end=now//900*900
    r.OUT=OUT;r.DATA=DATA;r.RESPONSES=DATA/'gate_responses';r.RESPONSES.mkdir(exist_ok=True)
    oldfile=ROOT/'outputs/retry_nov9_nov12/data/ETH_15m.csv'
    old=np.loadtxt(oldfile,delimiter=',',skiprows=1);old[:,0]/=1000
    first_new=int(old[-1,0])+900
    added=r.complete_candles('ETH',first_new,end,'15m')
    recent=np.array([[t,*v] for t,v in added.items()]);rows=np.concatenate((old,recent))
    assert np.array_equal(rows[:,0],np.arange(rows[0,0],end,900))
    file=DATA/'ETH_Gate_15m_extended.csv'
    np.savetxt(file,np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,
        header='timestamp,open,high,low,close,volume',comments='')
    leg=u.user_build(file,(r.START-30*86400)*1000,end*1000)
    prior=json.loads(r.selected.FAST_WINDOW_REPORT.read_text());policy=r.RegimeOverlay(**prior['policy'])
    pair=tuple(tuple(x) for x in prior['cases'][r.selected.MODE]['er_windows_and_thresholds'])
    profiles={};series={}
    profiles['USER_MA15']=r.ma_schedules('ETH',leg,price_file=file,include_gate_confirmation=True,
        regime_thresholds=pair,use_entry_crosses=False)
    profiles['USER_MA15_ER']=r.regime.market_schedules('ETH',leg,price_file=file,include_gate_confirmation=True,
        regime_thresholds=pair,use_entry_crosses=False)
    for minutes in (30,60,240):
        size=minutes//15;n=len(rows)//size;blocks=rows[:n*size].reshape(n,size,6)
        assert np.all(blocks[:,0,0]%(minutes*60)==0)
        closes=blocks[:,-1,4];lines=np.stack([r.model.sma(closes,n) for n in u.PERIODS])
        closed=(blocks[:,-1,0]+900).astype(np.int64)*1000;states=u.directions(lines)
        def combined_state(time,up,down):
            low=1 if up==6 else -1 if down==6 else 0;high,i=u.state_at(closed,states,time)
            return {1:'up',-1:'down',0:'range'}[low] if low==high else 'transition'
        source=inspect.getsource(r.regime.market_schedules)
        needle='        state, _, _ = regimes.get(time // HOUR * HOUR, ("transition", 0, 0))\n';assert source.count(needle)==1
        scope=dict(r.regime.__dict__);scope['combined_state']=combined_state
        exec(compile(source.replace(needle,'        state = combined_state(time, leg.up[i], leg.down[i])\n'),
            '<new six SMA closed higher timeframe for current Gate ETH>','exec'),scope)
        name=f'USER_MA15_{minutes}M'
        profiles[name]=scope['market_schedules']('ETH',leg,price_file=file,include_gate_confirmation=True,
            regime_thresholds=pair,use_entry_crosses=False)
        series[name]=(closed.copy(),states.copy())
    signals={name:r.stacked_signals(sch['baseline'],ctx,policy) for name,(sch,ctx) in profiles.items()}
    first=int(datetime(2026,11,13,7,tzinfo=r.TZ).timestamp())
    last=int(datetime(2026,11,13,9,15,tzinfo=r.TZ).timestamp())
    details=[]
    for t in range(first,last+1,900):
        ms=t*1000;i=int((ms-r.regime.BAR-leg.first)//r.regime.BAR);bar=leg.bars[ms-r.regime.BAR]
        common=dict(signal_beijing=r.local_s(t),signal_ms=ms,close=bar.c,
            close_below_all_six=bool(leg.below_band[i]),down_lines=int(leg.down[i]),
            MACD_hist=float(leg.histogram[i]),current_width_pct=float(leg.width[i]),min96_width_pct=float(leg.squeeze[96][i]))
        failures=[]
        if not common['close_below_all_six']:failures.append('收盘未低于全部六线')
        if common['down_lines']!=6:failures.append('不足六线向下')
        if common['MACD_hist']>=0:failures.append('DIF未低于DEA')
        if common['min96_width_pct']>.25:failures.append('最近96根最小带宽大于0.25%')
        for name,(schedule,ctx) in profiles.items():
            row=dict(**common,profile=name,regime=ctx[ms]['regime'],short_signal=signals[name].get(ms)==-1,
                any_signal_side=signals[name].get(ms,0),base_side=schedule['baseline'].get(ms,0),
                primary_failures='；'.join(failures),gate_reason=u.p.reason(schedule['baseline'].get(ms,0),ctx[ms],policy),
                gate_confirmation=json.dumps(ctx[ms].get('gate_confirmation'),ensure_ascii=False))
            if name in series:
                closed,states=series[name];s,hi=u.state_at(closed,states,ms)
                row.update(higher_state={1:'up',-1:'down',0:'range',9:'unavailable'}[s],
                    latest_higher_close=r.local_s(closed[hi]/1000) if hi>=0 else '')
            if row['short_signal']:assert not failures
            details.append(row)
    u.p.csv_out(OUT/'signal_check.csv',details)
    eight=[x for x in details if 'T08:' in x['signal_beijing']]
    receipts=dict(source='Gate USDT perpetual public REST',symbol='ETH_USDT',
        checked_date_beijing='2026-11-13',checked_signal_closes='07:00 through09:15 Beijing',
        now_utc=datetime.now(timezone.utc).isoformat(),last_complete15m_close=r.local_s(end),last_complete_price=float(rows[-1,4]),
        six_averages=list(u.PERIODS),all_SMA=True,compare_each_own_3bars_ago=True,
        old_source=str(oldfile),old_source_sha256=hashlib.file_digest(oldfile.open('rb'),'sha256').hexdigest(),
        Binance_live_API='FAILED_HTTP451; not silently substituted as Binance',
        direct_screenshot_venue_exact_result='UNVERIFIED',actual_account_positions='UNVERIFIED',
        actual_fill_replay_performed=False,raw_Gate_receipts=str(OUT/'api_requests.jsonl'),
        eight_oclock_results=eight,
        eligible_short_signals_07_to0915=[{k:x[k] for k in ('profile','signal_beijing','close')} for x in details if x['short_signal']])
    d.dump(OUT/'check.json',receipts)
    print(json.dumps(receipts,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
