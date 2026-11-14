"""Accounting attribution only: no strategy parameters are selected or changed."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
import csv
import json
from pathlib import Path
import zipfile

import numpy as np
import binance_inputs as d

OUT=Path(__file__).resolve().parent
TZ=timezone(timedelta(hours=8))
REASONS={
 'ER_TRANSITION_PAUSED':'ER过渡期暂停',
 'ER_DIRECTION_OPPOSES_ENTRY':'ER方向与本次信号相反',
 'RANGE_CURRENT_WIDTH_OVER_0_50':'ER震荡分支当前带宽超过0.50%',
 'RANGE_DENSITY_FAILED':'ER震荡分支密集条件不符',
 'TREND_SMA5_MACD_CONFIRM_FAILED':'趋势分支SMA5/MACD确认未通过',
 'TREND_LEVEL_VOLUME_RETEST_FAILED':'趋势分支距离/放量/回踩均未通过',
 'SIX_LINE_ALIGNMENT_FAILED':'不足六线同向',
 'CORE_SIGNAL_ABSENT':'原始基础信号不存在',
 'OCCUPIED_POSITION':'另一版本已有持仓，受此前交易路径影响',
 'OCCUPIED_PENDING_ORDER':'另一版本已有挂单，受此前交易路径影响',
 'SENT_BUT_NOT_FILLED':'另一版本已发挂单但未成交',
 'ELIGIBLE_EXECUTION_NOT_CLASSIFIED':'有信号，执行原因需进一步核对',
}


def local(us):
    return datetime.fromtimestamp(us/1e6,TZ).isoformat(timespec='milliseconds') if us else ''


def write(name,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def normalized(result):
    rows=[]
    for t in result['trades']:
        side=1 if t['side']=='LONG' else -1
        row=dict(asset=result['asset'],profile=result['profile'],status='CLOSED',
            signal_ms=int(t['signal_close_ms']),signal_beijing=local(t['signal_close_ms']*1000),
            side=t['side'],filled_us=t['opened_us'],filled_beijing=local(t['opened_us']),
            closed_us=t['closed_us'],closed_beijing=local(t['closed_us']),
            entry=t['entry'],exit_or_mark=t['exit'],quantity=t['quantity'],net_usdt=t['net'],
            rung=t['rung'],reason=t['reason'],opening_cash=t['opening_sleeve_cash_usdt'],
            price_return_pct=side*(t['exit']/t['entry']-1)*100,
            normalized_1500_pnl_usdt=1500*side*(t['exit']/t['entry']-1))
        rows.append(row)
    state=result['state_at_end']
    if p:=state['position']:
        o=p['order'];entry=o['price'];mark=result['final_mark_price'];side=o['side']
        rows.append(dict(asset=result['asset'],profile=result['profile'],status='OPEN_MARK',
            signal_ms=o['time']-10000,signal_beijing=local((o['time']-10000)*1000),
            side='LONG' if side==1 else 'SHORT',filled_us=state['position_opened_us'],
            filled_beijing=local(state['position_opened_us']),closed_us='',closed_beijing='',
            entry=entry,exit_or_mark=mark,quantity=o['qty'],net_usdt=side*(mark-entry)*o['qty'],
            rung=p['rung'],reason='OPEN_AT_WINDOW_END',opening_cash=p['opening_cash'],
            price_return_pct=100*side*(mark/entry-1),normalized_1500_pnl_usdt=1500*side*(mark/entry-1)))
    assert abs(sum(t['net_usdt'] for t in rows)-(result['ending_equity']-500))<1e-7
    return rows


def key(row):return row['signal_ms'],row['side']


def explain(t,other,audit,results):
    a=audit[t['signal_ms']]
    code=a[f'{other}_reject_reason']
    state=json.loads(a[f'{other}_book_before'])
    eligible=int(a[f'{other}_side'])==(1 if t['side']=='LONG' else -1)
    sent=[e for e in results[other]['events'] if e['event']=='order_sent'
            and e['time_us']==(t['signal_ms']+10000)*1000]
    if eligible:
        if sent:code='SENT_BUT_NOT_FILLED'
        elif state['position']:code='OCCUPIED_POSITION'
        elif state['pending_order']:code='OCCUPIED_PENDING_ORDER'
        else:code='ELIGIBLE_EXECUTION_NOT_CLASSIFIED'
    else:
        assert code!='ELIGIBLE',(t,a)
    blocker=state['position']['order'] if state['position'] else state['pending_order']
    return dict(**t,ER_regime=a['ER_regime'],MA_regime=a['MA_regime'],
         other_version=other,other_has_eligible_signal=eligible,other_reason=code,
         other_reason_zh=REASONS.get(code,code),other_was_occupied=bool(blocker),
         blocker_signal_beijing=local((blocker['time']-10000)*1000) if blocker else '',
         blocker_side=('LONG' if blocker['side']==1 else 'SHORT') if blocker else '',
         blocker_entry=blocker['price'] if blocker else '')


def drawdown(values,seed):
    values=np.r_[seed,values];return float(np.max(100*(1-values/np.maximum.accumulate(values))))


def process(assets):
    summaries=[];alltrades=[];paired=[];only={'ER':[],'MA':[]};accounts=[];monthly=[]
    signal_summary=[];causes=[];boundary=[];regressions={};combined={}
    for asset in assets:
        results={p:json.loads((OUT/f'{asset}_{p}_result.json').read_text()) for p in ('ER','MA')}
        trades={p:normalized(q) for p,q in results.items()}
        maps={p:{key(t):t for t in trades[p]} for p in trades}
        assert all(len(maps[p])==len(trades[p]) for p in maps)
        with (OUT/f'{asset}_signal_audit.csv').open(encoding='utf-8-sig') as f:
            audit={int(row['signal_ms']):row for row in csv.DictReader(f)}
        eq={p:np.load(OUT/f'{asset}_{p}_equity.npy') for p in results}
        for p,q in results.items():
            assert len(eq[p])==(d.END-d.START)//60
            assert abs(float(eq[p][-1])-q['ending_equity'])<1e-8
            combined[p]=combined.get(p,np.zeros(len(eq[p])))+eq[p]
            count=len(trades[p]);closed=q['trades'];h=sum(t['reason']=='hard_stop' for t in closed)
            summaries.append(dict(asset=asset,profile=p,return_pct=q['return_pct'],
                ending_equity=q['ending_equity'],opens=count,closed=len(closed),hard_stops=h,
                max_drawdown_minute_pct=drawdown(eq[p],500.),
                realized_pnl_usdt=sum(t['net'] for t in closed),
                open_mark_pnl_usdt=sum(t['net_usdt'] for t in trades[p] if t['status']=='OPEN_MARK')))
            alltrades.extend(trades[p]);boundary.extend(q['boundary_probes'])
        common=maps['ER'].keys()&maps['MA'].keys()
        extra={p:maps[p].keys()-common for p in maps}
        common_delta=0.;same_execution_delta=0.;different_execution_delta=0.;pathdiff=[]
        for k in sorted(common):
            a,b=maps['ER'][k],maps['MA'][k]
            fields=('filled_us','closed_us','entry','exit_or_mark','rung','reason','status')
            same=all(a[f]==b[f] for f in fields)
            row=dict(asset=asset,signal_beijing=a['signal_beijing'],side=a['side'],
                     same_execution=same,ER_quantity=a['quantity'],MA_quantity=b['quantity'],
                     ER_pnl=a['net_usdt'],MA_pnl=b['net_usdt'],pnl_delta=b['net_usdt']-a['net_usdt'],
                     ER_filled=a['filled_beijing'],MA_filled=b['filled_beijing'],
                     ER_exit=a['closed_beijing'],MA_exit=b['closed_beijing'],
                     ER_entry=a['entry'],MA_entry=b['entry'],ER_exit_price=a['exit_or_mark'],MA_exit_price=b['exit_or_mark'])
            paired.append(row);common_delta+=row['pnl_delta']
            if not same:
                pathdiff.append(row);different_execution_delta+=row['pnl_delta']
            else:same_execution_delta+=row['pnl_delta']
        for p in ('ER','MA'):
            other='MA' if p=='ER' else 'ER'
            added=[explain(maps[p][k],other,audit,results) for k in sorted(extra[p])]
            only[p].extend(added)
            grouped=defaultdict(list)
            for t in added:grouped[t['other_reason']].append(t)
            for code,ts in grouped.items():
                causes.append(dict(asset=asset,version_only=p,other_reason=code,
                    reason_zh=REASONS.get(code,code),count=len(ts),wins=sum(t['net_usdt']>0 for t in ts),
                    pnl_usdt=sum(t['net_usdt'] for t in ts),
                    normalized_1500_pnl_usdt=sum(t['normalized_1500_pnl_usdt'] for t in ts)))
        maonly=sum(maps['MA'][k]['net_usdt'] for k in extra['MA'])
        eronly=sum(maps['ER'][k]['net_usdt'] for k in extra['ER'])
        actual=results['MA']['ending_equity']-results['ER']['ending_equity']
        residual=actual-(maonly-eronly+common_delta)
        assert abs(residual)<1e-7
        accounts.append(dict(asset=asset,ER_opens=len(maps['ER']),MA_opens=len(maps['MA']),
            common_filled_signals=len(common),MA_only_count=len(extra['MA']),ER_only_count=len(extra['ER']),
            MA_only_pnl_usdt=maonly,ER_only_pnl_usdt=eronly,common_trade_delta_usdt=common_delta,
            same_execution_quantity_path_delta_usdt=same_execution_delta,
            different_execution_delta_usdt=different_execution_delta,
            equity_delta_usdt=actual,accounting_residual_usdt=residual,
            common_execution_differences=len(pathdiff)))
        for month in range(1,11):
            begin=int(datetime(2026,month,1,tzinfo=TZ).timestamp())
            end=int(datetime(2026,month+1,1,tzinfo=TZ).timestamp())
            row=dict(asset=asset,month=f'2026-{month:02}')
            for p in ('ER','MA'):
                opening=500. if begin==d.START else float(eq[p][(begin-d.START)//60-1])
                ending=float(eq[p][(end-d.START)//60-1])
                row[p+'_opening_equity']=opening;row[p+'_ending_equity']=ending
                row[p+'_return_pct']=100*(ending/opening-1);row[p+'_pnl_usdt']=ending-opening
                row[p+'_opens']=sum(begin*1e6<=t['filled_us']<end*1e6 for t in trades[p])
            row['MA_minus_ER_pnl_usdt']=row['MA_pnl_usdt']-row['ER_pnl_usdt'];monthly.append(row)
        paircounts=Counter()
        for row in audit.values():
            er=int(row['ER_side']);ma=int(row['MA_side'])
            paircounts['both' if er and ma else 'ER_only' if er else 'MA_only']+=1
        signal_summary.append(dict(asset=asset,**paircounts))
        regressions[asset]=json.loads((OUT/f'{asset}_regression.json').read_text())
    for p in ('ER','MA'):
        summaries.append(dict(asset='COMBINED',profile=p,
            return_pct=100*(float(combined[p][-1])/(500*len(assets))-1),ending_equity=float(combined[p][-1]),
            opens=sum(s['opens'] for s in summaries if s['asset'] in assets and s['profile']==p),
            hard_stops=sum(s['hard_stops'] for s in summaries if s['asset'] in assets and s['profile']==p),
            max_drawdown_minute_pct=drawdown(combined[p],500*len(assets))))
    for month in range(1,11):
        row=dict(asset='COMBINED',month=f'2026-{month:02}')
        selected=[m for m in monthly if m['month']==row['month'] and m['asset'] in assets]
        for p in ('ER','MA'):
            opening=sum(m[p+'_opening_equity'] for m in selected);ending=sum(m[p+'_ending_equity'] for m in selected)
            row[p+'_opening_equity']=opening;row[p+'_ending_equity']=ending
            row[p+'_return_pct']=100*(ending/opening-1);row[p+'_pnl_usdt']=ending-opening
            row[p+'_opens']=sum(m[p+'_opens'] for m in selected)
        row['MA_minus_ER_pnl_usdt']=row['MA_pnl_usdt']-row['ER_pnl_usdt'];monthly.append(row)
    files={'annual_asset_summary.csv':summaries,'all_trades.csv':alltrades,
           'paired_trades.csv':paired,'MA_only_trades.csv':only['MA'],'ER_only_trades.csv':only['ER'],
           'attribution.csv':accounts,'monthly_comparison.csv':monthly,
           'different_trade_causes.csv':causes,'signal_counts.csv':signal_summary,
           'boundary_probes.csv':boundary,
           'largest_extra_losses.csv':sorted([t for t in only['MA'] if t['net_usdt']<0],key=lambda t:t['net_usdt'])[:15],
           'largest_missed_winners.csv':sorted([t for t in only['ER'] if t['net_usdt']>0],key=lambda t:-t['net_usdt'])[:15],
           'common_execution_differences.csv':[t for t in paired if not t['same_execution']]}
    for name,rows in files.items():write(name,rows)
    report=dict(annual=summaries,attribution=accounts,causes=causes,signals=signal_summary,
            regression_against_prior_returns=regressions,earliest_changed_filled_trades={
                p:sorted(only[p],key=lambda t:t['filled_us'])[:3] for p in ('ER','MA')},
            largest_extra_losses=files['largest_extra_losses.csv'][:8],
            largest_missed_winners=files['largest_missed_winners.csv'][:8],
            common_execution_differences=files['common_execution_differences.csv'],
            known_exact_submit_boundary_observations=len(boundary),
            all_windows_include_open_position_mark_to_market=True,
            attribution_is_accounting_not_parameter_optimization=True)
    d.dump(OUT/'attribution.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--asset',choices=['BTC','ETH']);args=parser.parse_args()
    process([args.asset] if args.asset else ['BTC','ETH'])
