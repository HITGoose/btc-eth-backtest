"""Read-only matrix/attribution; never fills missing costs or histories with zero."""
from pathlib import Path
from collections import Counter
import json,csv,gzip,hashlib
import shared as s
np=s.np;O=s.OUT;h=s.z.h
COSTS_ALL=dict(s.COSTS,C2=dict(fee=.0005,slip=.0002,funding=True),C3=dict(fee=.0005,slip=.0005,funding=True),C4=dict(fee=.00075,slip=.001,funding=True))
PERIODS=['2020','2021','2022','2023','2024','2025','2026','NOV']
def load(period,asset,cost,group,fill,scene):
 if asset=='BTC':group='B';scene='STRICT'
 key=cost+'_'+group+'_'+fill
 stage='baseline'if cost in ('C0','C1')and group in ('B','G','H','I100')and fill=='F_TOUCH'else'experiment'
 if cost in ('C2','C3','C4'):root=O/'funded';stage='funded'
 else:root=O
 if period in ('2024','2025','2026')and asset=='ETH'and cost in ('C0','C1')and group in ('I50','I25')and fill=='F_TOUCH':root=O/'sizing_only';stage='experiment'
 if fill=='F_THROUGH':root=O/'through_exact_clock';stage='through'
 folder=root/'runs'/period/asset/stage
 status=folder/'status.json'
 if not status.exists()or not json.loads(status.read_text()).get('completed'):raise FileNotFoundError(str(folder))
 path=folder/'results'/scene/(key+'_result.json')
 q=json.loads(path.read_text());marks=np.load(path.with_name(key+'_equity.npz'))['marks'];return q,marks

def rows(q):
 out=h.rows(q)
 for t in out:
  t['asset']=q['asset']
  if t['status']=='OPEN':
   order=q['state_at_end']['position']['order'];t['origin']=order['origin'];t['signal_close_ms']=order['signal_close_ms']
 return out

def reject_reason(q,stamp,trades):
 attempts=[x for x in q['sizing_audit']if x['signal_close_ms']==stamp]
 if any(not x['accepted']for x in attempts):return 'MIN_NOTIONAL_OR_FUNDS'
 if attempts:
  if any(e['event']=='priority_cancel_extra_order'and e['extra_signal_close_ms']==stamp for e in q['events']):return 'CANCELLED_BY_CORE'
  pending=q['state_at_end']['pending_order']
  if pending and pending.get('signal_close_ms')==stamp:return 'PENDING_AT_END'
  return 'LIMIT_EXPIRED_UNFILLED'
 clock=(stamp+10000)*1000
 held=next((x for x in trades if x['opened_us']<=clock<(x.get('closed_us')or s.z.h.us(q['window'][1]))),None)
 if held:return 'BLOCKED_POSITION_'+held.get('origin','UNKNOWN')+':'+str(held['signal_close_ms'])
 for e in q['events']:
  if e['event']!='order_sent':continue
  submitted=e.get('effective_submission_us')or e['time_us'];sig=e.get('signal_close_ms',e['time_us']//1000-10000)
  if submitted>clock:continue
  fill=next((x for x in trades if x['signal_close_ms']==sig),None)
  cancel=next((x['time_us']for x in q['events']if x['event']=='priority_cancel_extra_order'and x['extra_signal_close_ms']==sig),10**30)
  end=min(submitted+3600000000,fill['opened_us']if fill else 10**30,cancel)
  if clock<end:return 'BLOCKED_PENDING_ORDER:'+str(sig)
 if any(e['event']=='priority_replace_requested'and e['core_signal_close_ms']==stamp for e in q['events']):return 'WAITING_CORE_REPLACEMENT'
 if any(e['event']=='priority_duplicate_core_ignored'and e['core_signal_close_ms']==stamp for e in q['events']):return 'BLOCKED_PRIORITY_LOCK'
 return 'NOT_EVALUATED_NO_ORDER_CHECK'

def attribution(base,new,meta):
 key=lambda t:(t['asset'],t['side'],int(t['signal_close_ms']))
 old={key(t):t for t in rows(base)};now={key(t):t for t in rows(new)};assert len(old)==len(rows(base))and len(now)==len(rows(new));result=[]
 for k in sorted(old.keys()|now.keys(),key=lambda x:x[2]):
  a,c=old.get(k),now.get(k)
  if a and c:
   fields=['opened_us','closed_us','quantity','entry','exit','rung','status']
   partial=lambda t:[(v['time_us'],v['quantity'],v['execution_price'])for v in t.get('partial_fills',[])]
   category='RETAINED'if all(a.get(f)==c.get(f)for f in fields)and partial(a)==partial(c)else'CHANGED'
  else:category='ADDED'if c else'DISAPPEARED'
  val=lambda t:t['contribution']if t else 0.
  norm=lambda t:val(t)/(t['entry']*t['quantity'])*1000 if t else 0.
  attempts=[x for x in new['sizing_audit']if x['signal_close_ms']==k[2]]
  status=reject_reason(new,k[2],list(now.values()))if a and not c else'ACTUAL_ACCOUNT_MATCH'
  result.append(dict(meta,asset=k[0],direction=k[1],signal_close_ms=k[2],category=category,old_origin=a.get('origin')if a else None,new_origin=c.get('origin')if c else None,old_actual_contribution_USDT=val(a),new_actual_contribution_USDT=val(c),actual_USDT_delta=val(c)-val(a),old_normalized_1000=norm(a),new_normalized_1000=norm(c),normalized_1000_delta=norm(c)-norm(a),old_opened_us=a.get('opened_us')if a else None,new_opened_us=c.get('opened_us')if c else None,old_closed_us=a.get('closed_us')if a else None,new_closed_us=c.get('closed_us')if c else None,old_quantity=a.get('quantity')if a else None,new_quantity=c.get('quantity')if c else None,old_entry=a.get('entry')if a else None,new_entry=c.get('entry')if c else None,old_exit=a.get('exit')if a else None,new_exit=c.get('exit')if c else None,old_rung=a.get('rung')if a else None,new_rung=c.get('rung')if c else None,old_partial_fills=json.dumps(a.get('partial_fills',[]))if a else None,new_partial_fills=json.dumps(c.get('partial_fills',[]))if c else None,old_net=a.get('net')if a else None,new_net=c.get('net')if c else None,reason=status))
 assert abs(sum(x['actual_USDT_delta']for x in result)-(new['ending_equity']-base['ending_equity']))<1e-7
 return result

def write(name,rows):
 if rows:s.z.csv_dump(O/name,rows)
 else:(O/name).write_text('NO_RECORDS\n')

def cases_for(period):
 primary=[(c,g,'F_TOUCH')for c in ['C0','C1','C2','C3','C4']for g in s.GROUPS]+[('C2',g,'F_THROUGH')for g in ['B','I100','I50','I25']]
 if period in ('2020','2021','2022','2023','NOV'):
  primary +=[(c,g,'F_TOUCH')for c in ['C3_NO_FUNDING','C4_NO_FUNDING']for g in s.GROUPS]
 if period in ('2020','2021','2022','2023'):primary +=[('C1',g,'F_THROUGH')for g in ['B','I100','I50','I25']]
 return primary
def main():
 metrics=[];availability=[];attrs=[];ce=[];checks=[];overlap=[];monthly=[];baseline=[];drawdowns=[]
 cases=[(c,g,'F_TOUCH')for c in COSTS_ALL for g in s.GROUPS]+[(c,g,'F_THROUGH')for c in ['C1','C2']for g in ['B','I100','I50','I25']]
 for period in PERIODS:
  scenes=s.b.SCENARIOS if period=='2025'else ['STRICT']
  btc_cache={}
  for cost,group,fill in cases_for(period):
   eth_vector_cache={}
   for scene in scenes:
    meta=dict(period=period,scenario=scene,cost=cost,group=group,fill=fill)
    try:
     bkey=(cost,fill)
     if bkey in btc_cache:qb,mb,vb=btc_cache[bkey]
     else:
      qb,mb=load(period,'BTC',cost,group,fill,scene);vb=h.curve(qb,mb);btc_cache[bkey]=(qb,mb,vb)
     qe,me=load(period,'ETH',cost,group,fill,scene)
    except FileNotFoundError as e:
     reason=str(e)
     if cost in ('C2','C3','C4'):
      src=O/'funding_data'/period/'ETH/result.json'
      if src.exists():
       data=json.loads(src.read_text())
       if data['status']!='COMPLETE':reason='OFFICIAL_SETTLEMENT_MARK_PRICE_MISSING:'+str(len(data['invalid_records']))+' ETH events; full-year funded path not executed'
     availability.append(dict(meta,status='UNVERIFIED',reason=reason));continue
    availability.append(dict(meta,status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'else'COMPLETE',funding=qe['funding']))
    payload={k:qe.get(k)for k in ['asset','fee','window','cash','trades','events','cash_events','state_at_end','open_partial_state','open_contribution']}
    signature=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()+me.tobytes()).hexdigest()
    if signature in eth_vector_cache:ve=eth_vector_cache[signature]
    else:ve=h.curve(qe,me);eth_vector_cache[signature]=ve
    for asset,q,marks,vec,initial in [('BTC',qb,mb,vb,500.),('ETH',qe,me,ve,500.),('COMBINED',None,mb+me,None,1000.)]:
     qs=[q]if q else[qb,qe];ts=[t for qq in qs for t in qq['trades']]
     for side,direction in [(None,'ALL'),(1,'LONG'),(-1,'SHORT')]:
      tt=ts if side is None else[t for t in ts if t['side']==direction]
      values=marks if side is None else vec['directions'][side]if vec else vb['directions'][side]+ve['directions'][side]
      opened=sum(bool(qq['state_at_end']['position'])and(side is None or qq['state_at_end']['position']['order']['side']==side)for qq in qs)
      m=h.metrics(tt,values,initial,qs[0]['window'],opened);months=m.pop('monthly');m.update(meta,asset=asset,direction=direction,status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'else'COMPLETE',funding=qe['funding'],scope='ACTUAL_ACCOUNT'if side is None else'DIRECTION_ATTRIBUTION_NOT_SEPARATE_ACCOUNT')
      fees=sum(qq['fee']*sum(t['entry']*t['quantity']+sum(f['execution_price']*f['quantity']for f in t.get('partial_fills',[]))+(t['exit']*t['final_exit_quantity']if t['status']=='CLOSED'else 0.)for t in rows(qq)if side is None or t['side']==direction)for qq in qs)
      fund_events=[f for qq in qs for f in qq.get('funding_events',[])if side is None or f['side']==side]
      included=all(qq['funding']=='INCLUDED_OFFICIAL'for qq in qs)
      m.update(fees_USDT=fees,funding_receipts_USDT=sum(max(0.,f['delta'])for f in fund_events)if included else None,funding_payments_USDT=-sum(min(0.,f['delta'])for f in fund_events)if included else None,net_profit_USDT=m['ending_equity']-initial);metrics.append(m);monthly.extend(dict(meta,asset=asset,direction=direction,**x)for x in months)
    for qq,eq in [(qb,mb),(qe,me)]:
     allrows=rows(qq);err=qq['ending_equity']-500-sum(t['net']for t in qq['trades'])-qq['open_contribution'];cerr=qq['cash']-500-sum(x['delta']for x in qq['cash_events']);assert abs(err)<1e-7 and abs(cerr)<1e-7
     slip=COSTS_ALL[cost]['slip'];slipcalc=0.
     for t in allrows:
      if t['status']=='CLOSED':slipcalc+=t['exit']/(1-(1 if t['side']=='LONG'else-1)*slip)*t['final_exit_quantity']*slip
      slipcalc+=sum(f['trigger_print']*f['quantity']*slip for f in t.get('partial_fills',[]))
     assert abs(slipcalc-qq['slippage_cost_USDT'])<1e-7,(meta,qq['asset'],'slippage check',slipcalc,qq['slippage_cost_USDT'])
     checks.append(dict(meta,asset=qq['asset'],closed_net=sum(t['net']for t in qq['trades']),open_contribution=qq['open_contribution'],cash=qq['cash'],ending_equity=qq['ending_equity'],cash_residual=cerr,equity_residual=err,slippage_USDT=slipcalc,fees_USDT=qq['stats'].get('fees',0.),funding_included=qq['funding']=='INCLUDED_OFFICIAL',funding_total_USDT=qq.get('funding_total_USDT'),funding_receipts_USDT=sum(max(0.,e['delta'])for e in qq.get('funding_events',[]))if qq['funding']=='INCLUDED_OFFICIAL'else None,funding_payments_USDT=-sum(min(0.,e['delta'])for e in qq.get('funding_events',[]))if qq['funding']=='INCLUDED_OFFICIAL'else None))
     if qq.get('baseline_exact_trade_cash_equity_minutes'):baseline.append(dict(meta,asset=qq['asset'],exact=True,reused_BTC=qq.get('BTC_baseline_reused',False)))
     for origin in ('CORE','EXTRA'):
      tr=[t for t in allrows if t.get('origin')==origin];closed=[t for t in tr if t['status']=='CLOSED'];partial=[t for t in tr if t.get('partial_fills')];attempt=[a for a in qq['sizing_audit']if a['origin']==origin]
      allreq=[e for e in qq['events']if e['event']=='adaptive_v2_request']
      req=[e for e in allreq if any(t['opened_us']<e['time_us']<=(t.get('closed_us')or h.us(qq['window'][1])-1)for t in tr)]
      turnover=sum(t['entry']*t['quantity']+sum(f['execution_price']*f['quantity']for f in t.get('partial_fills',[]))+(t['exit']*t['final_exit_quantity']if t['status']=='CLOSED'else 0.)for t in tr)
      source_slip=sum((t['exit']/(1-(1 if t['side']=='LONG'else-1)*slip)*t['final_exit_quantity']*slip if t['status']=='CLOSED'else 0.)+sum(f['trigger_print']*f['quantity']*slip for f in t.get('partial_fills',[]))for t in tr)
      funds=[f for f in qq.get('funding_events',[])if any(t['opened_us']<f['time_ms']*1000<=(t.get('closed_us')or h.us(qq['window'][1])-1)for t in tr)]
      ce.append(dict(meta,asset=qq['asset'],origin=origin,closed=len(closed),open=sum(t['status']=='OPEN'for t in tr),net_closed_USDT=sum(t['net']for t in closed),total_contribution_USDT=sum(t['contribution']for t in tr),initial_notional=sum(t['entry']*t['quantity']for t in tr),mean_initial_notional=np.mean([t['entry']*t['quantity']for t in tr])if tr else None,partial_trades=len(partial),mean_actual_reduction_fraction=np.mean([sum(f['quantity']for f in t['partial_fills'])/t['quantity']for t in partial])if partial else 0.,mean_reduction_fraction_all_trades=np.mean([sum(f['quantity']for f in t.get('partial_fills',[]))/t['quantity']for t in tr])if tr else 0.,V2_requests=len(req),minimum_rejections=sum(not a['accepted']for a in attempt),expired_account=qq['stats'].get('expired',0),replacements_account=sum(e['event']=='priority_replace_requested'for e in qq['events']),slippage_USDT=source_slip,fees_USDT=turnover*qq['fee'],funding_receipts_USDT=sum(max(0.,f['delta'])for f in funds)if qq['funding']=='INCLUDED_OFFICIAL'else None,funding_payments_USDT=-sum(min(0.,f['delta'])for f in funds)if qq['funding']=='INCLUDED_OFFICIAL'else None,account_counts_repeated_per_origin=True))
    both=vb['active']&ve['active'];risk=vb['reference_stop_risk']+ve['reference_stop_risk'];gross=vb['gross_notional']+ve['gross_notional'];curve=mb+me
    changes=np.diff(np.r_[1000.,curve]);overlap.append(dict(meta,overlap_minutes=int(both.sum()),max_simultaneous_stop_reference_USDT=float(risk[both].max())if both.any()else 0.,max_gross_notional_USDT=float(gross[both].max())if both.any()else 0.,worst_overlapping_minute_equity_change_USDT=float(changes[both].min())if both.any()else 0.,not_a_guaranteed_loss_bound=True))
    values=np.r_[1000.,curve];dd=1-values/np.maximum.accumulate(values);trough=int(np.argmax(dd));peak=int(np.argmax(values[:trough+1]));start=s.z.h.us(qe['window'][0])
    value=lambda a,i:500. if i==0 else float(a[i-1])
    drawdowns.append(dict(meta,peak_time_us=start+peak*60000000,trough_time_us=start+trough*60000000,peak_equity=float(values[peak]),trough_equity=float(values[trough]),drawdown_pct=float(dd[trough])*100,BTC_peak=value(mb,peak),BTC_trough=value(mb,trough),ETH_peak=value(me,peak),ETH_trough=value(me,trough),BTC_change=value(mb,trough)-value(mb,peak),ETH_change=value(me,trough)-value(me,peak)))
    if group!='B':
     try:base,_=load(period,'ETH',cost,'B',fill,scene)
     except FileNotFoundError:continue
     attrs.extend(attribution(base,qe,dict(meta,comparison_base='B')))
     attrs.extend(attribution(qb,qb,dict(meta,comparison_base='B')))
     if group in ('I50','I25'):
      try:full,_=load(period,'ETH',cost,'I100',fill,scene)
      except FileNotFoundError:continue
      attrs.extend(attribution(full,qe,dict(meta,comparison_base='I100')))
      attrs.extend(attribution(qb,qb,dict(meta,comparison_base='I100')))
 index={(m['period'],m['scenario'],m['cost'],m['fill'],m['asset'],m['direction'],m['group']):m for m in metrics}
 for m in metrics:
  base=index.get((m['period'],m['scenario'],m['cost'],m['fill'],m['asset'],m['direction'],'B'))
  if base:m.update(relative_B_USDT=m['ending_equity']-base['ending_equity'],relative_B_return_pp=m['return_pct']-base['return_pct'],relative_B_DD_pp=m['max_drawdown_pct']-base['max_drawdown_pct'],relative_B_total_loss_USDT=m['gross_losing_trade_net']-base['gross_losing_trade_net'])
 write('annual_matrix.csv',metrics);write('monthly_matrix.csv',monthly);write('availability.csv',availability);write('trade_attribution.csv.gz',attrs);write('core_extra.csv',ce);write('cash_cost_reconciliation.csv',checks);write('overlapping_exposure.csv',overlap);write('baseline_regression.csv',baseline);write('drawdown_extremes.csv',drawdowns)
 for category in ['RETAINED','ADDED','DISAPPEARED','CHANGED']:
  chosen=[x for x in attrs if x['category']==category]
  if chosen:write('trades_'+category.lower()+'.csv.gz',chosen)
  else:
   with gzip.open(O/('trades_'+category.lower()+'.csv.gz'),'wt',encoding='utf-8-sig',newline='')as f:csv.DictWriter(f,fieldnames=list(attrs[0])if attrs else ['period','scenario','cost','group','fill','asset','direction','signal_close_ms','category']).writeheader()
 ranges=[]
 for cost,group,fill in cases_for('2025'):
  vals=[m for m in metrics if m['period']=='2025'and m['cost']==cost and m['group']==group and m['fill']==fill and m['asset']=='COMBINED'and m['direction']=='ALL']
  for field in ['ending_equity','return_pct','max_drawdown_pct','gross_losing_trade_net','max_single_trade_loss','closed','fees_USDT']:
   ranges.append(dict(cost=cost,group=group,fill=fill,metric=field,completed_scenarios=len(vals),minimum=min(x[field]for x in vals)if vals else None,maximum=max(x[field]for x in vals)if vals else None,span=max(x[field]for x in vals)-min(x[field]for x in vals)if vals else None,status='COMPLETED_WITH_DATA_ANOMALY'if len(vals)==9 else'UNVERIFIED'))
 write('2025_scenario_ranges.csv',ranges)
 table=[m for m in metrics if m['asset']=='COMBINED'and m['direction']=='ALL'and m['scenario']in ('STRICT','S_ALL')];write('mobile_annual.csv',table)
 comparisons=[]
 for m in table:
  if m['group']not in ('I100','I50','I25','G','H'):continue
  base=next((v for v in table if v['period']==m['period']and v['cost']==m['cost']and v['fill']==m['fill']and v['group']=='B'),None)
  full=next((v for v in table if v['period']==m['period']and v['cost']==m['cost']and v['fill']==m['fill']and v['group']=='I100'),None)
  if base:
   advantage=m['ending_equity']-base['ending_equity'];original=full['ending_equity']-base['ending_equity']if full else None
   comparisons.append(dict(period=m['period'],cost=m['cost'],fill=m['fill'],group=m['group'],advantage_USDT=advantage,drawdown_delta_pp=m['max_drawdown_pct']-base['max_drawdown_pct'],I100_advantage_USDT=original,advantage_retained_pct=100*advantage/original if original is not None and original>1e-7 else None))
 write('relative_B.csv',comparisons)
 text=['# 固定EXTRA仓位与交易成本：实际执行报告','', '**按实际完成状态列示。2020—2023缺完整结算标记价格，含资金费全年结果未验证；2024/2025/2026/NOV另运行官方精确资金费C2—C4。不能混用含与不含资金费结果。**','', '每区间每币500，独立起算，非跨年复利。2025仅异常假设敏感性，本简表固定展示S_ALL，九情景范围见2025_scenario_ranges.csv；其他区间保留严格标签，2019未验证。已有年份不是样本外。F_THROUGH为越一tick的保守模拟代理，非真实排队概率。','', '|区间|成本|成交|版本|收益%|回撤%|期末U|','|---|---|---|---|---:|---:|---:|']
 for m in table:text.append(f"|{m['period']}|{m['cost']}|{m['fill']}|{m['group']}|{m['return_pct']:.3f}|{m['max_drawdown_pct']:.3f}|{m['ending_equity']:.3f}|")
 text+=['','## 核验与限制',f'完整账户核对{len(checks)}项，原基准逐笔/现金/期末/完整分钟数组精确回归{len(baseline)}项。', '资金费主API451，后发现官方www.binance.com/fapi/v1/fundingRate可用；其返回精确fundingTime、费率及markPrice。2020—2022所有markPrice为空，2023有911条缺价，因此全年含资金费未验证；2024/25/26/NOV数据完整后进入实际现金回放。缺失不补零、不用K线开盘价、不按固定8小时近似。NO_FUNDING附加结果与C2—C4严格分列。', '完整状态共享只在2025重新检查；保留各情景自己的历史分钟权益。结论应先看availability，缺失不填零。', 'CORE/EXTRA归因见core_extra.csv；带_account后缀的过期/替换为账户总数重复列示，不能加两次；V2请求、手续费、滑点和资金费均按实际持仓来源分别分配。滑点以实际退出成交价、方向和数量计算，并与执行时账户累计逐项对账。', '各交易实际与同初始名义1000归一化差异分开，归一化不是另一条可执行账户。', '未满足完整多年份/资金费条件时，不宣布可替换B，不按年份挑仓位。']
 (O/'report.md').write_text('\n'.join(text)+'\n');s.dump(O/'analysis.json',dict(metrics_rows=len(metrics),complete_portfolio_cases=len(table),cash_checks=len(checks),baseline_exact=len(baseline),attribution_rows=len(attrs),funding_matrix_complete=False,funding_complete_periods=['2024','2025','2026','NOV'],funding_incomplete_periods=['2020','2021','2022','2023'],conclusion='早年完整资金费未验证；已完成区间按固定矩阵判断，不能推断全历史实盘净优势',configurations_fixed=True))
 print('REPORT',len(table),'portfolio cases',len(checks),'cash checks')
if __name__=='__main__':main()
