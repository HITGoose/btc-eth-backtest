"""Independent cash/funding/quantity/timeline validation over complete account paths."""
from pathlib import Path
from decimal import Decimal
import json,hashlib
import shared as s
np=s.np;O=s.OUT;checks=[]

def audit_sources():
 rows=[]
 for p in sorted((O/'funding_data').glob('*/*/result.json')):
  d=json.loads(p.read_text());records=[]
  for src in d['sources']:
   raw=(O/src['stored']).read_bytes();assert hashlib.sha256(raw).hexdigest()==src['response_SHA256'];records+=json.loads(raw)
  rawmap={int(x['fundingTime']):x for x in records};assert len(rawmap)==len(records)
  a,b=d['window_ms'];wanted=[v for v in records if a<=int(v['fundingTime'])<b];assert wanted==d['records']
  events={e['time_ms']:e for e in d['events']}
  for x in wanted:
   if x in d['invalid_records']:continue
   e=events[int(x['fundingTime'])];assert Decimal(str(e['mark_price']))==Decimal(x['markPrice'])and Decimal(str(e['rate']))==Decimal(x['fundingRate'])
   assert e['official_record']==x and e['complete']and e['source']=='BINANCE_USDT_PERPETUAL_OFFICIAL'
  assert len(events)+len(d['invalid_records'])==len(wanted)
  rows.append(dict(period=d['period'],asset=d['asset'],status=d['status'],records=len(wanted),exact_API_responses=True,exact_event_fields=True))
 return rows

def actual_rows(q):
 rows=s.z.h.rows(q)
 for x in rows:
  if x['status']=='OPEN':x['signal_close_ms']=q['state_at_end']['position']['order']['signal_close_ms']
 return rows

def check(q,eq):
 trades=actual_rows(q);window=list(map(s.z.h.us,q['window']));assert len(eq)==(window[1]-window[0])//60000000
 assert abs(float(eq[-1])-q['ending_equity'])<1e-7
 assert abs(q['cash']-500-sum(e['delta']for e in q['cash_events']))<1e-7
 assert abs(q['ending_equity']-500-sum(t['net']for t in q['trades'])-q['open_contribution'])<1e-7
 turnover=sum(t['entry']*t['quantity']+sum(x['execution_price']*x['quantity']for x in t.get('partial_fills',[]))+(t['exit']*t['final_exit_quantity']if t['status']=='CLOSED'else 0)for t in trades)
 assert abs(q['stats'].get('fees',0)-turnover*q['fee'])<1e-7
 cfg=q['configuration'];slip=cfg['slip'];slipcost=0.
 if cfg['fill']=='F_THROUGH':
  tick=1./s.r.model.SCALES[q['asset']]
  for e in q['events']:
   if e['event']=='limit_touch_proxy_fill':
    assert e['side']*(e['price']-e['entry'])<=-tick+1e-8
    assert e['submitted_us']<=e['time_us']<e['submitted_us']+3600000000
 for a in q['sizing_audit']:
  if a.get('actual_notional')is None:continue # unchanged BTC reference metadata, separately source-proved
  expected_scale=s.GROUPS[cfg['group']][1]if q['asset']=='ETH'and a['origin']=='EXTRA'else 1.
  assert a['extra_ratio']==expected_scale
  if a['accepted']:
   assert a['actual_notional']<=max(0.,a['realized_balance'])*3*expected_scale+1e-7
   step=.0001 if q['asset']=='BTC'else s.r.model.RULES[q['asset']][0]
   assert abs(a['actual_quantity']/step-round(a['actual_quantity']/step))<1e-7
   assert a['actual_notional']>=s.r.model.RULES[q['asset']][1]

 for t in trades:
  side=1 if t['side']=='LONG'else-1
  partials=t.get('partial_fills',[]);partial_gross=sum(side*(f['execution_price']-t['entry'])*f['quantity']for f in partials);partial_fees=sum(f['execution_price']*f['quantity']*q['fee']for f in partials);entry_fee=t['entry']*t['quantity']*q['fee']
  assert abs(sum(f['quantity']for f in partials)+t['final_exit_quantity']-t['quantity'])<1e-8
  if t['status']=='CLOSED':
   expected=partial_gross-partial_fees+side*(t['exit']-t['entry'])*t['final_exit_quantity']-t['exit']*t['final_exit_quantity']*q['fee']-entry_fee+t.get('funding_net_USDT',0.)
   assert abs(expected-t['net'])<1e-7,('independent closed net',q['key'],t['signal_close_ms'],expected,t['net'])
  else:
   fund=q.get('open_partial_state',{}).get('funding_pnl')or 0.
   expected=partial_gross-partial_fees-entry_fee+side*(q['actual_raw_last_mark']-t['entry'])*t['final_exit_quantity']+fund
   assert abs(expected-q['open_contribution'])<1e-7,('independent open contribution',q['key'])

  if t['status']=='CLOSED':slipcost+=t['exit']/(1-side*slip)*t['final_exit_quantity']*slip
  slipcost+=sum(f['trigger_print']*f['quantity']*slip for f in t.get('partial_fills',[]))
  assert sum(f['quantity']for f in t.get('partial_fills',[]))<=t['quantity']*.25+1e-8
 assert abs(slipcost-q['slippage_cost_USDT'])<1e-7
 funding_expected=0.;funding_events=q.get('funding_events',[])
 if q['funding']=='INCLUDED_OFFICIAL':
  feed=json.loads((O/'funding_data'/q['period']/q['asset']/'result.json').read_text());assert feed['status']=='COMPLETE';expected=[]
  for trade in trades:
   delta=0.;event_count_before=len(expected);side=1 if trade['side']=='LONG'else-1
   for e in feed['events']:
    stamp=e['time_ms']*1000
    if trade['opened_us']<stamp<=(trade.get('closed_us')or window[1]-1):
     qty=trade['quantity']-sum(f['quantity']for f in trade.get('partial_fills',[])if f['time_us']<stamp)
     val=-side*qty*e['mark_price']*e['rate'];delta+=val;expected.append(dict(time_ms=e['time_ms'],quantity=qty,side=side,delta=val))
   if trade['status']=='CLOSED':assert abs(delta-trade['funding_net_USDT'])<1e-7
   else:
    stored=q['open_partial_state']['funding_pnl']
    if stored is None:
     assert len(expected)==event_count_before and delta==0.,'Uninitialized funding field is valid only with no held settlement events'
    else:assert abs(delta-stored)<1e-7
   funding_expected+=delta
  expected.sort(key=lambda x:x['time_ms']);assert len(expected)==len(funding_events)
  for e,f in zip(expected,funding_events):
   assert e['time_ms']==f['time_ms']and e['side']==f['side']and abs(e['quantity']-f['quantity'])<1e-8 and abs(e['delta']-f['delta'])<1e-7
  assert abs(funding_expected-q['funding_total_USDT'])<1e-7
 # Causal V2 budget: header settlement precedes check, same-time raw cash does not.
 for e in q['events']:
  if e['event']!='adaptive_v2_request':continue
  when=e['time_us'];known=500+sum(c['delta']for c in q['cash_events']if c['time_us']<when)+sum(f['delta']for f in funding_events if f['time_ms']*1000==when)
  assert abs(known-e['realized_balance'])<1e-7,(q['key'],'V2 cash timing',known,e['realized_balance'])
  assert abs(e['budget']-max(0.,known)*.03)<1e-7
  assert e['requested_quantity']<=.25*e['initial_quantity']+1e-8
 return dict(period=q['period'],asset=q['asset'],key=q['key'],scenario=q['scenario'],cash=q['cash'],ending_equity=q['ending_equity'],funding_expected=funding_expected,funding_events=len(funding_events),fees=q['stats'].get('fees',0),slippage=slipcost,all_checks_passed=True)

def main():
 sources=audit_sources()
 for root in [O/'runs',O/'sizing_only/runs',O/'funded/runs',O/'through_exact_clock/runs']:
  for status in root.glob('*/*/*/status.json'):
   if not json.loads(status.read_text()).get('completed'):continue
   for p in status.parent.glob('results/*/*_result.json'):
    q=json.loads(p.read_text());eq=np.load(p.with_name(p.name.replace('_result.json','_equity.npz')))['marks'];row=check(q,eq);row['legacy_through_not_primary']=q['configuration']['fill']=='F_THROUGH'and root!=O/'through_exact_clock/runs';checks.append(row)
 s.dump(O/'financial_audit.json',dict(passed=True,source_checks=sources,accounts=len(checks),checks=checks));print('INDEPENDENT_AUDIT',len(checks),'PASS')
if __name__=='__main__':main()
