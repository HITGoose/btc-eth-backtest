from pathlib import Path
from datetime import datetime,timezone,timedelta
import importlib.util,json,csv,collections
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('cross_v2',ROOT/'outputs/adaptive_risk_exit_v2/worker.py');v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v);p=v.e.p;r=v.e.r
TZ=timezone(timedelta(hours=8))
def fmt(ms):return datetime.fromtimestamp(ms/1000,TZ).strftime('%Y-%m-%d %H:%M:%S')
def save(name,rows):
 fields=list(dict.fromkeys(k for q in rows for k in q)) or ['none']
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
rows=[];conditions=[];coverage=[]
for dataset in list(range(2020,2027))+['2026NOV']:
 year=2026 if dataset=='2026NOV' else dataset
 folder=ROOT/(f'outputs/adaptive_risk_exit_v2/{year}' if year in (2024,2025) else f'outputs/adaptive_risk_exit_v2_extended/{year}')
 data=ROOT/('outputs/er_partial_2020/data' if year==2020 else 'outputs/attribution_2026/data' if year==2026 else f'outputs/other_years_050/{year}/data')
 if dataset=='2026NOV':
  folder=ROOT/'outputs/nov9_today_simultaneous/2026';data=ROOT/'outputs/nov9_today_simultaneous/data'
 books={a:{n:json.loads((folder/a/f'{n}_result.json').read_text()) for n in ('CONTROL','DYNAMIC')} for a in ('BTC','ETH')}
 start,end=[int(datetime.fromisoformat(x).timestamp()) for x in books['BTC']['CONTROL']['period']]
 window='2026年11月1日至13日08:00' if dataset=='2026NOV' else f'{year}年1—10月' if year==2026 else '2020年2月16日至年底' if year==2020 else str(year)+'全年'
 coverage.append(dict(year=year,period=window,start=fmt(start*1000),end_exclusive=fmt(end*1000)))
 prepared={a:p.prepare(a,data/f'{a}_15m.csv',start,end) for a in ('BTC','ETH')}
 for n,label in [('CONTROL','原ER'),('DYNAMIC','修正版V2')]:
  for asset,other in [('BTC','ETH'),('ETH','BTC')]:
   own=books[asset][n];opp=books[other][n];other_entries={t['signal_close_ms'] for t in opp['trades']}
   pos=opp['state_at_end']['position']
   if pos:other_entries.add(pos['order']['time']-10000)
   leg,signals,contexts,base,policy,pair=prepared[other]
   for t in own['trades']:
    ms=t['signal_close_ms'];side=1 if t['side']=='LONG' else -1
    if ms in other_entries:continue
    i=(ms-leg.first)//900000-1;bar=leg.bars[ms-900000];ctx=contexts['ER'].get(ms,{})
    knownpos=next((k for k in opp['trades'] if k['opened_us']<=ms*1000<k['closed_us']),None)
    if pos and opp['state_at_end']['position_opened_us']<=ms*1000:knownpos=pos
    orders=[e for e in opp['events'] if e['event']=='order_sent' and e['time_us']<=ms*1000<e['time_us']+3600*1000000]
    heldorder=any(not any(k['opened_us']<=ms*1000 and k['signal_close_ms']*1000+10000000==o['time_us'] for k in opp['trades']) for o in orders)
    side_signal=signals['ER'].get(ms,0)
    sent=next((e for e in opp['events'] if e['event']=='order_sent' and e['time_us']==(ms+10000)*1000),None)
    failure=[];aligned=int((leg.up if side==1 else leg.down)[i]);outside=bool((leg.above_band if side==1 else leg.below_band)[i]);macd=bool(side*leg.histogram[i]>0);density=float(leg.squeeze[96][i]);state=ctx.get('regime','UNVERIFIED')
    if density>.25:failure.append('最近96根最小带宽超过0.25%')
    if aligned<6:failure.append('六线未全部同向')
    if not outside:failure.append('收盘未位于全部六线方向外侧')
    if not macd:failure.append('MACD方向不符')
    if state=='transition':failure.append('ER过渡期暂停')
    elif state=='range' and float(leg.width[i])>.5:failure.append('震荡当前带宽超过0.50%')
    elif state in r.regime.DIRECTIONS and r.regime.DIRECTIONS[state]!=side:failure.append('ER趋势方向相反')
    gate=ctx.get('gate_confirmation')
    if base.get(ms)==side and gate and state in r.regime.DIRECTIONS and r.regime.DIRECTIONS[state]==side:
     if not gate['short_term_alignment']:failure.append('SMA5/SMA20趋势确认不符')
     dist=gate['distance_to_confirmed_hourly_level_pct'];near=dist is not None and dist<=2
     if not(near or gate['directional_volume_breakout'] or gate['confirmed_retest']):failure.append('2%绝对距离/放量突破/回踩均不通过')
    if knownpos:execution='已有持仓占用'
    elif heldorder:execution='已有挂单占用'
    elif sent:execution='已发挂单但该信号未成交'
    elif not side_signal:execution='未形成最终入场信号'
    elif side_signal!=side:execution='出现相反方向信号，未同向开仓'
    else:execution='有信号但无开仓，需进一步核对提交时点'
    key=f'{year}_{n}_{asset}_{ms}'
    row=dict(id=key,year=year,period=window,version=label,opened_asset=asset,missing_asset=other,signal_beijing=fmt(ms),direction='多' if side==1 else '空',outcome='盈利' if t['net']>0 else '亏损' if t['net']<0 else '持平',net_usdt=t['net'],signal_close_price=prepared[asset][0].bars[ms-900000].c,entry_price=t['entry'],entry_beijing=fmt(t['opened_us']/1000),exit_price=t['exit'],exit_beijing=fmt(t['closed_us']/1000),other_signal_close_price=bar.c,other_hypothetical_limit_price=r.model.limit_price(other,bar.c,side,nearest_tick=True),other_minimum_bandwidth_pct=density,other_current_bandwidth_pct=float(leg.width[i]),other_aligned_lines=aligned,other_close_outside_all_six=outside,other_MACD_histogram=float(leg.histogram[i]),other_ER_regime=state,other_actual_signal_direction=side_signal,other_execution_status=execution,other_failed_conditions='；'.join(failure) or '基础条件未发现失败项，见执行状态',other_has_position=bool(knownpos),other_has_pending_order=heldorder,trend_extra_details='见context' if gate and base.get(ms)==side else '基础信号不存在或方向不同，不将另一方向确认指标当作本方向',context=json.dumps(ctx,ensure_ascii=False))
    rows.append(row)
    checks=[('最近96根最小带宽≤0.25%',f'{density:.6f}%',density<=.25),('六线全部同向',f'{aligned}/6',aligned==6),('收盘在六线方向外侧',str(outside),outside),('MACD方向支持',f'{leg.histogram[i]:.8f}',macd),('ER允许当前方向',state,state=='range' or r.regime.DIRECTIONS.get(state)==side)]
    if state=='range':checks.append(('震荡当前带宽≤0.50%',f'{leg.width[i]:.6f}%',leg.width[i]<=.5))
    if gate and base.get(ms)==side and state in r.regime.DIRECTIONS and r.regime.DIRECTIONS[state]==side:
     distance=gate['distance_to_confirmed_hourly_level_pct'];near=distance is not None and distance<=2
     checks.append(('SMA5/SMA20及MACD趋势确认',str(gate['short_term_alignment']),gate['short_term_alignment']))
     checks.append(('2%绝对距离/放量突破/回踩至少一项',f'距离={distance}%;放量={gate["directional_volume_breakout"]};回踩={gate["confirmed_retest"]}',near or gate['directional_volume_breakout'] or gate['confirmed_retest']))
    for condition,value,passed in checks:conditions.append(dict(id=key,year=year,version=label,asset=other,signal_beijing=fmt(ms),condition=condition,value=value,result='通过' if passed else '不通过'))
 print(year,'done',len(rows),flush=True)
save('trades.csv',rows);save('conditions.csv',conditions)
summary=[]
for cov in coverage:
 y=cov['year'];window=cov['period']
 for label in ('原ER','修正版V2'):
  for a in ('BTC','ETH'):
   group=[q for q in rows if q['year']==y and q['period']==window and q['version']==label and q['opened_asset']==a]
   summary.append(dict(year=y,period=window,version=label,opened_asset=a,exclusive_closed_trades=len(group),wins=sum(q['net_usdt']>0 for q in group),losses=sum(q['net_usdt']<0 for q in group),breakeven=sum(q['net_usdt']==0 for q in group),net_usdt=sum(q['net_usdt'] for q in group)))
save('summary.csv',summary);(OUT/'results.json').write_text(json.dumps(dict(coverage=coverage,missing_2019='UNVERIFIED',summary=summary,trades=rows),ensure_ascii=False))
lines=['# BTC/ETH单边开仓全量核对','','仅币安USDT永续。按同一根15分钟信号：一币实际成交，另一币没有该信号对应的实际成交（不要求同一秒成交）。另一币若同根信号有相反方向成交也排除。盈利亏损按实际成交那笔完整交易净盈亏，含部分减仓；不推算另一币本会盈利。双方信号价均为当根已闭15m收盘；假设限价仅按规则计算，不是实际成交。原ER与V2分开，不把两版本相加。','','2019未验证；2020仅02-16至年底；2021—2025全年；2026年1—10月与11月1日至13日08:00分段列示。11月每币500重新起跑，与年度余额不同，不拼年度盈亏。之后至今天未验证。未平仓交易不分胜负、不计本次已平仓统计。手续费0、未计资金费。原代码不改、历史回测不重跑，只读取流水与重建入场指标。','','|年份|版本|BTC独开 盈/亏|ETH独开 盈/亏|','|---|---|---:|---:|']
for cov in coverage:
 y=cov['year'];window=cov['period']
 for label in ('原ER','修正版V2'):
  a,b=[next(q for q in summary if q['year']==y and q['period']==window and q['version']==label and q['opened_asset']==x) for x in ('BTC','ETH')];lines.append(f"|{window}|{label}|{a['wins']}/{a['losses']}|{b['wins']}/{b['losses']}|")
lines+=['','全量交易和双方价格见trades.csv；逐项条件表见conditions.csv；以下按原ER列出每笔案例。V2完整同格式数据在CSV，避免一份页面重复相同信号。']
for q in rows:
 if q['version']!='原ER':continue
 lines += ['',f"## {q['signal_beijing']} {q['opened_asset']}独开{q['direction']} · {q['outcome']} {q['net_usdt']:+.2f} USDT",'',f"{q['opened_asset']}信号收盘{q['signal_close_price']:.4f}，实际开仓{q['entry_price']:.4f}，平仓{q['exit_price']:.4f}；{q['missing_asset']}信号收盘{q['other_signal_close_price']:.4f}。",'', '|条件|未开币实际情况|结果|','|---|---|---|']
 for c in conditions:
  if c['id']==q['id']:lines.append(f"|{c['condition']}|{c['value']}|{c['result']}|")
 lines += ['',f"执行状态：{q['other_execution_status']}。失败条件：{q['other_failed_conditions']}。"]
(OUT/'report.md').write_text('\n'.join(lines)+'\n')
print('COMPLETE',len(rows),'versioned exclusive closed trades')
