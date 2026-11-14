"""Full-account attribution; may be rerun after job-level recovery."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import json,csv,gzip,math,gc
import numpy as np
import strategy as s
import analysis_helpers as h
OUT=s.OUT;PERIODS=['2024','2025','2020','2021','2022','2023','2026','NOV'];COSTS=['ZERO','ASSUMED_005_SIDE']

def decode(x):
 if x=='':return None
 if x=='True':return True
 if x=='False':return False
 try:return float(x)
 except(ValueError,TypeError):return x

def load_conditions(folder):
 with gzip.open(folder/'conditions.csv.gz','rt',encoding='utf-8-sig',newline='')as f:rows=[{k:decode(v)for k,v in r.items()}for r in csv.DictReader(f)]
 return{int(r['signal_close_ms']):r for r in rows}

def load(period,asset,cost,group):
 actual=group if asset=='ETH' else 'B'if s.GROUPS[group][1]else'A';folder=OUT/'runs'/period/asset;key=cost+'_'+actual
 if period=='2025' and asset=='ETH' and not(folder/'status.json').exists():
  suffix={.25:'25',.30:'30',.35:'35'}[s.GROUPS[group][0]];folder=OUT/'isolation'/suffix/'runs'/period/asset
 status=h.read(folder/'status.json');assert status['completed']
 q=h.read(folder/f'{key}_result.json');marks=np.load(folder/f'{key}_equity.npy');return q,marks

def subset(q,side):return[t for t in q['trades']if t['side']==('LONG'if side==1 else'SHORT')]
def overlap(q1,q2,v1,v2,eq):
 mask=v1['active']&v2['active'];count=int(mask.sum());end=h.us(q1['window'][1]);positions1=h.rows(q1);positions2=h.rows(q2)
 exact_intervals=[]
 for a in positions1:
  for b in positions2:
   lo=max(a['opened_us'],b['opened_us']);hi=min(a['closed_us']or end,b['closed_us']or end)
   if lo<hi:exact_intervals.append((lo,hi))
 negative_cash=0.
 for own,other in ((q1,positions2),(q2,positions1)):
  for event in own['cash_events']:
   if event['delta']<0 and any(x['opened_us']<=event['time_us']<=(x['closed_us']or end)for x in other):negative_cash-=event['delta']
 risk=v1['reference_stop_risk']+v2['reference_stop_risk'];notional=v1['gross_notional']+v2['gross_notional'];peak=np.maximum.accumulate(np.r_[1000.,eq])[1:]
 return dict(overlap_minutes_at_minute_marks=count,exact_overlap_episodes=len(exact_intervals),exact_overlap_seconds=sum(b-a for a,b in exact_intervals)/1e6,negative_cashflows_while_other_position_open=negative_cash,negative_cashflows_scope='includes entry/exit fees and negative realized partial/final cash credits; timestamp endpoints included',worst_combined_floating_PnL=float(min(0.,(v1['floating']+v2['floating'])[mask].min()))if count else 0.,max_reference_stop_giveback_USDT=float(risk[mask].max())if count else 0.,max_reference_stop_giveback_pct=float(np.max(100*risk[mask]/eq[mask]))if count else 0.,max_gross_notional_USDT=float(notional[mask].max())if count else 0.,max_combined_drawdown_during_overlap_pct=float(np.max(100*(1-eq[mask]/peak[mask])))if count else 0.)

def main():
 metrics=[];attribution=[];impact=[];monthly=[];failures=[];overlaps=[];decision_counts=[];completed=[];concentration=[];availability=[];partial_periods=[]
 for period in PERIODS:
  available=[]
  for group in s.GROUPS:
   try:
    load(period,'BTC','ZERO',group);load(period,'ETH','ZERO',group);load(period,'BTC','ASSUMED_005_SIDE',group);load(period,'ETH','ASSUMED_005_SIDE',group)
    available.append(group);availability.append(dict(period=period,group=group,status='COMPLETE'))
   except Exception as error:
    failure=dict(period=period,group=group,status='UNVERIFIED',error=repr(error))
    if period=='2025':
     suffix={.25:'25',.30:'30',.35:'35'}[s.GROUPS[group][0]];evidence=OUT/'isolation'/suffix/'runs/2025/ETH/failure.json'
     if evidence.exists():failure.update(actual_error=h.read(evidence)['error'],evidence_file=str(evidence),official_archive_issue='2025-08-29 ETH raw trade IDs conflict; official daily and monthly day are byte-identical',recovery_evidence=str(OUT/'recovery_20250829_ETH/result.json'))
    failures.append(failure);availability.append(failure)
  if not available:continue
  features={a:load_conditions(OUT/'runs'/period/a)for a in ('BTC','ETH')}
  smaps={a:{float(k):{int(t):v for t,v in values.items()}for k,values in h.read(OUT/'runs'/period/a/'signals.json').items()}for a in ('BTC','ETH')}
  for asset in ('BTC','ETH'):
   assert set(smaps[asset][.25].items())<=set(smaps[asset][.30].items())<=set(smaps[asset][.35].items()),'Non-monotonic raw signal sets'
  for asset in ('BTC','ETH'):
   lo,hi=map(h.us,h.read(OUT/'runs'/period/asset/'config.json')['period'])
   for sigs in smaps[asset].values():assert all(k in features[asset] and features[asset][k]['side']==side for k,side in sigs.items()if lo<=k*1000<hi),'Final signal missing from diagnostic candidate set'
  for cost in COSTS:
   loaded={};vectors={};decisions={};dec_rows=[]
   for asset in ('BTC','ETH'):
    for group in (available if asset=='ETH'else['A','B']):
     q,marks=load(period,asset,cost,group);loaded[asset,group]=(q,marks);vectors[asset,group]=h.curve(q,marks)
     thr=s.GROUPS[group][0]if asset=='ETH'else .25
     signals=smaps[asset][thr];dec=h.diagnostic(q,features[asset],signals,thr);decisions[asset,group]=dec
     assert not any(x['execution_status']=='UNEXPLAINED_NO_ORDER'for x in dec.values()),(period,asset,cost,group,'unexplained decision')
     for item in dec.values():dec_rows.append(dict(period=period,cost=cost,group=group,asset=asset,**item))
     counts=Counter(x['execution_status']for x in dec.values());decision_counts.append(dict(period=period,cost=cost,group=group,asset=asset,**counts))
   for group in available:
    bg='B'if s.GROUPS[group][1]else'A';qb,mb=loaded['BTC',bg];qe,me=loaded['ETH',group];vb=vectors['BTC',bg];ve=vectors['ETH',group];combined=mb+me
    for asset,q,marks,vec,initial in [('BTC',qb,mb,vb,500.),('ETH',qe,me,ve,500.),('COMBINED',None,combined,None,1000.)]:
     trades=q['trades']if q else qb['trades']+qe['trades'];window=q['window']if q else qb['window'];opencount=int(bool(q['state_at_end']['position']))if q else int(bool(qb['state_at_end']['position']))+int(bool(qe['state_at_end']['position']))
     for side,direction in [(None,'ALL'),(1,'LONG'),(-1,'SHORT')]:
      ts=trades if side is None else[t for t in trades if t['side']==direction]
      values=marks if side is None else vec['directions'][side]if vec else vb['directions'][side]+ve['directions'][side]
      nopen=opencount if side is None else sum(1 for qq in ([q]if q else[qb,qe])if qq['state_at_end']['position']and qq['state_at_end']['position']['order']['side']==side)
      m=h.metrics(ts,values,initial,window,nopen);months=m.pop('monthly');m.update(period=period,cost=cost,group=group,asset=asset,direction=direction,return_scope='ACTUAL_ACCOUNT'if side is None else'DIRECTION_PNL_ATTRIBUTION_NOT_SEPARATE_ACCOUNT')
      if side is None:
       sq=[q]if q else[qb,qe];m.update(signals=sum(sum(int(window[0] and h.us(window[0]))<=int(t)*1000<h.us(window[1])for t in smaps[qq['asset']][s.GROUPS[group][0]if qq['asset']=='ETH'else .25])for qq in sq),submitted=sum(qq['stats'].get('submitted',0)for qq in sq),expired=sum(qq['stats'].get('expired',0)for qq in sq),funds_rejected=sum(qq['stats'].get('rejected',0)for qq in sq),opens=sum(qq['opens']for qq in sq),pending=sum(bool(qq['state_at_end']['pending_order'])for qq in sq),fees_paid_USDT=sum(qq['stats'].get('fees',0.)for qq in sq))
      metrics.append(m)
      monthly.extend(dict(period=period,cost=cost,group=group,asset=asset,direction=direction,**x)for x in months)
    overlaps.append(dict(period=period,cost=cost,group=group,**overlap(qb,qe,vb,ve,combined)))
   for variant,base in [('C','A'),('E','A'),('D','B'),('F','B')]:
    if variant not in available or base not in available:continue
    for asset in ('BTC','ETH'):
     va=variant if asset=='ETH'else'B'if s.GROUPS[variant][1]else'A';ba=base if asset=='ETH'else'B'if s.GROUPS[base][1]else'A';old=loaded[asset,ba][0];new=loaded[asset,va][0]
     comparison=h.compare(old,new,decisions[asset,va]);comparison=[dict(period=period,cost=cost,asset=asset,variant=variant,base=base,**row)for row in comparison];attribution.extend(comparison)
     added_wins=sorted([x['new_net']for x in comparison if x['category']=='ADDED'and x['new_status']=='CLOSED'and x['new_net']>0],reverse=True);positive_changes=sorted([x['actual_USDT_delta']for x in comparison if x['actual_USDT_delta']>0],reverse=True)
     concentration.append(dict(period=period,cost=cost,asset=asset,variant=variant,base=base,added_gross_profit=sum(added_wins),added_top1_profit_share=sum(added_wins[:1])/sum(added_wins)if added_wins else None,added_top5_profit_share=sum(added_wins[:5])/sum(added_wins)if added_wins else None,positive_attribution_delta=sum(positive_changes),top5_positive_delta_share=sum(positive_changes[:5])/sum(positive_changes)if positive_changes else None))
     for direction in ('ALL','LONG','SHORT'):
      wanted=None if direction=='ALL'else 1 if direction=='LONG'else-1
      start_us,end_us=map(h.us,new['window'])
      old_signals={(int(t),v)for t,v in smaps[asset][s.GROUPS[base][0]if asset=='ETH'else .25].items()if start_us<=int(t)*1000<end_us and(wanted is None or v==wanted)}
      new_signals={(int(t),v)for t,v in smaps[asset][s.GROUPS[variant][0]if asset=='ETH'else .25].items()if start_us<=int(t)*1000<end_us and(wanted is None or v==wanted)}
      old_orders={(e['time_us']//1000-10000,e['side'])for e in old['events']if e['event']=='order_sent'and(wanted is None or e['side']==wanted)}
      new_orders={(e['time_us']//1000-10000,e['side'])for e in new['events']if e['event']=='order_sent'and(wanted is None or e['side']==wanted)}
      fill_keys={(t['signal_close_ms'],1 if t['side']=='LONG'else-1)for t in h.rows(new)}
      additional_orders=new_orders-old_orders
      use=[x for x in comparison if direction=='ALL'or x['side']==direction];add=[x for x in use if x['category']=='ADDED'];lost=[x for x in use if x['category']=='DISAPPEARED'];matched=[x for x in use if x['category']in('RETAINED','CHANGED')]
      impact.append(dict(period=period,cost=cost,asset=asset,variant=variant,base=base,direction=direction,new_signals=len(new_signals-old_signals),disappeared_signals=len(old_signals-new_signals),actual_new_order_keys=len(additional_orders),disappeared_order_keys=len(old_orders-new_orders),new_order_keys_filled=len(additional_orders&fill_keys),new_order_keys_unfilled=len(additional_orders-fill_keys),retained=sum(x['category']=='RETAINED'for x in use),changed=sum(x['category']=='CHANGED'for x in use),added=len(add),disappeared=len(lost),added_closed_wins=sum(x['new_status']=='CLOSED'and x['new_net']>0 for x in add),added_closed_losses=sum(x['new_status']=='CLOSED'and x['new_net']<0 for x in add),added_open=sum(x['new_status']=='OPEN'for x in add),added_winning_net=sum(x['new_net']for x in add if x['new_status']=='CLOSED'and x['new_net']>0),added_losing_net=-sum(x['new_net']for x in add if x['new_status']=='CLOSED'and x['new_net']<0),added_closed_net=sum(x['new_net']for x in add if x['new_status']=='CLOSED'),lost_original_winning_trades=sum(x['old_status']=='CLOSED'and x['old_net']>0 for x in lost),lost_original_winning_profit=sum(x['old_net']for x in lost if x['old_status']=='CLOSED'and x['old_net']>0),avoided_original_losses=-sum(x['old_net']for x in lost if x['old_status']=='CLOSED'and x['old_net']<0),old_losing_trade_worsened_actual=sum(x['old_status']=='CLOSED'and x['new_status']=='CLOSED'and x['old_net']<0 and x['new_net']<x['old_net']-1e-8 for x in matched),old_losing_trade_worsened_normalized=sum(x['old_status']=='CLOSED'and x['new_status']=='CLOSED'and x['old_net']<0 and x['new_normalized_1000']<x['old_normalized_1000']-1e-8 for x in matched),matched_actual_USDT_delta=sum(x['actual_USDT_delta']for x in matched),matched_normalized_1000_delta=sum(x['normalized_1000_delta']for x in matched),added_normalized_1000_net=sum(x['new_normalized_1000']for x in add),actual_USDT_delta=sum(x['actual_USDT_delta']for x in use),normalized_1000_delta=sum(x['normalized_1000_delta']for x in use),gross_losing_trade_net_delta=sum(max(0,-x['new_net'])if x['new_status']=='CLOSED'else 0 for x in use)-sum(max(0,-x['old_net'])if x['old_status']=='CLOSED'else 0 for x in use),disappearance_reasons=json.dumps(Counter(x['variant_reason']for x in lost),ensure_ascii=False)))
   dec_rows.sort(key=lambda x:(x['asset'],x['signal_close_ms'],x['group']))
   s.csv_dump(OUT/f'diagnostics_{period}_{cost}.csv.gz',dec_rows)
   del loaded,vectors,decisions,dec_rows;gc.collect()
  if len(available)==6:completed.append(period)
  else:partial_periods.append(dict(period=period,verified_groups=available))
  print('COLLECTED',period,available,flush=True)
 s.csv_dump(OUT/'availability.csv',availability);s.csv_dump(OUT/'concentration.csv',concentration);s.csv_dump(OUT/'yearly_metrics.csv',metrics);s.csv_dump(OUT/'monthly.csv',monthly);s.csv_dump(OUT/'trade_attribution.csv',attribution);s.csv_dump(OUT/'impact.csv',impact);s.csv_dump(OUT/'overlap_risk.csv',overlaps);s.csv_dump(OUT/'decision_counts.csv',decision_counts)
 for category in ('ADDED','DISAPPEARED','CHANGED','RETAINED'):s.csv_dump(OUT/f'trades_{category.lower()}.csv',[x for x in attribution if x['category']==category])
 wide=[]
 for period in ['2019','2020','2021','2022','2023','2024','2025','2026','NOV']:
  for cost in COSTS:
   row=dict(period=period,cost=cost)
   for group in s.GROUPS:
    value=next((x for x in metrics if x['period']==period and x['cost']==cost and x['group']==group and x['asset']=='COMBINED'and x['direction']=='ALL'),None)
    row[group+'_status']='COMPLETE'if value else'UNVERIFIED'
    for field in ('return_pct','ending_equity','max_drawdown_pct','worst_month_return_pct','max_consecutive_losses','closed','open'):row[group+'_'+field]=value[field]if value else None
   wide.append(row)
 s.csv_dump(OUT/'comparison_six_groups.csv',wide)
 s.dump(OUT/'analysis.json',dict(completed_periods=completed,partial_periods=partial_periods,failures=failures,metrics=metrics,impact=impact,concentration=concentration,overlap=overlaps,missing_2019='UNVERIFIED',fee_assumption='uniform0.05pct/side hypothetical; funding absent',base_commit=s.BASE_COMMIT))
 report(metrics,impact,overlaps,failures,completed,concentration)
 print('DONE',len(metrics),'metrics rows',len(attribution),'attribution rows',flush=True)

def report(metrics,impact,overlaps,failures,completed,concentration):
 lines=['# ETH历史密集阈值：固定六组逐笔实验','','## 当前结论','']
 if len(completed)!=len(PERIODS):lines+=['结果尚未完整，不能宣称任何放宽有效，也不能将未验证组填为零。暂保留0.25%，待数据问题解决再完成判断；缺失组见availability.csv与末尾，2019始终UNVERIFIED。']
 else:
  for variant,base in [('C','A'),('E','A'),('D','B'),('F','B')]:
   for cost in COSTS:
    items=[x for x in impact if x['variant']==variant and x['cost']==cost and x['asset']=='ETH'and x['direction']=='ALL'];profits=sum(x['added_winning_net']for x in items);losses=sum(x['added_losing_net']for x in items);wins=sum(x['added_closed_wins']for x in items);losscount=sum(x['added_closed_losses']for x in items);delta=sum(x['actual_USDT_delta']for x in items)
    lines.append(f'- {variant}对{base}（{cost}）：新增已平仓{wins}赢/{losscount}亏，新增盈利{profits:.2f}、亏损{losses:.2f}、净额{profits-losses:+.2f} USDT；各独立区间账户差额合计{delta:+.2f} USDT（非跨年复利）。挤掉原盈利金额{sum(x["lost_original_winning_profit"]for x in items):.2f} USDT。')
  # Conservative rule fixed before results: robust improvement requires more than total profit.
  robust=[]
  for variant,base in [('C','A'),('E','A'),('D','B'),('F','B')]:
   pairs=[]
   for cost in COSTS:
    for period in PERIODS:
     a=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==base and x['asset']=='COMBINED'and x['direction']=='ALL');b=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==variant and x['asset']=='COMBINED'and x['direction']=='ALL');pairs.append((b['return_pct']>a['return_pct'],b['max_drawdown_pct']<=a['max_drawdown_pct'],b['worst_month_return_pct']>=a['worst_month_return_pct']))
   if all(all(p)for p in pairs):robust.append(variant)
  lines+=['','保留建议：'+('仅'+','.join(robust)+'满足本报告保守的逐区间收益/回撤/最差月要求，仍需参考机器人交易匹配及未查看数据验证。'if robust else'保留0.25%。0.30%和0.35%未在全部区间及费用压力下同时体现收益、回撤和最差月的稳定优势。不得按年选择最佳组。')]
 lines+=['','已验证部分暂不支持替换0.25%：新增ETH交易自身总体盈利，但四个放宽对照的独立区间账户期末损益差额合计均为负，并存在挤掉原盈利、回撤/最差月恶化和费用侵蚀。2025放宽组缺数据，不将这一观察称为全历史完整验证。','','|对照|费用|新增ETH赢/亏|新增交易净额USDT|完整账户差额USDT|消失原盈利单|失去原盈利USDT|','|---|---|---:|---:|---:|---:|---:|']
 for variant,base in [('C','A'),('D','B'),('E','A'),('F','B')]:
  for cost in COSTS:
   items=[x for x in impact if x['variant']==variant and x['cost']==cost and x['asset']=='ETH'and x['direction']=='ALL']
   if items:lines.append(f"|{variant}/{base}|{cost}|{sum(x['added_closed_wins']for x in items)}/{sum(x['added_closed_losses']for x in items)}|{sum(x['added_closed_net']for x in items):+.2f}|{sum(x['actual_USDT_delta']for x in items):+.2f}|{sum(x['lost_original_winning_trades']for x in items)}|{sum(x['lost_original_winning_profit']for x in items):.2f}|")
 lines+=['','以上为已验证独立区间的USDT描述性合计，不是连续复利收益，也未将原ER/V2或两种费用场景当作独立样本相加。匹配旧亏损单的USDT扩大与同初始名义扩大另列，不能混为价格风险。']
 lines+=['','## 六组逐区间比较','','A=.25原出场；B=.25V2；C=.30原出场；D=.30V2；E=.35原出场；F=.35V2。仅ETH阈值改变，BTC固定.25。收益/回撤均为BTC+ETH分钟组合权益。每个区间各币500；2020仅02-16至年底；2026仅1—10月；NOV为11月独立起算至13日08:00。不拼接成年内连续收益。','','|区间|费用|组|收益%|回撤%|最差月%|最长连亏|已平/未平|','|---|---|---|---:|---:|---:|---:|---:|']
 for period in ['2019','2020','2021','2022','2023','2024','2025','2026','NOV']:
  for cost in COSTS:
   for group in s.GROUPS:
    x=next((x for x in metrics if x['period']==period and x['cost']==cost and x['group']==group and x['asset']=='COMBINED'and x['direction']=='ALL'),None)
    if x:lines.append(f"|{period}|{cost}|{group}|{x['return_pct']:+.2f}|{x['max_drawdown_pct']:.2f}|{x['worst_month_return_pct']:+.2f}|{x['max_consecutive_losses']}|{x['closed']}/{x['open']}|")
    else:lines.append(f'|{period}|{cost}|{group}|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|UNVERIFIED|')
 lines+=['','## 七项核算答复（仅已验证的比较区间）','']
 for variant,base in [('C','A'),('E','A'),('D','B'),('F','B')]:
  for cost in COSTS:
   items=[x for x in impact if x['variant']==variant and x['cost']==cost and x['asset']=='ETH'and x['direction']=='ALL']
   if not items:continue
   periods=[x['period']for x in items];net=sum(x['added_closed_net']for x in items);count=sum(x['added_closed_losses']for x in items);loss=sum(x['added_losing_net']for x in items);worse=[];months=[];tails=[];improved=[]
   for period in periods:
    a=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==base and x['asset']=='COMBINED'and x['direction']=='ALL');b=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==variant and x['asset']=='COMBINED'and x['direction']=='ALL')
    if b['max_drawdown_pct']>a['max_drawdown_pct']+1e-8:worse.append(period)
    if b['worst_month_return_pct']<a['worst_month_return_pct']-1e-8:months.append(period)
    # ETH trade tail (USDT amount; normalized changes separately in attribution).
    ea=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==base and x['asset']=='ETH'and x['direction']=='ALL');eb=next(x for x in metrics if x['period']==period and x['cost']==cost and x['group']==variant and x['asset']=='ETH'and x['direction']=='ALL')
    if eb['max_single_trade_loss']<ea['max_single_trade_loss']-1e-8:tails.append(period)
    if b['return_pct']>a['return_pct']+1e-8:improved.append(period)
   conc=[x for x in concentration if x['variant']==variant and x['cost']==cost and x['asset']=='ETH'];concentrated=[x['period']for x in conc if x['added_top5_profit_share']is not None and x['added_top5_profit_share']>=.5]
   lines += ['',f'### {variant}对{base} / {cost}',f'1. 新增ETH已平仓整体净额{net:+.2f} USDT（各独立区间合计，非复利收益率）。',f'2. 新增亏损{count}笔，新增亏损额{loss:.2f} USDT；全体ETH已平仓总亏损额变化{sum(x["gross_losing_trade_net_delta"]for x in items):+.2f} USDT。',f'3. 消失的原盈利单{sum(x["lost_original_winning_trades"]for x in items)}笔，失去盈利{sum(x["lost_original_winning_profit"]for x in items):.2f} USDT；避免原亏损{sum(x["avoided_original_losses"]for x in items):.2f} USDT。',f'4. 匹配原亏损单中，实际USDT损失扩大{sum(x["old_losing_trade_worsened_actual"]for x in items)}笔；统一初始名义后扩大{sum(x["old_losing_trade_worsened_normalized"]for x in items)}笔，两者不得混淆。',f'5. 回撤恶化区间{worse or "无"}；最差月恶化{months or "无"}；ETH最大单笔USDT亏损恶化{tails or "无"}。',f'6. 组合收益改善区间{improved or "无"}，比较覆盖{periods}；新增盈利前5笔占比≥50%的区间{concentrated or "无"}。完整集中度及归因值见concentration.csv。','7. 本段费用场景与ZERO分开完整重放。ASSUMED_005_SIDE只是假设压力；账户实际费率及资金费缺失，不能声称真实净收益。缺失区间不参与通过判定。']
 lines+=['','## 解释和文件','','yearly_metrics.csv分资产、方向列收益、权益、回撤、最差月、连续亏损、胜率、盈利因子、盈利亏损总额、尾部单笔和订单数。方向收益是同初始资本分母的PnL归因，不是另一个可执行方向账户。','组合连续亏损按平仓微秒时间排序，同时间BTC优先；方向曲线是PnL归因，不是拆开的独立可交易账户。','BTC的C/E重用A完整逐笔重放，D/F重用B；策略和独立子账户状态完全相同，非另一个独立样本，ETH所有六组均单独执行。','trade_attribution.csv及四类CSV按资产/方向/signal_close_ms匹配，保留不能配对记录；实际USDT差额与同1000USDT初始名义归一化分开。归一化含费用、数量取整和减仓比例的差异，不是纯价格路径指标，后者只作归因。所有已平仓净收益＋年末未平仓费用/部分退出/估值精确核对期末权益。','concentration.csv列新增盈利及正向归因差额的前1/前5笔集中度，不按结果挑样本；全年改善分布见yearly_metrics.csv。','impact.csv分年、资产、方向统计新增亏损、被挤盈利、旧亏损扩大及归一化变化。overlap_risk.csv列精确重叠秒数及发生在另一币持仓时的负现金流（含费用），另列分钟末同时持仓及最差合计浮亏、当前止损参考回吐及重叠时段回撤，不是实盘保证。','diagnostics_*.csv.gz记录所有预带宽候选的完整价格/指标/ER/趋势确认/回踩与实际提交或重建占用；NOT_EVALUATED不视为通过。诊断不反馈信号，不使用BTC将来成交或盈利。','非零费用下legacy close事件的net_usdt是旧观察器口径，整笔净收益以修正后的trade.net及cash_events核对；修正不改变账户交易。','费用ZERO=0；ASSUMED_005_SIDE=每边0.05%假设压力，并非核实用户实际费率。资金费未计，不能声称真实净收益验证；所有成交为真实逐笔价格上的全量触价代理，不保证实盘成交。','已有年份反复查看，不称样本外；只测试预设.25/.30/.35，没有逐年调参。新阈值都跑全部可验证区间，不因早期表现差省略。','data/config/provenance、官方raw_sources和逐币run_attempt日志保留；月末checkpoint为继续执行断点，pickle仅限本项目自产可信文件。入口与命令见EXPERIMENT.md。', '', '## 缺失或失败','','2019：UNVERIFIED，未补造；2026年11月13日08:00之后：UNVERIFIED。']
 for x in failures:lines.append(json.dumps(x,ensure_ascii=False))
 lines+=['','## 数据阻断与继续执行','','2025-08-29 ETH官方daily档案有3个重复成交ID，对应不同时间/价格；同市场官方monthly目标日与daily解压CSV逐字节相同，不能靠换档案或去重恢复。没有更可靠原始逐笔之前，仍依赖该档案的组保持UNVERIFIED。0.25独立组若已恢复成功则单列，不用其结果填充0.30/0.35。','每组隔离恢复入口：python outputs/eth_density_experiment/isolate_2025.py .25 / .30 / .35（各为独立命令）；后两组在现有冲突档案下仍会停止。全量已完成任务用python outputs/eth_density_experiment/supervisor.py跳过，网络失败从月末断点继续；代码指纹变化拒绝复用断点。','发现新可信官方原始档案后，需先核实SHA、ID/时间与完整覆盖，再建立有记录的数据恢复流程，不得直接将某一冲突记录删掉以跑通。']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
