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
 if x=='True':return True
 if x=='False':return False
 try:return float(x)
 except(ValueError,TypeError):return x

def load_conditions(folder):
 with gzip.open(folder/'conditions.csv.gz','rt',encoding='utf-8-sig',newline='')as f:rows=[{k:decode(v)for k,v in r.items()}for r in csv.DictReader(f)]
 return{int(r['signal_close_ms']):r for r in rows}

def load(period,asset,cost,group):
 actual=group if asset=='ETH' else 'B'if s.GROUPS[group][1]else'A';folder=OUT/'runs'/period/asset;key=cost+'_'+actual
 status=h.read(folder/'status.json');assert status['completed']
 q=h.read(folder/f'{key}_result.json');marks=np.load(folder/f'{key}_equity.npy');return q,marks

def subset(q,side):return[t for t in q['trades']if t['side']==('LONG'if side==1 else'SHORT')]
def overlap(q1,q2,v1,v2,eq):
 mask=v1['active']&v2['active'];count=int(mask.sum());risk=v1['reference_stop_risk']+v2['reference_stop_risk'];notional=v1['gross_notional']+v2['gross_notional'];peak=np.maximum.accumulate(np.r_[1000.,eq])[1:]
 return dict(overlap_minutes=count,worst_combined_floating_PnL=float(min(0.,(v1['floating']+v2['floating'])[mask].min()))if count else 0.,max_reference_stop_giveback_USDT=float(risk[mask].max())if count else 0.,max_reference_stop_giveback_pct=float(np.max(100*risk[mask]/eq[mask]))if count else 0.,max_gross_notional_USDT=float(notional[mask].max())if count else 0.,max_combined_drawdown_during_overlap_pct=float(np.max(100*(1-eq[mask]/peak[mask])))if count else 0.)

def main():
 metrics=[];attribution=[];impact=[];monthly=[];failures=[];overlaps=[];decision_counts=[];completed=[]
 for period in PERIODS:
  try:
   for asset in ('BTC','ETH'):assert h.read(OUT/'runs'/period/asset/'status.json')['completed']
  except Exception as error:failures.append(dict(period=period,status='UNVERIFIED',error=repr(error)));continue
  features={a:load_conditions(OUT/'runs'/period/a)for a in ('BTC','ETH')}
  smaps={a:{float(k):{int(t):v for t,v in values.items()}for k,values in h.read(OUT/'runs'/period/a/'signals.json').items()}for a in ('BTC','ETH')}
  for cost in COSTS:
   loaded={};vectors={};decisions={};dec_rows=[]
   for asset in ('BTC','ETH'):
    for group in (list(s.GROUPS)if asset=='ETH'else['A','B']):
     q,marks=load(period,asset,cost,group);loaded[asset,group]=(q,marks);vectors[asset,group]=h.curve(q,marks)
     thr=s.GROUPS[group][0]if asset=='ETH'else .25
     signals=smaps[asset][thr];dec=h.diagnostic(q,features[asset],signals,thr);decisions[asset,group]=dec
     assert not any(x['execution_status']=='UNEXPLAINED_NO_ORDER'for x in dec.values()),(period,asset,cost,group,'unexplained decision')
     for item in dec.values():dec_rows.append(dict(period=period,cost=cost,group=group,asset=asset,**item))
     counts=Counter(x['execution_status']for x in dec.values());decision_counts.append(dict(period=period,cost=cost,group=group,asset=asset,**counts))
   for group in s.GROUPS:
    bg='B'if s.GROUPS[group][1]else'A';qb,mb=loaded['BTC',bg];qe,me=loaded['ETH',group];vb=vectors['BTC',bg];ve=vectors['ETH',group];combined=mb+me
    for asset,q,marks,vec,initial in [('BTC',qb,mb,vb,500.),('ETH',qe,me,ve,500.),('COMBINED',None,combined,None,1000.)]:
     trades=q['trades']if q else qb['trades']+qe['trades'];window=q['window']if q else qb['window'];opencount=int(bool(q['state_at_end']['position']))if q else int(bool(qb['state_at_end']['position']))+int(bool(qe['state_at_end']['position']))
     for side,direction in [(None,'ALL'),(1,'LONG'),(-1,'SHORT')]:
      ts=trades if side is None else[t for t in trades if t['side']==direction]
      values=marks if side is None else vec['directions'][side]if vec else vb['directions'][side]+ve['directions'][side]
      nopen=opencount if side is None else sum(1 for qq in ([q]if q else[qb,qe])if qq['state_at_end']['position']and qq['state_at_end']['position']['order']['side']==side)
      m=h.metrics(ts,values,initial,window,nopen);months=m.pop('monthly');m.update(period=period,cost=cost,group=group,asset=asset,direction=direction,return_scope='ACTUAL_ACCOUNT'if side is None else'DIRECTION_PNL_ATTRIBUTION_NOT_SEPARATE_ACCOUNT')
      if side is None:
       sq=[q]if q else[qb,qe];m.update(signals=sum(sum(int(window[0] and h.us(window[0]))<=int(t)*1000<h.us(window[1])for t in smaps[qq['asset']][s.GROUPS[group][0]if qq['asset']=='ETH'else .25])for qq in sq),submitted=sum(qq['stats'].get('submitted',0)for qq in sq),expired=sum(qq['stats'].get('expired',0)for qq in sq),funds_rejected=sum(qq['stats'].get('rejected',0)for qq in sq),opens=sum(qq['opens']for qq in sq),pending=sum(bool(qq['state_at_end']['pending_order'])for qq in sq))
      metrics.append(m)
      monthly.extend(dict(period=period,cost=cost,group=group,asset=asset,direction=direction,**x)for x in months)
    overlaps.append(dict(period=period,cost=cost,group=group,**overlap(qb,qe,vb,ve,combined)))
   for variant,base in [('C','A'),('E','A'),('D','B'),('F','B')]:
    for asset in ('BTC','ETH'):
     va=variant if asset=='ETH'else'B'if s.GROUPS[variant][1]else'A';ba=base if asset=='ETH'else'B'if s.GROUPS[base][1]else'A';old=loaded[asset,ba][0];new=loaded[asset,va][0]
     comparison=h.compare(old,new,decisions[asset,va]);comparison=[dict(period=period,cost=cost,asset=asset,variant=variant,base=base,**row)for row in comparison];attribution.extend(comparison)
     for direction in ('ALL','LONG','SHORT'):
      use=[x for x in comparison if direction=='ALL'or x['side']==direction];add=[x for x in use if x['category']=='ADDED'];lost=[x for x in use if x['category']=='DISAPPEARED'];matched=[x for x in use if x['category']in('RETAINED','CHANGED')]
      impact.append(dict(period=period,cost=cost,asset=asset,variant=variant,base=base,direction=direction,retained=sum(x['category']=='RETAINED'for x in use),changed=sum(x['category']=='CHANGED'for x in use),added=len(add),disappeared=len(lost),added_closed_wins=sum(x['new_status']=='CLOSED'and x['new_net']>0 for x in add),added_closed_losses=sum(x['new_status']=='CLOSED'and x['new_net']<0 for x in add),added_open=sum(x['new_status']=='OPEN'for x in add),added_winning_net=sum(x['new_net']for x in add if x['new_status']=='CLOSED'and x['new_net']>0),added_losing_net=-sum(x['new_net']for x in add if x['new_status']=='CLOSED'and x['new_net']<0),added_closed_net=sum(x['new_net']for x in add if x['new_status']=='CLOSED'),lost_original_winning_profit=sum(x['old_net']for x in lost if x['old_status']=='CLOSED'and x['old_net']>0),avoided_original_losses=-sum(x['old_net']for x in lost if x['old_status']=='CLOSED'and x['old_net']<0),old_losing_trade_worsened_actual=sum(x['old_status']=='CLOSED'and x['new_status']=='CLOSED'and x['old_net']<0 and x['new_net']<x['old_net']-1e-8 for x in matched),old_losing_trade_worsened_normalized=sum(x['old_status']=='CLOSED'and x['new_status']=='CLOSED'and x['old_net']<0 and x['new_normalized_1000']<x['old_normalized_1000']-1e-8 for x in matched),actual_USDT_delta=sum(x['actual_USDT_delta']for x in use),normalized_1000_delta=sum(x['normalized_1000_delta']for x in use),gross_losing_trade_net_delta=sum(max(0,-x['new_net'])if x['new_status']=='CLOSED'else 0 for x in use)-sum(max(0,-x['old_net'])if x['old_status']=='CLOSED'else 0 for x in use),disappearance_reasons=json.dumps(Counter(x['variant_reason']for x in lost),ensure_ascii=False)))
   s.csv_dump(OUT/f'diagnostics_{period}_{cost}.csv.gz',dec_rows)
   del loaded,vectors,decisions,dec_rows;gc.collect()
  completed.append(period);print('COLLECTED',period,flush=True)
 s.csv_dump(OUT/'yearly_metrics.csv',metrics);s.csv_dump(OUT/'monthly.csv',monthly);s.csv_dump(OUT/'trade_attribution.csv',attribution);s.csv_dump(OUT/'impact.csv',impact);s.csv_dump(OUT/'overlap_risk.csv',overlaps);s.csv_dump(OUT/'decision_counts.csv',decision_counts)
 for category in ('ADDED','DISAPPEARED','CHANGED','RETAINED'):s.csv_dump(OUT/f'trades_{category.lower()}.csv',[x for x in attribution if x['category']==category])
 s.dump(OUT/'analysis.json',dict(completed_periods=completed,failures=failures,metrics=metrics,impact=impact,overlap=overlaps,missing_2019='UNVERIFIED',fee_assumption='uniform0.05pct/side hypothetical; funding absent',base_commit=s.BASE_COMMIT))
 report(metrics,impact,overlaps,failures,completed)
 print('DONE',len(metrics),'metrics rows',len(attribution),'attribution rows',flush=True)

def report(metrics,impact,overlaps,failures,completed):
 lines=['# ETH历史密集阈值：固定六组逐笔实验','','## 当前结论','']
 if len(completed)!=len(PERIODS):lines+=['结果尚未完整，不能宣称任何放宽有效。缺失任务详见末尾；2019始终UNVERIFIED。']
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
 lines+=['','## 六组逐区间比较','','A=.25原出场；B=.25V2；C=.30原出场；D=.30V2；E=.35原出场；F=.35V2。仅ETH阈值改变，BTC固定.25。收益/回撤均为BTC+ETH分钟组合权益。每个区间各币500；2020仅02-16至年底；2026仅1—10月；NOV为11月独立起算至13日08:00。不拼接成年内连续收益。','','|区间|费用|组|收益%|回撤%|最差月%|最长连亏|已平/未平|','|---|---|---|---:|---:|---:|---:|---:|']
 for x in metrics:
  if x['asset']=='COMBINED'and x['direction']=='ALL':lines.append(f"|{x['period']}|{x['cost']}|{x['group']}|{x['return_pct']:+.2f}|{x['max_drawdown_pct']:.2f}|{x['worst_month_return_pct']:+.2f}|{x['max_consecutive_losses']}|{x['closed']}/{x['open']}|")
 lines+=['','## 解释和文件','','yearly_metrics.csv分资产、方向列收益、权益、回撤、最差月、连续亏损、胜率、盈利因子、盈利亏损总额、尾部单笔和订单数。方向收益是同初始资本分母的PnL归因，不是另一个可执行方向账户。','trade_attribution.csv及四类CSV按资产/方向/signal_close_ms匹配，保留不能配对记录；实际USDT差额与同1000USDT初始名义归一化分开。后者只作归因。所有已平仓净收益＋年末未平仓费用/部分退出/估值精确核对期末权益。','impact.csv分年、资产、方向统计新增亏损、被挤盈利、旧亏损扩大及归一化变化。overlap_risk.csv列同时持仓分钟、最差合计浮亏、当前止损参考回吐及重叠时段回撤，不是实盘保证。','diagnostics_*.csv.gz记录所有预带宽候选的完整价格/指标/ER/趋势确认/回踩与实际提交或重建占用；NOT_EVALUATED不视为通过。诊断不反馈信号，不使用BTC将来成交或盈利。','费用ZERO=0；ASSUMED_005_SIDE=每边0.05%假设压力，并非核实用户实际费率。资金费未计，不能声称真实净收益验证；所有成交为真实逐笔价格上的全量触价代理，不保证实盘成交。','已有年份反复查看，不称样本外；只测试预设.25/.30/.35，没有逐年调参。新阈值都跑全部可验证区间，不因早期表现差省略。','data/config/provenance、官方raw_sources和逐币run_attempt日志保留；月末checkpoint为继续执行断点，pickle仅限本项目自产可信文件。入口与命令见EXPERIMENT.md。', '', '## 缺失或失败','','2019：UNVERIFIED，未补造；2026年11月13日08:00之后：UNVERIFIED。']
 for x in failures:lines.append(json.dumps(x,ensure_ascii=False))
 (OUT/'report.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
