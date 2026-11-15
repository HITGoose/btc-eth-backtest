"""Snapshots and descriptive reports; never turns a halted sampler into validated returns."""
from pathlib import Path
import sys,json,pickle,csv,gzip,hashlib,datetime
import online as n
O=n.O;s=n.s;np=n.np
def write(name,rows):
 if rows:s.z.csv_dump(O/name,rows)
def main():
 metrics=[];ledgers=[];timeline=[]
 for folder in sorted((O/'forward').iterdir()):
  if not folder.is_dir()or folder.name.endswith('_receipt_replay')or'RECOVERY_TEST'in folder.name:continue
  cp=folder/'checkpoint.pkl'
  if not cp.exists():timeline.append(dict(run=folder.name,status='STARTUP_FAILED_NO_ACCOUNT_CHECKPOINT'));continue
  with cp.open('rb')as f:e=pickle.load(f)
  e.audit();valid=not e.halts and e.last_clock>=e.t0*1000;cut=e.last_clock
  timeline.append(dict(run=folder.name,T0_UTC=n.utc(e.t0*1000),observed_last_received_UTC=n.utc(e.last_seen),financial_verified_cut_UTC=n.utc(cut)if cut>=e.t0*1000 else None,status='OBSERVED_REALTIME_SIMULATION'if valid else'UNVERIFIED_FINANCIAL_HALTED',halt_count=len(e.halts),first_halt=e.halts[0]if e.halts else None,raw_unique_validated_trade_messages=e.raw_count,forward_sample_sufficient=False))
  for (fill,g,a),x in e.books.items():
   rows=[r for r in e.marks if r['fill']==fill and r['group']==g and r['asset']==a and r['time_us']>e.t0*1000];values=np.array([500.]+[r['equity']for r in rows]);dd=float((1-values/np.maximum.accumulate(values)).max()*100)
   latest=e.latest.get(a,{}).get('price');eq=x.equity(latest)if latest is not None else x.cash;net=sum(t['net']for t in x.journal);pos=x.position
   open_contribution=(pos.order.side*(latest-pos.order.price)*pos.order.qty+getattr(pos,'partial_net',0.)+getattr(pos,'funding_pnl',0.)-x.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty))if pos else 0.
   assert abs(x.cash-500-sum(c['delta']for c in x.cash_events))<1e-7;assert abs(eq-500-net-open_contribution)<1e-7
   streak=longest=0
   for t in x.journal:streak=streak+1 if t['net']<0 else 0;longest=max(longest,streak)
   gp=sum(max(0,t['net'])for t in x.journal);gl=-sum(min(0,t['net'])for t in x.journal)
   def worst(period):
    groups={}
    for r in rows:
     d=datetime.datetime.fromtimestamp(r['time_us']/1e6,datetime.timezone(datetime.timedelta(hours=8)));key=d.strftime('%Y-%m-%d'if period=='day'else'%Y-%m');groups.setdefault(key,[]).append(r['equity'])
    previous=500.;out=[]
    for key,v in sorted(groups.items()):out.append(dict(period=key,return_pct=100*(v[-1]/previous-1)));previous=v[-1]
    return min(out,key=lambda x:x['return_pct'])if out and valid else None
   m=dict(run=folder.name,fill=fill,group=g,asset=a,status='VALIDATED_LEDGER_PREFIX_ONLY_SAMPLE_INSUFFICIENT'if valid else'UNVERIFIED_FINANCIAL_HALTED',return_pct=100*(eq/500-1)if valid else None,ending_equity=eq if valid else None,recorded_cash=x.cash,recorded_position=bool(x.position),pending_order=bool(x.order),closed=len(x.journal),open=int(bool(x.position)),max_drawdown_pct=dd if valid else None,worst_day=worst('day'),worst_month=worst('month'),longest_loss_streak=longest if valid else None,gross_profit=gp if valid else None,gross_loss=gl if valid else None,max_single_loss=min([0.]+[t['net']for t in x.journal])if valid else None,fees_recorded=x.stats.get('fees',0),funding_recorded=x.funding_total,slippage_recorded=x.slippage_cost,CORE_contribution=(sum(t['net']for t in x.journal if t.get('origin')=='CORE')+(open_contribution if pos and x.order_info['origin']=='CORE'else 0))if valid else None,EXTRA_contribution=(sum(t['net']for t in x.journal if t.get('origin')=='EXTRA')+(open_contribution if pos and x.order_info['origin']=='EXTRA'else 0))if valid else None,cash_reconciled=True,I25_V2_budget_rate=.03)
   metrics.append(m);state=s.b.p.state(x);pos=x.position
   if pos:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   q=dict(asset=a,period='FORWARD',key=g+'_'+fill,configuration=dict(group=g,fill=fill,fee=x.fee,slip=x.slippage),fee=x.fee,status=m['status'],window=[n.utc(e.t0*1000),n.utc(max(e.t0*1000,cut))],cash=x.cash,ending_equity=eq,source='OBSERVED_PUBLIC_WS_OR_REST_AS_LABELLED',trades=x.journal,events=x.events,driver_events=e.events,cash_events=x.cash_events,stats=dict(x.stats),state_at_end=state,open_contribution=open_contribution,actual_raw_last_mark=latest,open_partial_state={k:getattr(pos,k,None)for k in ['initial_quantity','partial_fills','partial_net','funding_pnl']}if pos else{},funding_events=x.funding_events,funding_total_USDT=x.funding_total,sizing_audit=x.sizing_audit,slippage_cost_USDT=x.slippage_cost,metric=m,valuation_unverified_after_halt=bool(e.halts),no_future_performance_claim=True)
   p=folder/'reports';p.mkdir(exist_ok=True);(p/(g+'_'+fill+'_'+a+'.json')).write_text(json.dumps(q));ledgers.append(dict(run=folder.name,path=str(p/(g+'_'+fill+'_'+a+'.json'))))
 combined=[]
 for run in sorted({r['run']for r in metrics}):
  for fill in ['F_TOUCH','F_THROUGH']:
   for g in ['B','I100','I50','I25']:
    rr=[r for r in metrics if r['run']==run and r['fill']==fill and r['group']==g]
    if len(rr)!=2:continue
    valid=all(r['return_pct']is not None for r in rr)
    combined.append(dict(run=run,fill=fill,group=g,asset='COMBINED',status='UNVERIFIED_FINANCIAL_HALTED'if not valid else'DESCRIPTIVE_SAMPLE_ONLY',return_pct=(sum(r['ending_equity']for r in rr)/1000-1)*100 if valid else None,ending_equity=sum(r['ending_equity']for r in rr)if valid else None,recorded_cash=sum(r['recorded_cash']for r in rr),closed=sum(r['closed']for r in rr),open=sum(r['open']for r in rr),fees_recorded=sum(r['fees_recorded']for r in rr),funding_recorded=sum(r['funding_recorded']for r in rr),slippage_recorded=sum(r['slippage_recorded']for r in rr),cash_reconciled=all(r['cash_reconciled']for r in rr),combination_risk_not_sum_of_asset_DD=True))
 metrics.extend(combined)
 write('forward_metrics.csv',metrics);(O/'forward_timeline.json').write_text(json.dumps(timeline,indent=2));(O/'forward_ledger_index.json').write_text(json.dumps(ledgers,indent=2))
 text=['# 实际前瞻/采集状态','', '原始采集与财务有效截止分开。HALTED行不提供收益/回撤，不把初始现金500误写成已验证0%收益；记录中的零手续费/零资金费只是尚无模拟交易的账本计数，不是未知成本填零。当前未形成可比较策略表现的有效样本。','']
 for t in timeline:text.append('```json\n'+json.dumps(t,ensure_ascii=False,indent=2)+'\n```')
 text+=['','全部已创建账本的现金/已实现/未平仓估值可对账，但数据闸门未通过不能当完整前瞻收益。历史估算与本次实时观察独立。原始消息、接收/进入模拟器时间、原响应SHA及哈希链在云端保留；未运行未来30/60/90天，不承诺环境常驻。','', '目前实际观察到官方WS的p=0,q=0,X=NA消息，未核实语义前严格拒绝，不用0价止损、不跳过伪造收益。部分后继ID gap是拒绝零价消息后的派生标记，不等于已证明网络丢包。API历史补查无密钥返回401，文档查询未取得NA语义正文；限制仍在。']
 (O/'FORWARD_STATUS.md').write_text('\n'.join(text)+'\n');print('FORWARD_REPORT',len(metrics),'book snapshots',len(timeline),'runs')
if __name__=='__main__':main()
