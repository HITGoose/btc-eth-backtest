from pathlib import Path
import ast,csv,json,math
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1]
tree=ast.parse((R/'outputs/adaptive_density_control/report.py').read_text());ns=dict(np=np,json=json,csv=csv)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['metrics','csvwrite','reason']],type_ignores=[]),'<original statistics>','exec'),ns)
FEES=['ZERO','MAKER_002_SIDE'];GROUPS=['A_BASE','A_VOL','A_FIXED_LOW'];rows=[];expos=[];trades=[];matches=[];down=[];checks=[];decomp=[];target=[];sizing=[]
def key(t):return(t['side'],int(t['signal_close_ms']))
def records(q):
 m={}
 for t in q['trades']:assert key(t)not in m;m[key(t)]=dict(t,record_type='CLOSED',contribution=t['net'],unrealized=0.,open_entry_fee=0.,entry_cash=t['opening_sleeve_cash_usdt'])
 p=q['state_at_end']['position']
 if p:
  o=p['order'];nom=o['price']*o['qty'];u=o['side']*o['qty']*(q['mark_price']-o['price']);t=dict(side='LONG'if o['side']==1 else'SHORT',signal_close_ms=int(o['signal_close_ms']),entry=o['price'],quantity=o['qty'],notional=nom,opened_us=q['state_at_end']['position_opened_us'],closed_us=None,exit=None,reason='OPEN_AT_END',record_type='OPEN_AT_END',net=None,contribution=u-q['fee']*nom,unrealized=u,open_entry_fee=q['fee']*nom,entry_cash=p['opening_cash']);assert key(t)not in m;m[key(t)]=t
 return m

def exposure(q,v,inp,prices):
 start,end=inp['start'],inp['end'];qty=np.zeros(len(v));secs=0.;weighted=0.
 for t in records(q).values():
  a=t['opened_us'];b=t.get('closed_us')or end*1000000
  lo=max(0,int(a//60000000-start//60));hi=min(len(qty),int(b//60000000-start//60));qty[lo:hi]=t['quantity'];duration=(min(b,end*1000000)-max(a,start*1000000))/1e6;secs+=duration;weighted+=t['notional']*duration
 gross=qty*prices;assert np.isfinite(v).all()and(v>0).all();lev=gross/v
 return gross,dict(minute_count=len(v),mean_minute_end_gross_equity=float(np.mean(lev)),max_minute_end_gross_equity=float(np.max(lev)),mean_gross_USDT=float(np.mean(gross)),holding_fraction=secs/(end-start),duration_weighted_entry_notional_USDT=weighted/(end-start))

def outcome(t):return'NO_BASE_FILL'if t is None else'BASE_OPEN_AT_END'if t['record_type']=='OPEN_AT_END'else'BASE_WIN'if t['net']>0 else'BASE_LOSS'if t['net']<0 else'BASE_FLAT'
for y in range(2020,2027):
 period=str(y)
 for fee in FEES:
  acc={}
  for asset in ['BTC','ETH']:
   folder=O/'runs'/period/asset
   if not(folder/'status_final.json').exists():continue
   inp=json.loads((folder/'input.json').read_text());data=np.load(Path(inp['data'])/(asset+'_1m.npy'),mmap_mode='r');i=(inp['start']-inp['minute_first'])//60;j=(inp['end']-inp['minute_first'])//60;prices=data[i:j,3];core={int(k):v for k,v in json.loads((folder/'signals.json').read_text())['A'].items()};diags={int(r['signal_close_ms']):r for r in csv.DictReader((folder/'volatility_signals.csv').open(encoding='utf-8-sig'))}
   for group in GROUPS:
    q=json.loads((folder/f'{fee}_{group}_result.json').read_text());v=np.load(folder/f'{fee}_{group}_equity.npz')['marks'];m=records(q);closed=sum(t['net']for t in q['trades']);u=sum(t['unrealized']for t in m.values());ef=sum(t['open_entry_fee']for t in m.values());cashres=q['cash']-500-closed+ef;eqres=q['ending_equity']-q['cash']-u;eventres=q['cash']-500-sum(t['delta']for t in q['cash_events']);assert max(abs(cashres),abs(eqres),abs(eventres),abs(v[-1]-q['ending_equity']))<1e-7
    gross,ex=exposure(q,v,inp,prices);lv=[t['notional']/t['entry_cash']for t in m.values()];submitted=[a for a in q['sizing_audit']if a['accepted']];rejects=[a for a in q['sizing_audit']if not a['accepted']];levtarget=[3. if group=='A_BASE'else a['target_leverage']for a in submitted];fillkeys=set(m);submitkeys={(core[a['signal_close_ms']],int(a['signal_close_ms']))for a in submitted};assert all(core[k[1]]==(1 if k[0]=='LONG'else-1)for k in m)
    ck=dict(period=period,asset=asset,fee_scenario=fee,group=group,cash_residual=cashres,equity_residual=eqres,cash_event_residual=eventres,all_fills_original_signals=True);checks.append(ck)
    r=dict(period=period,asset=asset,fee_scenario=fee,group=group,**ns['metrics'](v,500,q['trades']),net_pnl_USDT=q['ending_equity']-500,cash_USDT=q['cash'],closed_net_USDT=closed,end_unrealized_USDT=u,open_entry_fee_USDT=ef,open_count=sum(t['record_type']=='OPEN_AT_END'for t in m.values()),filled_count=len(m),avg_actual_entry_leverage=float(np.mean(lv))if lv else 0.,avg_submitted_target_leverage=float(np.mean(levtarget))if levtarget else 0.,submitted_orders=len(submitted),rejected_order_attempts=len(rejects),not_filled_submitted_orders=len(submitted)-len(m),fallback_signal_count=q.get('fallback_full_signal_count',0),fallback_submitted_count=q.get('fallback_submitted_count',0),minute_count=len(v),timeweighted_gross_equity=ex['mean_minute_end_gross_equity'],source=q['status']);rows.append(r);expos.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**ex,avg_actual_entry_leverage=r['avg_actual_entry_leverage']));acc[asset,group]=(q,v,m,gross,lv,levtarget)
    for t in m.values():trades.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,actual_entry_leverage=t['notional']/t['entry_cash'],r1000=1000*t['contribution']/t['notional'],**t))
    for a in q['sizing_audit']:
     targetL=3. if group=='A_BASE'else a['target_leverage'];d=diags[int(a['signal_close_ms'])];accepted=a['accepted'];nom=a['actual_notional'];price_events=[e for e in q['events']if e['event']=='order_sent'and int(e['signal_close_ms'])==int(a['signal_close_ms'])];p=price_events[0]['price']if price_events else None
     if accepted:
      assert nom<=a['realized_balance']*targetL+1e-7
      assert p is not None and a['realized_balance']*targetL-nom<p*(.0001 if asset=='BTC'else .01)+1e-7
     sizing.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**a,target_leverage_checked=targetL,target_notional_checked=a['realized_balance']*targetL,rounding_notional_shortfall_USDT=a['realized_balance']*targetL-nom if accepted else None,signal_L_VOL=float(d['target_L']),signal_fallback=d['fallback']))
   b,bv,aa,_,_,_=acc[asset,'A_BASE']
   for group in ['A_VOL','A_FIXED_LOW']:
    q,v,bb,_,_,_=acc[asset,group];new=[t for k,t in bb.items()if k not in aa];lost=[t for k,t in aa.items()if k not in bb];newnet=sum(t['contribution']for t in new);lostnet=sum(t['contribution']for t in lost);matched=sum(bb[k]['contribution']-a['contribution']for k,a in aa.items()if k in bb);delta=q['ending_equity']-b['ending_equity'];assert abs(delta-newnet+lostnet-matched)<1e-7
    decomp.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,account_difference_USDT=delta,new_fills=len(new),new_contribution_USDT=newnet,lost_fills=len(lost),lost_contribution_USDT=lostnet,matched_difference_USDT=matched,reconciliation_residual=delta-newnet+lostnet-matched))
    accepted=core
    for k in sorted(set(aa)|set(bb)):
     a=aa.get(k);t=bb.get(k);cat='NEW'if a is None else'DISAPPEARED'if t is None else'RETAINED'if all(a.get(x)==t.get(x)for x in ['record_type','opened_us','closed_us','entry','exit','quantity','contribution'])else'CHANGED';diag=diags[k[1]]
     z=dict(period=period,asset=asset,fee_scenario=fee,group=group,side=k[0],signal_close_ms=k[1],category=cat,base_outcome=outcome(a),base_contribution_USDT=a['contribution']if a else None,variant_contribution_USDT=t['contribution']if t else None,actual_difference_USDT=t['contribution']-a['contribution']if a and t else None,base_r1000=1000*a['contribution']/a['notional']if a else None,variant_r1000=1000*t['contribution']/t['notional']if t else None,r1000_difference=1000*(t['contribution']/t['notional']-a['contribution']/a['notional'])if a and t else None,base_notional_USDT=a['notional']if a else None,variant_notional_USDT=t['notional']if t else None,base_opened_us=a['opened_us']if a else None,variant_opened_us=t['opened_us']if t else None,base_closed_us=a.get('closed_us')if a else None,variant_closed_us=t.get('closed_us')if t else None,base_reason=a['reason']if a else None,variant_reason=t['reason']if t else None,absent_reason=ns['reason'](q,k[1],1 if k[0]=='LONG'else-1,accepted)if t is None else None,vol_target_L=float(diag['target_L']),vol_fallback=diag['fallback'])
     matches.append(z)
     if group=='A_VOL'and float(diag['target_L'])<3-1e-12:down.append(z)
   if period=='2024'and asset=='BTC':
    p=b['state_at_end']['position'];assert p;kk=('LONG'if p['order']['side']==1 else'SHORT',int(p['order']['signal_close_ms']))
    for group in GROUPS:
     q,_,m,_,_,_=acc[asset,group];t=m.get(kk);d=diags[kk[1]];target.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,signal_close_ms=kk[1],record_type=t['record_type']if t else'NO_FILL',entry=t['entry']if t else None,quantity=t['quantity']if t else None,notional_USDT=t['notional']if t else None,entry_cash_USDT=t['entry_cash']if t else None,actual_entry_leverage=t['notional']/t['entry_cash']if t else None,opened_us=t['opened_us']if t else None,holding_days=(q['window'][1]*1000-t['opened_us'])/86400000000 if t else None,contribution_USDT=t['contribution']if t else None,unrealized_USDT=t['unrealized']if t else None,open_entry_fee_USDT=t['open_entry_fee']if t else None,vol_target_L=float(d['target_L']),vol_fallback=d['fallback'],no_special_preservation_rule=True))
  for group in GROUPS:
   if('BTC',group)not in acc or('ETH',group)not in acc:continue
   a,av,aa,ag,al,at=acc['BTC',group];b,bv,bb,bg,bl,bt=acc['ETH',group];assert a['window']==b['window']and len(av)==len(bv);v=av+bv;gross=ag+bg;lv=gross/v;t=a['trades']+b['trades'];mr=list(aa.values())+list(bb.values());entry=al+bl;targets=at+bt
   r=dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,**ns['metrics'](v,1000,t),net_pnl_USDT=a['ending_equity']+b['ending_equity']-1000,cash_USDT=a['cash']+b['cash'],closed_net_USDT=sum(x['net']for x in t),end_unrealized_USDT=sum(x['unrealized']for x in mr),open_entry_fee_USDT=sum(x['open_entry_fee']for x in mr),open_count=sum(x['record_type']=='OPEN_AT_END'for x in mr),filled_count=len(mr),avg_actual_entry_leverage=float(np.mean(entry))if entry else 0.,avg_submitted_target_leverage=float(np.mean(targets))if targets else 0.,submitted_orders=sum(len([x for x in q['sizing_audit']if x['accepted']])for q in [a,b]),rejected_order_attempts=sum(len([x for x in q['sizing_audit']if not x['accepted']])for q in [a,b]),not_filled_submitted_orders=sum(len([x for x in q['sizing_audit']if x['accepted']])for q in [a,b])-len(mr),fallback_signal_count=sum(q.get('fallback_full_signal_count',0)for q in [a,b]),fallback_submitted_count=sum(q.get('fallback_submitted_count',0)for q in [a,b]),minute_count=len(v),timeweighted_gross_equity=float(np.mean(lv)),source='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS');rows.append(r);expos.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,minute_count=len(v),mean_minute_end_gross_equity=float(np.mean(lv)),max_minute_end_gross_equity=float(np.max(lv)),mean_gross_USDT=float(np.mean(gross)),avg_actual_entry_leverage=r['avg_actual_entry_leverage']))
index={(r['period'],r['asset'],r['fee_scenario'],r['group']):r for r in rows}
for r in rows:
 for g,label in [('A_BASE','base'),('A_FIXED_LOW','fixed_low')]:
  b=index.get((r['period'],r['asset'],r['fee_scenario'],g))
  if b:r['difference_vs_'+label+'_USDT']=r['net_pnl_USDT']-b['net_pnl_USDT'];r['drawdown_difference_vs_'+label+'_pp']=r['max_drawdown_pct']-b['max_drawdown_pct']
totals=[]
for stage,years in [('TRAIN_2020_2022',['2020','2021','2022']),('LATER_2023_2026',['2023','2024','2025','2026']),('ALL_7',[str(x)for x in range(2020,2027)])]:
 for fee in FEES:
  for asset in ['BTC','ETH','COMBINED']:
   for group in GROUPS:
    rr=[r for r in rows if r['period']in years and r['fee_scenario']==fee and r['asset']==asset and r['group']==group]
    if len(rr)!=len(years):continue
    total=dict(stage=stage,fee_scenario=fee,asset=asset,group=group,independent_intervals=len(rr),net_pnl_USDT=sum(r['net_pnl_USDT']for r in rr),closed_net_USDT=sum(r['closed_net_USDT']for r in rr),end_unrealized_USDT=sum(r['end_unrealized_USDT']for r in rr),open_entry_fee_USDT=sum(r['open_entry_fee_USDT']for r in rr),closed_trades=sum(r['closed_trades']for r in rr),total_loss_USDT=sum(r['total_loss_USDT']for r in rr),max_single_loss_USDT=max(r['max_single_loss_USDT']for r in rr),worst_annual_drawdown_pct=max(r['max_drawdown_pct']for r in rr),timeweighted_gross_equity=sum(r['timeweighted_gross_equity']*r['minute_count']for r in rr)/sum(r['minute_count']for r in rr),avg_actual_entry_leverage=sum(r['avg_actual_entry_leverage']*r['filled_count']for r in rr)/sum(r['filled_count']for r in rr),filled_count=sum(r['filled_count']for r in rr),fallback_submitted_count=sum(r['fallback_submitted_count']for r in rr),rejected_order_attempts=sum(r['rejected_order_attempts']for r in rr))
    for g,label in [('A_BASE','base'),('A_FIXED_LOW','fixed_low')]:
     base=[index.get((y,asset,fee,g))for y in years]
     if all(base):
      total['difference_vs_'+label+'_USDT']=total['net_pnl_USDT']-sum(r['net_pnl_USDT']for r in base);total['outperform_years_vs_'+label]=sum(r['net_pnl_USDT']>b['net_pnl_USDT']+1e-8 for r,b in zip(rr,base));total['lower_drawdown_years_vs_'+label]=sum(r['max_drawdown_pct']<b['max_drawdown_pct']-1e-8 for r,b in zip(rr,base))
    totals.append(total)
for name,v in [('annual.csv',rows),('exposure.csv',expos),('trades.csv',trades),('trade_matching.csv',matches),('downweighted_trade_matching.csv',down),('ledger_checks.csv',checks),('account_decomposition.csv',decomp),('btc_2024_long_position.csv',target),('sizing_audit.csv',sizing),('period_summary.csv',totals)]:ns['csvwrite'](O/name,v)
summary=[]
for fee in FEES:
 for stage,years in [('TRAIN_2020_2022',['2020','2021','2022']),('LATER_2023_2026',['2023','2024','2025','2026']),('ALL_7',[str(y)for y in range(2020,2027)])]:
  for asset in ['BTC','ETH','COMBINED']:
   for cat in ['BASE_WIN','BASE_LOSS','BASE_OPEN_AT_END','NO_BASE_FILL','BASE_FLAT']:
    rr=[r for r in down if r['fee_scenario']==fee and r['period']in years and(asset=='COMBINED'or r['asset']==asset)and r['base_outcome']==cat];paired=[r for r in rr if r['actual_difference_USDT']is not None]
    summary.append(dict(stage=stage,fee_scenario=fee,asset=asset,base_outcome=cat,signals=len(rr),matched_fills=len(paired),missing_variant=sum(r['category']=='DISAPPEARED'for r in rr),new_variant=sum(r['category']=='NEW'for r in rr),base_contribution_USDT=sum(r['base_contribution_USDT']or 0 for r in rr),variant_contribution_USDT=sum(r['variant_contribution_USDT']or 0 for r in rr),matched_actual_difference_USDT=sum(r['actual_difference_USDT']for r in paired),matched_sum_r1000_difference=sum(r['r1000_difference']for r in paired),matched_mean_r1000_difference=float(np.mean([r['r1000_difference']for r in paired]))if paired else None))
ns['csvwrite'](O/'downweighted_summary.csv',summary)
print('REPORT',len(rows),'annual rows',len(trades),'filled records',len(checks),'reconciled accounts',flush=True)
