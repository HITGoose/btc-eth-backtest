from pathlib import Path
import csv,json,ast
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];tree=ast.parse((R/'outputs/adaptive_density_control/report.py').read_text());ns=dict(np=np,json=json,csv=csv);exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['metrics','csvwrite','reason']],type_ignores=[]),'<original statistics functions>','exec'),ns)
FEES=['ZERO','MAKER_002_SIDE'];GROUPS=['A_BASE','A_CANCEL'];PERIODS=[str(y)for y in range(2020,2027)];rows=[];trades=[];checks=[];cancel_rows=[];order_rows=[];match=[];decomp=[];target=[];request_rows=[];check_rows=[]
def key(t):return(t['side'],int(t['signal_close_ms']))
def records(q):
 m={}
 for t in q['trades']:assert key(t)not in m;m[key(t)]=dict(t,record_type='CLOSED',contribution=t['net'],unrealized=0.,open_entry_fee=0.)
 p=q['state_at_end']['position']
 if p:
  o=p['order'];nom=o['price']*o['qty'];u=o['side']*o['qty']*(q['mark_price']-o['price']);t=dict(side='LONG'if o['side']==1 else'SHORT',signal_close_ms=int(o['signal_close_ms']),entry=o['price'],quantity=o['qty'],notional=nom,opened_us=q['state_at_end']['position_opened_us'],closed_us=None,exit=None,reason='OPEN_AT_END',record_type='OPEN_AT_END',net=None,contribution=u-q['fee']*nom,unrealized=u,open_entry_fee=q['fee']*nom);assert key(t)not in m;m[key(t)]=t
 return m

def orders(q):
 out={}
 for e in q['events']:
  if e['event']=='order_sent':
   k=('LONG'if e['side']==1 else'SHORT',int(e['signal_close_ms']));assert k not in out;out[k]=dict(signal_close_ms=k[1],side=k[0],scheduled_submission_us=int(e.get('submitted_us',e['time_us'])),actual_submission_us=int(e.get('effective_submission_us')or e.get('submitted_us')or e['time_us']),price=e['price'],quantity=e['quantity'])
 return out

def validate(q,v):
 m=records(q);closed=sum(t['net']for t in q['trades']);u=sum(t['unrealized']for t in m.values());ef=sum(t['open_entry_fee']for t in m.values());a=q['cash']-500-closed+ef;b=q['ending_equity']-q['cash']-u;c=q['cash']-500-sum(t['delta']for t in q['cash_events']);assert max(abs(a),abs(b),abs(c),abs(v[-1]-q['ending_equity']))<1e-7;return m,dict(cash_residual=a,equity_residual=b,cash_event_residual=c)
def outcome(t):return'BASE_UNFILLED'if t is None else'BASE_OPEN_AT_END'if t['record_type']=='OPEN_AT_END'else'BASE_FILLED_LOSS'if t['net']<0 else'BASE_FILLED_PROFIT'if t['net']>0 else'BASE_FILLED_BREAKEVEN'
for period in PERIODS:
 for fee in FEES:
  acc={}
  for asset in ['BTC','ETH']:
   folder=O/'runs'/period/asset
   if not(folder/'status.json').exists():continue
   maps=json.loads((folder/'signals.json').read_text());assert maps['A_BASE']==maps['A_CANCEL'];core={int(k):v for k,v in maps['A_BASE'].items()}
   for group in GROUPS:
    q=json.loads((folder/f'{fee}_{group}_result.json').read_text());v=np.load(folder/f'{fee}_{group}_equity.npz')['marks'];m,ck=validate(q,v);acc[asset,group]=(q,v,m);checks.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**ck));rows.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**ns['metrics'](v,500,q['trades']),net_pnl_USDT=q['ending_equity']-500,cash_USDT=q['cash'],closed_net_USDT=sum(t['net']for t in q['trades']),end_unrealized_USDT=sum(t['unrealized']for t in m.values()),open_entry_fee_USDT=sum(t['open_entry_fee']for t in m.values()),open_count=sum(t['record_type']=='OPEN_AT_END'for t in m.values()),cancelled_orders=q['stats'].get('stale_cancelled',0)if group=='A_CANCEL'else 0,source=q['status']))
    for t in m.values():assert core.get(t['signal_close_ms'])==(1 if t['side']=='LONG'else-1);trades.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**t))
   b,bv,aa=acc[asset,'A_BASE'];q,vv,bb=acc[asset,'A_CANCEL'];bo=orders(b);vo=orders(q);cancelled={('LONG'if c['side']==1 else'SHORT',int(c['signal_close_ms'])):c for c in q['cancel_requests']if c['result']=='CANCELLED'};assert len(cancelled)==q['stats'].get('stale_cancelled',0);first=min(q['actual_cancel_times'],default=b['window'][1]*1000);ix=max(0,int(first//60000000-b['window'][0]//60000));diff=float(np.max(np.abs(vv[:ix]-bv[:ix])))if ix else 0.;assert diff<1e-8;checks[-1].update(prefix_before_first_actual_cancellation_matches=True,prefix_max_abs_difference=diff)
   for c in q['order_checks']:
    assert c['submitted_us']<c['check_ms']*1000 and c['check_ms']==c['bar_close_ms'] and c['check_ms']%900000==0;assert c['stale']==(c['close']<=c['band_high']if c['side']==1 else c['close']>=c['band_low']);check_rows.append(dict(period=period,asset=asset,fee_scenario=fee,**c))
   for c in q['cancel_requests']:
    k=('LONG'if c['side']==1 else'SHORT',int(c['signal_close_ms']));a=aa.get(k);order=bo.get(k);assert c['ready_ms']==c['check_ms']+60000
    if c['result']=='CANCELLED':assert c['result_us']==c['ready_ms']*1000 and k not in bb and c['cash_before']==c['cash_after']
    if c['result']=='FILLED_BEFORE_CANCEL':assert c['result_us']<c['ready_ms']*1000
    if c['result']=='EXPIRED_BEFORE_CANCEL':assert c['result_us']<=c['ready_ms']*1000
    cat=outcome(a)if order else'BASE_NO_SUBMITTED_ORDER';wait=(a['opened_us']-order['actual_submission_us'])/60000000 if a and order else None;basenorm=1000*a['contribution']/a['notional']if a else None;lossseq=bool(c['result']=='CANCELLED'and cat=='BASE_FILLED_LOSS'and c['submitted_us']<c['check_ms']*1000<c['result_us']<=a['opened_us'])
    if c['result']=='CANCELLED'and a:assert a['opened_us']>=c['result_us']
    r=dict(period=period,asset=asset,fee_scenario=fee,side=k[0],signal_close_ms=k[1],**{x:y for x,y in c.items()if x not in ['side','signal_close_ms']},base_outcome=cat,base_order_submitted=order is not None,base_actual_submission_us=order['actual_submission_us']if order else None,base_opened_us=a['opened_us']if a else None,base_closed_us=a.get('closed_us')if a else None,base_wait_to_fill_minutes=wait,base_net_or_marked_contribution_USDT=a['contribution']if a else 0. if order else None,base_initial_actual_filled_notional_USDT=a['notional']if a else None,base_r1000=basenorm,base_is_open_not_final_winner_or_loser=bool(a and a['record_type']=='OPEN_AT_END'),evidence_stale_then_later_fill_and_loss=lossseq)
    request_rows.append(r)
    if c['result']=='CANCELLED':cancel_rows.append(r)
   pending=b['state_at_end']['pending_order'];pendingkey=('LONG'if pending['side']==1 else'SHORT',int(pending['signal_close_ms']))if pending else None
   for k,o in bo.items():
    t=aa.get(k);bucket='CANCELLED_IN_VARIANT'if k in cancelled else'VAR_ORDER_PRESENT_NOT_CANCELLED'if k in vo else'BASE_ONLY_NO_VARIANT_ORDER';wait=(t['opened_us']-o['actual_submission_us'])/60000000 if t else None
    if t:assert wait>=0
    order_rows.append(dict(period=period,asset=asset,fee_scenario=fee,side=k[0],signal_close_ms=k[1],bucket=bucket,base_outcome=outcome(t),base_actual_submission_us=o['actual_submission_us'],base_scheduled_submission_us=o['scheduled_submission_us'],base_opened_us=t['opened_us']if t else None,base_wait_to_fill_minutes=wait,base_order_terminal='FILLED'if t else'PENDING_AT_END'if k==pendingkey else'EXPIRED',base_net_or_marked_USDT=t['contribution']if t else 0.,base_r1000=1000*t['contribution']/t['notional']if t else None))
   new=[r for k,r in bb.items()if k not in aa];lost=[r for k,r in aa.items()if k not in bb];matched=sum(bb[k]['contribution']-t['contribution']for k,t in aa.items()if k in bb);delta=q['ending_equity']-b['ending_equity'];nr=sum(t['contribution']for t in new);lr=sum(t['contribution']for t in lost);assert abs(delta-nr+lr-matched)<1e-7
   decomp.append(dict(period=period,asset=asset,fee_scenario=fee,account_difference_USDT=delta,new_fill_count=len(new),new_closed_net_USDT=sum(t['net']for t in new if t['record_type']=='CLOSED'),new_open_contribution_USDT=sum(t['contribution']for t in new if t['record_type']=='OPEN_AT_END'),new_all_contribution_USDT=nr,disappeared_fill_count=len(lost),disappeared_directly_cancelled_count=sum(key(t)in cancelled for t in lost),disappeared_other_count=sum(key(t)not in cancelled for t in lost),disappeared_closed_net_USDT=sum(t['net']for t in lost if t['record_type']=='CLOSED'),disappeared_open_contribution_USDT=sum(t['contribution']for t in lost if t['record_type']=='OPEN_AT_END'),disappeared_all_contribution_USDT=lr,matched_contribution_difference_USDT=matched))
   for k in sorted(set(aa)|set(bb)):
    a=aa.get(k);v=bb.get(k);category='NEW_FILL'if a is None else'DISAPPEARED_FILL'if v is None else'RETAINED'if all(a.get(x)==v.get(x)for x in ['record_type','entry','exit','quantity','opened_us','closed_us','contribution'])else'CHANGED';reason='STALE_ORDER_CANCELLED'if k in cancelled else ns['reason'](q,k[1],1 if k[0]=='LONG'else-1,core)if v is None else None
    match.append(dict(period=period,asset=asset,fee_scenario=fee,side=k[0],signal_close_ms=k[1],category=category,absent_reason=reason,directly_cancelled=k in cancelled,base_record_type=a['record_type']if a else None,variant_record_type=v['record_type']if v else None,A_net=a['contribution']if a else None,variant_net=v['contribution']if v else None,actual_difference_USDT=v['contribution']-a['contribution']if a and v else None,r1000_difference=1000*(v['contribution']/v['notional']-a['contribution']/a['notional'])if a and v else None,base_opened_us=a['opened_us']if a else None,variant_opened_us=v['opened_us']if v else None,base_notional=a['notional']if a else None,variant_notional=v['notional']if v else None,base_reason=a['reason']if a else None,variant_reason=v['reason']if v else None))
   if period=='2024'and asset=='BTC':
    p=b['state_at_end']['position'];assert p is not None;k=('LONG'if p['order']['side']==1 else'SHORT',int(p['order']['signal_close_ms']));a=aa[k];v=bb.get(k);o=bo[k];requests=[c for c in q['cancel_requests']if c['signal_close_ms']==k[1]];oc=[c for c in q['order_checks']if c['signal_close_ms']==k[1]];target.append(dict(period=period,asset=asset,fee_scenario=fee,signal_close_ms=k[1],base_wait_minutes=(a['opened_us']-o['actual_submission_us'])/60000000,base_holding_days=(b['window'][1]*1000-a['opened_us'])/86400000000,base_contribution_USDT=a['contribution'],variant_filled=v is not None,variant_cancelled=k in cancelled,variant_record_type=v['record_type']if v else None,variant_contribution_USDT=v['contribution']if v else None,variant_r1000_difference=1000*(v['contribution']/v['notional']-a['contribution']/a['notional'])if v else None,variant_order_checks=oc,variant_cancel_requests=requests,no_preservation_exception=True))
  for group in GROUPS:
   if('BTC',group)not in acc or('ETH',group)not in acc:continue
   a,av,aa=acc['BTC',group];b,bv,bb=acc['ETH',group];assert a['window']==b['window']and len(av)==len(bv);v=av+bv;t=a['trades']+b['trades'];ar=list(aa.values())+list(bb.values());rows.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,**ns['metrics'](v,1000,t),net_pnl_USDT=a['ending_equity']+b['ending_equity']-1000,cash_USDT=a['cash']+b['cash'],closed_net_USDT=sum(r['net']for r in t),end_unrealized_USDT=sum(r['unrealized']for r in ar),open_entry_fee_USDT=sum(r['open_entry_fee']for r in ar),open_count=sum(r['record_type']=='OPEN_AT_END'for r in ar),cancelled_orders=sum(q['stats'].get('stale_cancelled',0)for q in [a,b])if group=='A_CANCEL'else 0,source='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS'))
base={(r['period'],r['asset'],r['fee_scenario']):r for r in rows if r['group']=='A_BASE'}
for r in rows:
 b=base[r['period'],r['asset'],r['fee_scenario']];r.update(account_difference_vs_base_USDT=r['net_pnl_USDT']-b['net_pnl_USDT'],drawdown_difference_vs_base_pp=r['max_drawdown_pct']-b['max_drawdown_pct'])
totals=[];cancel_summary=[];wait_summary=[]
def mean(v):return float(np.mean(v))if v else None
def median(v):return float(np.median(v))if v else None
for fee in FEES:
 for asset in ['BTC','ETH','COMBINED']:
  for group in GROUPS:
   for stage,ys in [('2020_2022',['2020','2021','2022']),('2023_2026',['2023','2024','2025','2026']),('ALL7',PERIODS)]:
    rr=[r for r in rows if r['fee_scenario']==fee and r['asset']==asset and r['group']==group and r['period']in ys];tt=[t for t in trades if t['fee_scenario']==fee and(asset=='COMBINED'or t['asset']==asset)and t['group']==group and t['period']in ys and t['record_type']=='CLOSED'];totals.append(dict(fee_scenario=fee,asset=asset,group=group,stage=stage,completed_intervals=len(rr),net_pnl_USDT=sum(r['net_pnl_USDT']for r in rr),closed_net_USDT=sum(r['closed_net_USDT']for r in rr),unrealized_USDT=sum(r['end_unrealized_USDT']for r in rr),open_entry_fee_USDT=sum(r['open_entry_fee_USDT']for r in rr),account_difference_vs_base_USDT=sum(r['account_difference_vs_base_USDT']for r in rr),closed_trades=len(tt),win_rate_pct=100*sum(t['net']>0 for t in tt)/len(tt)if tt else None,worst_annual_drawdown_pct=max([r['max_drawdown_pct']for r in rr],default=None),years_net_improved=sum(r['account_difference_vs_base_USDT']>1e-8 for r in rr),years_drawdown_increased=sum(r['drawdown_difference_vs_base_pp']>1e-8 for r in rr)))
  for cat in ['BASE_UNFILLED','BASE_FILLED_LOSS','BASE_FILLED_PROFIT','BASE_FILLED_BREAKEVEN','BASE_OPEN_AT_END','BASE_NO_SUBMITTED_ORDER']:
   rr=[r for r in cancel_rows if r['fee_scenario']==fee and(asset=='COMBINED'or r['asset']==asset)and r['base_outcome']==cat];values=[r['base_r1000']for r in rr if r['base_r1000']is not None];cancel_summary.append(dict(fee_scenario=fee,asset=asset,base_outcome=cat,cancelled_count=len(rr),baseline_net_or_marked_USDT=None if cat=='BASE_NO_SUBMITTED_ORDER'else sum(r['base_net_or_marked_contribution_USDT']for r in rr if r['base_net_or_marked_contribution_USDT']is not None),r1000_N=len(values),r1000_mean=mean(values),r1000_median=median(values),r1000_sum=sum(values)if values else None,evidence_stale_then_fill_and_loss_count=sum(r['evidence_stale_then_later_fill_and_loss']for r in rr)))
  for bucket in ['CANCELLED_IN_VARIANT','VAR_ORDER_PRESENT_NOT_CANCELLED','BASE_ONLY_NO_VARIANT_ORDER']:
   rr=[r for r in order_rows if r['fee_scenario']==fee and(asset=='COMBINED'or r['asset']==asset)and r['bucket']==bucket];filled=[r for r in rr if r['base_wait_to_fill_minutes']is not None];vals=[r['base_wait_to_fill_minutes']for r in filled];wait_summary.append(dict(fee_scenario=fee,asset=asset,bucket=bucket,orders=len(rr),baseline_filled=len(filled),baseline_unfilled=len(rr)-len(filled),wait_fill_minutes_mean=mean(vals),wait_fill_minutes_median=median(vals),wait_fill_minutes_p90=float(np.quantile(vals,.9))if vals else None,base_filled_loss_count=sum(r['base_outcome']=='BASE_FILLED_LOSS'for r in rr),base_filled_profit_count=sum(r['base_outcome']=='BASE_FILLED_PROFIT'for r in rr),base_closed_net_USDT=sum(r['base_net_or_marked_USDT']for r in filled if r['base_outcome']not in ['BASE_OPEN_AT_END'])))
done={(r['period'],r['asset'],r['fee_scenario'],r['group'])for r in checks};missing=[dict(period=p,asset=a,fee=f,group=g,status='NOT_COMPLETED')for p in PERIODS for a in ['BTC','ETH']for f in FEES for g in GROUPS if(p,a,f,g)not in done]
for name,rs in [('annual.csv',rows),('totals_and_stages.csv',totals),('trades.csv',trades),('cancel_matching.csv',cancel_rows),('cancel_requests.csv',request_rows),('order_checks.csv',check_rows),('cancel_summary.csv',cancel_summary),('base_order_waiting.csv',order_rows),('waiting_summary.csv',wait_summary),('trade_matching.csv',match),('new_disappeared_reconciliation.csv',decomp),('btc_2024_long_hold.csv',target),('cash_checks.csv',checks),('incomplete.csv',missing)]:ns['csvwrite'](O/name,rs)
text='# 挂单失效撤销：固定A_BASE对照\n\n只增加已提交未成交挂单的收盘失效检查；多close<=六线max、空close>=六线min，等号及跨过整带均触发。每个提交后新的闭15m检查，第一次触发T+60秒的分钟起点撤单，原到期先处理，再撤同一原订单，最后价格撮合。此前成交请求失效，持仓按原fixed/cap5，不撤既有成交。没有A_FAIL_EXIT、V2、重挂/追价或新过滤。\n\nZERO/MAKER_002_SIDE每边0.02%假设、零资金费、0.02%退出滑点、年度每币500独立3x；原固定入场集合完全相同。15m信号+1m OHLC假设执行，不是RAW。2020仅02-16起，2026仅1—10月。净额含期末未平估值扣已付入场费；合计不是跨年复利或跨年最大回撤。\n\n'
for fee in FEES:
 text+='## '+fee+'\n\n|年|组|净额|相对A差|最大回撤%|已平N|胜率%|已平净额|期末浮盈|未平入场费|\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:
  if r['asset']=='COMBINED'and r['fee_scenario']==fee:text+=f"|{r['period']}|{r['group']}|{r['net_pnl_USDT']:.2f}|{r['account_difference_vs_base_USDT']:+.2f}|{r['max_drawdown_pct']:.2f}|{r['closed_trades']}|{r['win_rate_pct']or 0:.2f}|{r['closed_net_USDT']:.2f}|{r['end_unrealized_USDT']:.2f}|{r['open_entry_fee_USDT']:.4f}|\n"
 text+='\n|阶段|组|净额合计|相对A差|跑赢区间|回撤扩大区间|\n|---|---|---:|---:|---:|---:|\n'
 for r in totals:
  if r['asset']=='COMBINED'and r['fee_scenario']==fee:text+=f"|{r['stage']}|{r['group']}|{r['net_pnl_USDT']:.2f}|{r['account_difference_vs_base_USDT']:+.2f}|{r['years_net_improved']}/{r['completed_intervals']}|{r['years_drawdown_increased']}/{r['completed_intervals']}|\n"
 text+='\n### 实际撤单在基准中的结果\n\n未成交无实际成交名义，r1000留空；基准未提交同身份订单单列不强配。期末未平仅作估值，不判最终输赢。\n\n|基准结果|撤单N|基准净额/期末贡献|r1000N|逐笔均值|中位数|失效→撤单→基准成交亏损证据N|\n|---|---:|---:|---:|---:|---:|---:|\n'
 for r in cancel_summary:
  if r['asset']=='COMBINED'and r['fee_scenario']==fee:text+=f"|{r['base_outcome']}|{r['cancelled_count']}|{format(r['baseline_net_or_marked_USDT'],'.2f')if r['baseline_net_or_marked_USDT']is not None else'—'}|{r['r1000_N']}|{format(r['r1000_mean'],'.2f')if r['r1000_mean']is not None else'—'}|{format(r['r1000_median'],'.2f')if r['r1000_median']is not None else'—'}|{r['evidence_stale_then_fill_and_loss_count']}|\n"
 text+='\n### 基准等待到成交时间\n\n只对基准真实模拟成交订单计算等待；未成交不将TTL当成交等待。未在变体提交的基准订单另列，不冒充保留订单。此为事后描述，不是因果匹配试验。\n\n|订单分组|基准订单N|基准成交N|未成交N|成交等待均值min|中位min|P90min|亏损N|盈利N|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in wait_summary:
  if r['asset']=='COMBINED'and r['fee_scenario']==fee:text+=f"|{r['bucket']}|{r['orders']}|{r['baseline_filled']}|{r['baseline_unfilled']}|{format(r['wait_fill_minutes_mean'],'.2f')if r['wait_fill_minutes_mean']is not None else'—'}|{format(r['wait_fill_minutes_median'],'.2f')if r['wait_fill_minutes_median']is not None else'—'}|{format(r['wait_fill_minutes_p90'],'.2f')if r['wait_fill_minutes_p90']is not None else'—'}|{r['base_filled_loss_count']}|{r['base_filled_profit_count']}|\n"
text+='\n完整分币年度表在annual.csv；检查/计划/结果在cancel_requests.csv，实际撤单匹配cancel_matching.csv。其他新增/消失/变化成交见trade_matching.csv和new_disappeared_reconciliation.csv：完整权益差=新增成交贡献−消失成交贡献+匹配贡献变化。直接撤单与后续占用变化造成的消失分列，归因不是可直接加回基准的收益。\n\n'
for r in target:text+=f"2024BTC长期未平：{r['fee_scenario']}，基准等待{r['base_wait_minutes']:.2f}分钟，持有{r['base_holding_days']:.2f}天；变体是否成交{r['variant_filled']}，是否直接撤销{r['variant_cancelled']}，变体状态{r['variant_record_type']}、期末贡献{r['variant_contribution_USDT']}。完整请求/检查见btc_2024_long_hold.csv，无保护特例。\n\n"
text+=f'已对账{len(checks)}/56（28新回放、28引用基准），未完成{len(missing)}；首次实际撤单之前权益与基准一致，验证未改变原挂单/撮合/出场。原main及旧账本未改，未搜索新等待时间/两根确认/费用场景，不称新样本外。\n';(O/'CONCLUSION.md').write_text(text);print(json.dumps(dict(accounts=len(checks),incomplete=len(missing),actual_cancel_records=len(cancel_rows),request_records=len(request_rows))))
