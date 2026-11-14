from datetime import datetime,timedelta,timezone
import json,math,gzip,csv
import numpy as np
TZ=timezone(timedelta(hours=8))
def us(text):return round(datetime.fromisoformat(text).timestamp()*1e6)
def time_s(stamp):return datetime.fromtimestamp(stamp/1e6,TZ).isoformat(timespec='milliseconds')
def read(path):return json.loads(path.read_text())
def rows(q):
 result=[dict(t,status='CLOSED',contribution=t['net'])for t in q['trades']]
 pos=q['state_at_end']['position']
 if pos:
  order=pos['order'];initial=q.get('open_partial_state',{}).get('initial_quantity')or order['qty'];fills=q.get('open_partial_state',{}).get('partial_fills')or[]
  result.append(dict(signal_close_ms=order.get('signal_close_ms',order['time']-10000),signal_ms=order['time'],submitted_us=round(order['time']*1000),origin=order.get('origin'),opened_us=q['state_at_end']['position_opened_us'],closed_us=None,side='LONG'if order['side']==1 else'SHORT',entry=order['price'],quantity=initial,final_exit_quantity=order['qty'],partial_fills=fills,partial_net=sum(x['net_usdt']for x in fills),entry_fee_usdt=q['fee']*initial*order['price'],net=None,status='OPEN',contribution=q['open_contribution'],exit=None))
 return result

def curve(q,marks):
 alltrades=rows(q);entry_turnover=sum(t['entry']*t['quantity']for t in alltrades);exit_turnover=sum(sum(f['execution_price']*f['quantity']for f in t.get('partial_fills',[]))+(t['exit']*t.get('final_exit_quantity',t['quantity'])if t['status']=='CLOSED'else 0)for t in alltrades)
 assert abs(q['stats'].get('fees',0.)-q['fee']*(entry_turnover+exit_turnover))<1e-7 if 'stats'in q else True
 start,end=map(us,q['window']);ticks=np.arange(start+60000000,end+1,60000000,dtype=np.int64);n=len(ticks);assert len(marks)==n
 cash_imp=np.zeros(n);cash_side={side:np.zeros(n)for side in (1,-1)}
 for item in q['cash_events']:
  index=int(np.searchsorted(ticks,item['time_us'],side='right'))
  if index<n:cash_imp[index]+=item['delta'];cash_side[item['side']][index]+=item['delta']
 cash=500+np.cumsum(cash_imp);assert abs(cash[-1]-q['cash'])<1e-7
 qty=np.zeros(n);entry=np.zeros(n);sidevec=np.zeros(n);stops=np.zeros(n)
 updates=[x for x in q['events']if x['event']=='poll_moves_stop']
 from strategy import r
 for trade in rows(q):
  a=int(np.searchsorted(ticks,trade['opened_us'],side='right'));b=int(np.searchsorted(ticks,trade['closed_us']or end,side='right'));b=min(n,b)
  if a>=b:continue
  side=1 if trade['side']=='LONG'else-1
  qty[a:b]=trade['quantity'];entry[a:b]=trade['entry'];sidevec[a:b]=side;stops[a:b]=r.model.stop_price(q['asset'],trade['entry'],side,0)
  for f in trade.get('partial_fills',[]):
   k=int(np.searchsorted(ticks,f['time_us'],side='right'));qty[max(a,k):b]-=f['quantity']
  for update in updates:
   if trade['opened_us']<=update['time_us']<(trade['closed_us']or end):
    k=int(np.searchsorted(ticks,update['time_us'],side='right'));stops[max(a,k):b]=update['stop']
 assert np.isfinite(marks).all() and np.isfinite(cash).all() and (qty>=-1e-8).all()
 active=qty>1e-10;floating=np.asarray(marks)-cash;assert np.allclose(floating[~active],0,atol=1e-7)
 price=entry+np.divide(sidevec*floating,qty,out=np.zeros(n),where=active)
 assert (price[active]>0).all()
 direction_curves={side:500+np.cumsum(cash_side[side])+np.where(sidevec==side,floating,0)for side in (1,-1)}
 assert np.allclose(direction_curves[1]+direction_curves[-1]-500,marks,atol=1e-7)
 return dict(ticks=ticks,cash=cash,active=active,qty=qty,side=sidevec,floating=floating,directions=direction_curves,gross_notional=qty*price,reference_stop_risk=np.where(active,np.maximum(0,sidevec*(price-stops))*qty,0))

def metrics(trades,marks,initial,window,open_count=0):
 values=np.r_[initial,marks];peak=np.maximum.accumulate(values);dd=100*(1-values/peak);gross_profit=sum(max(0,t['net'])for t in trades);gross_loss=-sum(min(0,t['net'])for t in trades)
 streak=longest=0
 for t in sorted(trades,key=lambda x:x['closed_us']):
  streak=streak+1 if t['net']<0 else 0;longest=max(longest,streak)
 start,end=[datetime.fromisoformat(x)for x in window];month=start.replace(day=1,hour=0,minute=0,second=0,microsecond=0);monthly=[]
 while month<end:
  nxt=month.replace(year=month.year+1,month=1)if month.month==12 else month.replace(month=month.month+1)
  lo=max(start,month);hi=min(end,nxt);a=round((lo-start).total_seconds()/60);b=round((hi-start).total_seconds()/60)
  if b>a:
   previous=initial if a==0 else float(marks[a-1]);val=float(marks[b-1]);monthly.append(dict(month=month.strftime('%Y-%m'),return_pct=100*(val/previous-1),partial_month=lo!=month or hi!=nxt))
  month=nxt
 worst=min(monthly,key=lambda x:x['return_pct'])if monthly else dict(month=None,return_pct=None,partial_month=True)
 return dict(return_pct=100*(float(marks[-1])/initial-1),ending_equity=float(marks[-1]),max_drawdown_pct=float(dd.max()),worst_month=worst['month'],worst_month_return_pct=worst['return_pct'],worst_month_partial=worst['partial_month'],max_consecutive_losses=longest,closed=len(trades),open=open_count,wins=sum(t['net']>0 for t in trades),losses=sum(t['net']<0 for t in trades),win_rate_pct=100*sum(t['net']>0 for t in trades)/len(trades)if trades else None,profit_factor=gross_profit/gross_loss if gross_loss else None,profit_factor_no_losses=gross_loss==0,gross_winning_trade_net=gross_profit,gross_losing_trade_net=gross_loss,max_single_trade_loss=min([0.]+[t['net']for t in trades]),max_loss_per_1000_initial_notional=min([0.]+[t['net']/(t['entry']*t['quantity'])*1000 for t in trades]),monthly=monthly)

def diagnostic(q,conditions,signals,threshold):
 positions=rows(q);opens=np.array([x['opened_us']for x in positions],dtype=np.int64)
 order_events=[x for x in q['events']if x['event']=='order_sent'];order_times=np.array([x['time_us']for x in order_events],dtype=np.int64)
 fills={t['signal_close_ms']:t for t in positions};sent={(e['time_us']//1000)-10000:e for e in order_events};attempts={(e['scheduled_us']//1000)-10000:e for e in q['place_attempts']}
 cash_times=np.array([e['time_us']for e in q['cash_events']],dtype=np.int64)
 end=us(q['window'][1]);out={}
 for stamp,item in conditions.items():
  side=item['side'];clock=(stamp+10000)*1000;state=item['ER_regime'];matching=(state=='up'and side==1)or(state=='down'and side==-1)
  failed=[]
  if item['historical_minimum_bandwidth_pct']>threshold:failed.append('HISTORICAL_BANDWIDTH')
  if item['aligned_lines']<6:failed.append('SIX_LINES')
  if not item['close_outside_six']:failed.append('CLOSE_POSITION')
  if not item['MACD_direction_pass']:failed.append('MACD')
  if state=='transition':failed.append('ER_TRANSITION')
  elif state=='range':
   if item['current_bandwidth_pct']>.5:failed.append('RANGE_CURRENT_BANDWIDTH')
  elif not matching:failed.append('ER_DIRECTION')
  else:
   if not item['trend_confirmation_pass']:failed.append('TREND_CONFIRMATION')
   if item['extra_trend_pass']is not True:failed.append('TREND_LEVEL_VOLUME_RETEST')
  eligible=not failed;assert eligible==(signals.get(stamp)==side),(stamp,failed,signals.get(stamp))
  i=int(np.searchsorted(opens,clock,side='right'))-1;held=positions[i]if i>=0 and clock<(positions[i]['closed_us']or end)else None
  j=int(np.searchsorted(order_times,clock,side='left'))-1;pending=False
  if j>=0:
   order=order_events[j];key=order['time_us']//1000-10000;fill=fills.get(key);resolved=min(order['time_us']+3600*1000000,fill['opened_us']if fill else end)
   pending=clock<resolved
  held_record=held
  pending_record=order_events[j]if j>=0 and pending else None
  attempt=attempts.get(stamp)
  if attempt:held=bool(attempt['has_position']);pending=bool(attempt['has_order'])
  c=int(np.searchsorted(cash_times,clock,side='right'))-1;cash=q['cash_events'][c]['cash']if c>=0 else 500.
  if attempt:cash=attempt['cash']
  if not eligible:status='SIGNAL_REJECTED'
  elif stamp in fills:status='FILLED'
  elif stamp in sent:status='ORDER_PENDING_AT_END'if q['state_at_end']['pending_order']and q['state_at_end']['pending_order']['time']==stamp+10000 else'ORDER_EXPIRED_UNFILLED'
  elif attempt and not attempt['accepted']:status='FUNDS_OR_MIN_NOTIONAL'
  elif held:status='BLOCKED_POSITION'
  elif pending:status='BLOCKED_PENDING_ORDER'
  else:status='UNEXPLAINED_NO_ORDER'
  out[stamp]=dict(item,threshold_pct=threshold,eligible=eligible,failed_conditions=';'.join(failed),execution_status=status,scheduled_submission_us=clock,observed_submission_check_us=attempt['observed_check_us']if attempt else'NOT_EVALUATED',occupancy_source='ACTUAL_PLACE_CHECK'if attempt else'RECONSTRUCTED_EVENTS_AT_SCHEDULED_CLOCK',has_position=bool(held),has_pending_order=bool(pending),occupying_signal_close_ms=held_record['signal_close_ms']if held and held_record else'NOT_EVALUATED',occupying_trade_opened_us=held_record['opened_us']if held and held_record else'NOT_EVALUATED',occupying_side=held_record['side']if held and held_record else'NOT_EVALUATED',pending_signal_close_ms=pending_record['time_us']//1000-10000 if pending and pending_record else'NOT_EVALUATED',realized_balance_at_check=cash)
 return out

def trade_key(t):return(t['side'],int(t['signal_close_ms']))
def compare(base,variant,decisions):
 a={trade_key(t):t for t in rows(base)};b={trade_key(t):t for t in rows(variant)};result=[]
 for key in sorted(a.keys()|b.keys(),key=lambda k:k[1]):
  old,new=a.get(key),b.get(key)
  if old and new:
   unchanged=all(old.get(f)==new.get(f)for f in ('opened_us','closed_us','quantity','entry','exit','rung','status','signal_ms','origin','reason'))
   partial_path=lambda t:[(x['time_us'],x['quantity'],x['execution_price'])for x in t.get('partial_fills',[])]
   unchanged=unchanged and partial_path(old)==partial_path(new)
   category='RETAINED'if unchanged else'CHANGED'
  else:category='ADDED'if new else'DISAPPEARED'
  stamp=key[1];norm=lambda t:t['contribution']/(t['entry']*t['quantity'])*1000 if t else 0.
  row=dict(side=key[0],signal_close_ms=stamp,old_origin=old.get('origin')if old else None,new_origin=new.get('origin')if new else None,old_submitted_us=old.get('submitted_us',old.get('signal_ms',0)*1000)if old else None,new_submitted_us=new.get('submitted_us',new.get('signal_ms',0)*1000)if new else None,old_exit_reason=old.get('reason')if old else None,new_exit_reason=new.get('reason')if new else None,signal_beijing=time_s(stamp*1000),category=category,old_status=old['status']if old else None,new_status=new['status']if new else None,old_net=old.get('net')if old else None,new_net=new.get('net')if new else None,old_contribution=old['contribution']if old else 0.,new_contribution=new['contribution']if new else 0.,actual_USDT_delta=(new['contribution']if new else 0.)-(old['contribution']if old else 0.),normalized_1000_delta=norm(new)-norm(old),old_normalized_1000=norm(old),new_normalized_1000=norm(new),old_opened_us=old['opened_us']if old else None,new_opened_us=new['opened_us']if new else None,old_closed_us=old['closed_us']if old else None,new_closed_us=new['closed_us']if new else None,old_quantity=old['quantity']if old else None,new_quantity=new['quantity']if new else None,old_entry=old['entry']if old else None,new_entry=new['entry']if new else None,old_exit=old.get('exit')if old else None,new_exit=new.get('exit')if new else None,old_rung=old.get('rung')if old else None,new_rung=new.get('rung')if new else None,old_opening_cash=old.get('opening_sleeve_cash_usdt')if old else None,new_opening_cash=new.get('opening_sleeve_cash_usdt')if new else None,old_partial_fills=json.dumps(old.get('partial_fills',[]),ensure_ascii=False)if old else None,new_partial_fills=json.dumps(new.get('partial_fills',[]),ensure_ascii=False)if new else None,variant_reason=decisions.get(stamp,{}).get('execution_status','NOT_EVALUATED'),variant_failed_conditions=decisions.get(stamp,{}).get('failed_conditions','NOT_EVALUATED'),variant_occupying_signal_close_ms=decisions.get(stamp,{}).get('occupying_signal_close_ms','NOT_EVALUATED'),variant_pending_signal_close_ms=decisions.get(stamp,{}).get('pending_signal_close_ms','NOT_EVALUATED'))
  result.append(row)
 assert abs(sum(x['contribution']for x in a.values())-(base['ending_equity']-500))<1e-7
 assert abs(sum(x['contribution']for x in b.values())-(variant['ending_equity']-500))<1e-7
 delta=variant['ending_equity']-base['ending_equity'];decomposition=sum(x['actual_USDT_delta']for x in result);assert abs(delta-decomposition)<1e-7,(delta,decomposition)
 return result
