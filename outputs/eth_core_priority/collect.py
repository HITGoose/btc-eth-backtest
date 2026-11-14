"""Read-only full-account analysis. No import of an ambiguous legacy collect."""
from pathlib import Path
from collections import Counter
import json,csv,gzip,gc
import numpy as np
import strategy as z
h=z.module('priority_metrics',z.OUT/'analysis_helpers.py');OUT=z.OUT
PAIRS=[('G','D'),('H','D'),('I','D'),('G','B'),('H','B'),('I','B')]

def locate(period,asset,cost,group):
 group='B'if asset=='BTC'else group
 for folder in sorted((OUT/'runs'/period/asset).glob('*')):
  q=folder/f'{cost}_{group}_result.json';eq=folder/f'{cost}_{group}_equity.npy'
  if q.exists()and eq.exists()and(folder/'status.json').exists():return folder
 # Independently isolated cost tasks may finish despite the other cost blocking.
 folder=OUT/'cost_isolation'/cost/'runs'/period/asset/group
 if(folder/f'{cost}_{group}_result.json').exists()and(folder/'status.json').exists():return folder
 raise FileNotFoundError(f'{period} {asset} {cost} {group} not complete')
def load(period,asset,cost,group):
 f=locate(period,asset,cost,group);g='B'if asset=='BTC'else group
 return h.read(f/f'{cost}_{g}_result.json'),np.load(f/f'{cost}_{g}_equity.npy')
def maps(period,asset):
 for f in (OUT/'runs'/period/asset).glob('*/signals.json'):return h.read(f)
 raise FileNotFoundError('signals absent')
def decision(q,accepted,core,wide,btc,group):
 trades=h.rows(q);fills={x['signal_close_ms']:x for x in trades};orders=[x for x in q['events']if x['event']=='order_sent'];sent={x['signal_close_ms']:x for x in orders}
 cancelled={x['extra_signal_close_ms']:x['time_us']for x in q['events']if x['event']=='priority_cancel_extra_order'}
 req=[x for x in q['events']if x['event']=='priority_replace_requested'];out={};end=h.us(q['window'][1]);start=h.us(q['window'][0])
 for stamp,side in wide.items():
  if not start<=stamp*1000<end:continue
  clock=(stamp+10000)*1000;origin='CORE'if core.get(stamp)==side else'EXTRA';held=next((x for x in trades if x['opened_us']<=clock<(x['closed_us']or end)),None);pending=None
  for order in orders:
   fill=fills.get(order['signal_close_ms']);until=min(order['time_us']+3600000000,fill['opened_us']if fill else end,cancelled.get(order['signal_close_ms'],end))
   if order['time_us']<clock<until:pending=order
  if stamp not in accepted:status='BTC_FILTER_REJECTED'if group in('G','I')and origin=='EXTRA'else'NOT_IN_GROUP_SIGNAL'
  elif stamp in fills:status='FILLED'
  elif stamp in sent:status='CANCELLED_BY_CORE'if stamp in cancelled else'PENDING_AT_END'if sent[stamp]['time_us']+3600000000>end else'EXPIRED_UNFILLED'
  elif any(a['scheduled_us']//1000-10000==stamp and not a['accepted']for a in q['place_attempts']):status='FUNDS_OR_MIN_NOTIONAL'
  elif any(x['core_signal_close_ms']==stamp for x in req):status='PRIORITY_WAITING_OR_SUBMIT_REJECTED'
  elif held:status='BLOCKED_POSITION'
  elif pending:status='BLOCKED_PENDING_ORDER'
  else:status='NO_ORDER_CHECK_EVENT_OR_PRIORITY_LOCK'
  out[stamp]=dict(signal_close_ms=stamp,side=side,origin=origin,BTC_complete_signal=btc.get(stamp,0),execution_status=status,failed_conditions='BTC_SAME_DIRECTION'if status=='BTC_FILTER_REJECTED'else'',occupying_signal_close_ms=held['signal_close_ms']if held else None,pending_signal_close_ms=pending['signal_close_ms']if pending else None)
 return out

def main():
 metrics=[];monthly=[];attr=[];impact=[];priority=[];filters=[];availability=[];cashchecks=[];concentration=[];decisions_all=[];allq={}
 for period in z.PERIODS:
  sm=maps(period,'ETH');core={int(k):v for k,v in sm['core'].items()};wide={int(k):v for k,v in sm['wide'].items()};btc={int(k):v for k,v in sm['BTC'].items()}
  for cost in z.COSTS:
   loaded={};vectors={};decisions={}
   for group in z.GROUPS:
    try:
     qb,mb=load(period,'BTC',cost,group);qe,me=load(period,'ETH',cost,group)
    except FileNotFoundError as error:
     availability.append(dict(period=period,cost=cost,group=group,status='UNVERIFIED',error=str(error)));continue
    availability.append(dict(period=period,cost=cost,group=group,status='COMPLETE'));loaded[group]=(qb,mb,qe,me);allq[period,cost,group]=qe
    accepted=z.classify(core,wide,btc,group)[0];decisions[group]=decision(qe,accepted,core,wide,btc,group)
    decisions_all.extend(dict(period=period,cost=cost,group=group,**x)for x in decisions[group].values())
    vb=h.curve(qb,mb);ve=h.curve(qe,me);vectors[group]=(vb,ve)
    for asset,q,marks,vec,initial in [('BTC',qb,mb,vb,500.),('ETH',qe,me,ve,500.),('COMBINED',None,mb+me,None,1000.)]:
     qs=[q]if q else[qb,qe];trades=[t for qq in qs for t in qq['trades']];window=qs[0]['window']
     for side,direction in[(None,'ALL'),(1,'LONG'),(-1,'SHORT')]:
      ts=trades if side is None else[x for x in trades if x['side']==direction]
      values=marks if side is None else vec['directions'][side]if vec else vb['directions'][side]+ve['directions'][side]
      opened=sum(bool(qq['state_at_end']['position'])and(side is None or qq['state_at_end']['position']['order']['side']==side)for qq in qs)
      row=h.metrics(ts,values,initial,window,opened);months=row.pop('monthly')
      fees=sum(sum(x['entry']*x['quantity']+sum(f['execution_price']*f['quantity']for f in x.get('partial_fills',[]))+(x['exit']*x['final_exit_quantity']if x['status']=='CLOSED'else 0)for x in h.rows(qq)if side is None or x['side']==direction)*qq['fee']for qq in qs)
      row.update(period=period,cost=cost,group=group,asset=asset,direction=direction,fees_paid_USDT=fees,scope='ACTUAL_ACCOUNT'if side is None else'DIRECTION_PNL_ATTRIBUTION_NOT_SEPARATE_ACCOUNT')
      metrics.append(row);monthly.extend(dict(period=period,cost=cost,group=group,asset=asset,direction=direction,**m)for m in months)
     for qq in qs:
      err=qq['ending_equity']-500-sum(t['net']for t in qq['trades'])-qq['open_contribution'];assert abs(err)<1e-7
      assert abs(qq['cash']-500-sum(x['delta']for x in qq['cash_events']))<1e-7
      cashchecks.append(dict(period=period,cost=cost,group=group,asset=qq['asset'],closed_net=sum(t['net']for t in qq['trades']),open_fee_partial_and_MTM_contribution=qq['open_contribution'],ending_equity=qq['ending_equity'],residual=err,cash_event_residual=qq['cash']-500-sum(x['delta']for x in qq['cash_events'])))
    events=qe['events'];fills={x['signal_close_ms']:x for x in h.rows(qe)};ev=lambda n:[x for x in events if x['event']==n]
    requests=ev('priority_replace_requested');active=[t for t in qe['trades']if t['reason']=='core_priority_exit'];submits=ev('priority_core_submit_result');corekeys={x['core_signal_close_ms']for x in submits if x['accepted']}
    priority.append(dict(period=period,cost=cost,group=group,cancelled_EXTRA_orders=len(ev('priority_cancel_extra_order')),replace_requests=len(requests),active_exit_count=len(active),active_exit_same_direction=sum(x['same_direction']for x in ev('priority_position_closed')),active_exit_opposite_direction=sum(not x['same_direction']for x in ev('priority_position_closed')),stop_first_count=len(ev('priority_stop_first')),active_exited_full_trade_net=sum(x['net']for x in active),active_exit_final_leg_cash_credit=sum(x['actual_final_cash_credit']for x in active),active_exit_fees=sum(x['exit']*x['final_exit_quantity']*qe['fee']for x in active),replacement_CORE_submitted=len(corekeys),replacement_CORE_filled=len(corekeys&fills.keys()),replacement_CORE_expired=sum(x in corekeys and row['execution_status']=='EXPIRED_UNFILLED'for x,row in decisions[group].items()),replacement_CORE_unfilled_at_end=sum(x in corekeys and row['execution_status']=='PENDING_AT_END'for x,row in decisions[group].items()),replacement_CORE_entry_fees=sum(fills[x]['entry']*fills[x]['quantity']*qe['fee']for x in corekeys&fills.keys()),extra_turnover_fees_scope='observed active-exit plus replacement-entry fees; incremental total cost is full account fee delta',pending_priority_at_end=bool(qe.get('replacement_at_end'))))
   if 'D'in loaded:
    qd=loaded['D'][2];dt={x['signal_close_ms']:x for x in h.rows(qd)}
   else:dt=None
   start,end=map(h.us,next(iter(loaded.values()))[0]['window'])if loaded else(0,0)
   for stamp,side in wide.items():
    if not start<=stamp*1000<end or core.get(stamp)==side:continue
    passed=btc.get(stamp)==side;t=dt.get(stamp)if dt is not None else None
    filters.append(dict(period=period,cost=cost,signal_close_ms=stamp,side='LONG'if side==1 else'SHORT',BTC_signal_side=btc.get(stamp,0),BTC_confirm_pass=passed,D_status='NOT_EVALUATED'if dt is None else t['status']if t else'NOT_FILLED',D_net=t.get('net')if t else None,D_quantity=t['quantity']if t else None,D_net_per_1000_initial=t['contribution']/(t['entry']*t['quantity'])*1000 if t else None,scope='same filter for G/I once; D outcome hindsight attribution only'))
   for variant,base in PAIRS:
    if variant not in loaded or base not in loaded:continue
    for asset,index in[('BTC',0),('ETH',2)]:
     old=loaded[base][index];new=loaded[variant][index];rows=h.compare(old,new,decisions[variant]if asset=='ETH'else{})
     rows=[dict(period=period,cost=cost,variant=variant,base=base,asset=asset,**x)for x in rows];attr.extend(rows)
     for direction in('ALL','LONG','SHORT'):
      use=rows if direction=='ALL'else[x for x in rows if x['side']==direction];added=[x for x in use if x['category']=='ADDED'];lost=[x for x in use if x['category']=='DISAPPEARED'];match=[x for x in use if x['category']in('RETAINED','CHANGED')]
      impact.append(dict(period=period,cost=cost,variant=variant,base=base,asset=asset,direction=direction,actual_USDT_delta=sum(x['actual_USDT_delta']for x in use),normalized_1000_delta=sum(x['normalized_1000_delta']for x in use),added=len(added),disappeared=len(lost),retained=sum(x['category']=='RETAINED'for x in use),changed=sum(x['category']=='CHANGED'for x in use),added_wins=sum(x['new_status']=='CLOSED'and x['new_net']>0 for x in added),added_losses=sum(x['new_status']=='CLOSED'and x['new_net']<0 for x in added),added_closed_net=sum(x['new_net']for x in added if x['new_status']=='CLOSED'),lost_winners=sum(x['old_status']=='CLOSED'and x['old_net']>0 for x in lost),lost_winner_profit=sum(x['old_net']for x in lost if x['old_status']=='CLOSED'and x['old_net']>0),avoided_old_loss=-sum(x['old_net']for x in lost if x['old_status']=='CLOSED'and x['old_net']<0),gross_loss_delta=sum(-min(0,x['new_net'])for x in use if x['new_status']=='CLOSED')-sum(-min(0,x['old_net'])for x in use if x['old_status']=='CLOSED'),old_losing_worsened_actual=sum(x['old_status']=='CLOSED'and x['new_status']=='CLOSED'and x['old_net']<0 and x['new_net']<x['old_net']-1e-8 for x in match),old_losing_worsened_normalized=sum(x['old_status']=='CLOSED'and x['new_status']=='CLOSED'and x['old_net']<0 and x['new_normalized_1000']<x['old_normalized_1000']-1e-8 for x in match),matched_actual_delta=sum(x['actual_USDT_delta']for x in match),matched_normalized_delta=sum(x['normalized_1000_delta']for x in match),fees_delta=new['stats'].get('fees',0)-old['stats'].get('fees',0),disappearance_reasons=json.dumps(Counter(x['variant_reason']for x in lost))))
     if asset=='ETH':
      positive=sorted([x['actual_USDT_delta']for x in rows if x['actual_USDT_delta']>0],reverse=True);addedprofit=sorted([x['new_net']for x in rows if x['category']=='ADDED'and x['new_status']=='CLOSED'and x['new_net']>0],reverse=True)
      concentration.append(dict(period=period,cost=cost,variant=variant,base=base,positive_attribution=sum(positive),top1_positive_share=sum(positive[:1])/sum(positive)if positive else None,top5_positive_share=sum(positive[:5])/sum(positive)if positive else None,added_profit=sum(addedprofit),added_top5_share=sum(addedprofit[:5])/sum(addedprofit)if addedprofit else None))
   # Recovery counts relative to B and D use same signal keys, never a rule input.
   if 'B'in loaded and'D'in loaded:
    bkeys={h.trade_key(x):x for x in h.rows(loaded['B'][2])};dkeys={h.trade_key(x)for x in h.rows(loaded['D'][2])}
    for row in priority:
     if row['period']!=period or row['cost']!=cost or row['group']not in loaded:continue
     vkeys={h.trade_key(x)for x in h.rows(loaded[row['group']][2])};restored=(bkeys.keys()-dkeys)&vkeys;lost=bkeys.keys()-vkeys
     row.update(restored_B_trades=len(restored),still_missing_B_trades=len(lost),restored_B_winners=sum(bkeys[k]['status']=='CLOSED'and bkeys[k]['net']>0 for k in restored),still_missing_B_winners=sum(bkeys[k]['status']=='CLOSED'and bkeys[k]['net']>0 for k in lost))
   del loaded,vectors;gc.collect()
  print('COLLECTED',period,flush=True)
 for name,rows in[('yearly_metrics',metrics),('monthly',monthly),('trade_attribution',attr),('impact',impact),('priority_summary',priority),('btc_filter_audit',filters),('availability',availability),('cash_reconciliation',cashchecks),('concentration',concentration),('signal_execution_diagnostics',decisions_all)]:z.csv_dump(OUT/(name+('.csv.gz'if name=='signal_execution_diagnostics'else'.csv')),rows)
 for cat in('ADDED','DISAPPEARED','CHANGED','RETAINED'):z.csv_dump(OUT/f'trades_{cat.lower()}.csv',[x for x in attr if x['category']==cat])
 events=[]
 for(period,cost,group),q in allq.items():
  for item in q['events']:
   if item['event'].startswith('priority_')or item['event']=='core_priority_exit':events.append(dict(period=period,cost=cost,group=group,**item))
 z.csv_dump(OUT/'priority_events.csv',events)
 wide=[]
 for period in['2020','2021','2022','2023','2024','2025','2026','NOV']:
  for cost in z.COSTS:
   row=dict(period=period,cost=cost)
   for g in z.GROUPS:
    m=next((x for x in metrics if x['period']==period and x['cost']==cost and x['group']==g and x['asset']=='COMBINED'and x['direction']=='ALL'),None);row[g+'_status']='COMPLETE'if m else'UNVERIFIED'
    for field in('return_pct','ending_equity','max_drawdown_pct','worst_month_return_pct','max_consecutive_losses','gross_winning_trade_net','gross_losing_trade_net','max_single_trade_loss','closed','open','fees_paid_USDT'):row[g+'_'+field]=m[field]if m else None
   wide.append(row)
 z.csv_dump(OUT/'comparison_five_groups.csv',wide)
 z.dump(OUT/'analysis.json',dict(metrics=metrics,impact=impact,priority=priority,availability=availability,concentration=concentration,full_history_complete=all(x['status']=='COMPLETE'for x in availability),funding='NOT_INCLUDED',fee_assumption='hypothetical .05pct per side'))
 report(metrics,impact,priority,filters,availability,concentration)
 print('DONE',len(metrics),'metrics',len(attr),'attributions',flush=True)

def report(metrics,impact,priority,filters,availability,conc):
 lines=['# ETH新增信号：BTC确认与CORE优先固定对照','','结果由完整账户逐笔重放产生；缺失区间不填零。B=.25 V2，D=.30 V2，G=BTC确认，H=CORE优先，I=两者；BTC始终.25 V2。费用ZERO或每边.05%假设，资金费未计。','','## 对照结果（仅同时完成的独立区间，非连续复利）','','|对照|费用|账户差额USDT|收益提高区间/已验证区间|回撤恶化区间|总亏损增加USDT|旧亏损扩大 实际/归一化|','|---|---|---:|---:|---|---:|---:|']
 for v,b in PAIRS:
  for cost in z.COSTS:
   use=[x for x in impact if x['variant']==v and x['base']==b and x['cost']==cost and x['asset']=='ETH'and x['direction']=='ALL'];periods=[x['period']for x in use];worse=[];improve=[]
   for period in periods:
    old=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==b and x['asset']=='COMBINED'and x['direction']=='ALL');new=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==v and x['asset']=='COMBINED'and x['direction']=='ALL')
    if new['return_pct']>old['return_pct']+1e-8:improve.append(period)
    if new['max_drawdown_pct']>old['max_drawdown_pct']+1e-8:worse.append(period)
   lines.append(f"|{v}/{b}|{cost}|{sum(x['actual_USDT_delta']for x in use):+.2f}|{len(improve)}/{len(periods)}（{','.join(improve)}）|{','.join(worse)or'无'}|{sum(x['gross_loss_delta']for x in use):+.2f}|{sum(x['old_losing_worsened_actual']for x in use)}/{sum(x['old_losing_worsened_normalized']for x in use)}|")
 lines+=['','## 五组收益／最大回撤（%）','','2020从02-16起；2026为1—10月；NOV独立起算至11-13 08:00北京时间。每年每币500。回撤为分钟末口径，非逐笔峰谷最大回撤。','','|区间|费用|B|D|G|H|I|','|---|---|---:|---:|---:|---:|---:|']
 for period in['2020','2021','2022','2023','2024','2025','2026','NOV']:
  for cost in z.COSTS:
   vals=[]
   for group in z.GROUPS:
    x=next((x for x in metrics if x['period']==period and x['cost']==cost and x['group']==group and x['asset']=='COMBINED'and x['direction']=='ALL'),None)
    vals.append(f"{x['return_pct']:+.2f} / {x['max_drawdown_pct']:.2f}"if x else'UNVERIFIED')
   lines.append('|'+period+'|'+cost+'|'+'|'.join(vals)+'|')
 lines+=['','## BTC过滤归因（G/I共享条件，不重复计样本）','']
 for cost in z.COSTS:
  use=[x for x in filters if x['cost']==cost];rej=[x for x in use if not x['BTC_confirm_pass']];passed=[x for x in use if x['BTC_confirm_pass']]
  for name,items in[('过滤拒绝',rej),('过滤通过',passed)]:
   ts=[x for x in items if x['D_status']=='CLOSED'];net=sum(x['D_net']for x in ts)
   lines.append(f"- {cost} {name}EXTRA候选{len(items)}；其中D已平{len(ts)}，赢{sum(x['D_net']>0 for x in ts)}/亏{sum(x['D_net']<0 for x in ts)}，D原账户net{net:+.2f}USDT。此为事后归因，不能作为过滤规则或可加到账户的收益。未完成D的候选表现为NOT_EVALUATED。")
 lines+=['','## CORE优先：主动退出代价','','|组|费用|撤EXTRA挂单|提前退出 同向/反向|主动退出整笔net|退出费用|恢复B交易|仍缺B交易|','|---|---|---:|---:|---:|---:|---:|---:|']
 for g in('H','I'):
  for cost in z.COSTS:
   use=[x for x in priority if x['group']==g and x['cost']==cost]
   lines.append(f"|{g}|{cost}|{sum(x['cancelled_EXTRA_orders']for x in use)}|{sum(x['active_exit_same_direction']for x in use)}/{sum(x['active_exit_opposite_direction']for x in use)}|{sum(x['active_exited_full_trade_net']for x in use):+.2f}|{sum(x['active_exit_fees']for x in use):.2f}|{sum(x.get('restored_B_trades',0)for x in use)}|{sum(x.get('still_missing_B_trades',0)for x in use)}|")
 lines+=['','主动退出整笔net包含已经发生的V2部分退出及完整开仓费；退出费用仅此次最终全平收费，重开/部分收费见priority_summary和完整账户fees_delta。恢复/仍缺只在B/D/实验同区间完成时核算，不把未验证当0。独立影子延续见shadow_results.csv/shadow_summary.md；影子不反馈账户，不能与实际收益相加。','','## 归因与限制','','trade_attribution及四类CSV按资产、方向、signal_close_ms匹配，延迟提交保留原CORE signal_close_ms，不能从actual order.time减10秒错误分类。匹配交易实际USDT与同1000初始名义归一化分开；V2减仓比例和步长取整影响归一化结果，不全是价格风险。','cash_reconciliation逐组核对closed net＋open fee/partial/MTM＝ending−500，以及现金事件总和。方向曲线为PnL归因，不是另开资金的独立策略。','concentration列新增盈利、正向差额前5笔占比；已有年份反复查看，不称独立样本外，不按年选组。','2025已知官方ETH日/月相同的3个冲突ID，不删行、猜价或OHLC替代。各组独立尝试，见failure和断点；2019不在本轮可验证范围。原生缓存及每次原始ZIP来源/checksum见runs；checksum不独立证明市场全集无缺漏。','信号BTC确认不要求BTC空闲或成交，也未使用BTC事后盈利。触价全量是模拟成交代理，不代表实盘深度可成交。','','## 未验证组','']
 lines += [f"- {x['period']} {x['cost']} {x['group']}：UNVERIFIED"for x in availability if x['status']!='COMPLETE']
 lines+=['','命令、时钟排序、冻结规则及恢复见EXPERIMENT.md；实际问题见ISSUES.md。结论在审计后写入CONCLUSION.md。']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
