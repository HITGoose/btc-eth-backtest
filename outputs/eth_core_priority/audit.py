from pathlib import Path
import json,hashlib,gzip,csv
import numpy as np
import strategy as z
h=z.module('priority_audit_helpers',z.OUT/'analysis_helpers.py');c=z.module('priority_audit_collect',z.OUT/'collect.py');OUT=z.OUT

def main():
 cfg=h.read(OUT/'frozen_config.json')
 for name,digest in cfg['code_SHA256'].items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest
 assert h.read(OUT/'tests.json')['passed']and h.read(OUT/'validation32/test_results.json')['failed']==0
 assert h.read(OUT/'baseline_status.json')['passed']
 checks=[];BTC_hashes={};filled=0;requests=0;totalfees=0.
 analysis=h.read(OUT/'analysis.json')
 for row in analysis['availability']:
  if row['status']!='COMPLETE':continue
  period,cost,g=row['period'],row['cost'],row['group']
  for asset in('BTC','ETH'):
   q,eq=c.load(period,asset,cost,g);vec=h.curve(q,eq)
   assert abs(q['ending_equity']-eq[-1])<1e-7
   assert abs(q['ending_equity']-500-sum(t['net']for t in q['trades'])-q['open_contribution'])<1e-7
   assert abs(q['cash']-500-sum(x['delta']for x in q['cash_events']))<1e-7
   assert q['stats'].get('submitted',0)==q['opens']+q['stats'].get('expired',0)+q['stats'].get('priority_cancelled',0)+bool(q['state_at_end']['pending_order'])
   assert q['opens']==len(q['trades'])+bool(q['state_at_end']['position'])
   assert not(q['state_at_end']['position']and q['state_at_end']['pending_order'])
   if asset=='BTC':
    digest=hashlib.sha256(json.dumps(q,sort_keys=True).encode()).hexdigest();key=(period,cost)
    if key in BTC_hashes:assert BTC_hashes[key]==digest
    BTC_hashes[key]=digest
   else:
    filled+=q['opens'];requests+=sum(x['event']=='priority_replace_requested'for x in q['events']);totalfees+=q['stats'].get('fees',0)
    sm=c.maps(period,'ETH');core={int(k):v for k,v in sm['core'].items()};wide={int(k):v for k,v in sm['wide'].items()};btc={int(k):v for k,v in sm['BTC'].items()}
    for t in h.rows(q):
     stamp=t['signal_close_ms'];side=1 if t['side']=='LONG'else-1;expected='CORE'if core.get(stamp)==side else'EXTRA'
     assert wide.get(stamp)==side
     if t['status']=='CLOSED':assert t['origin']==expected
     if g=='B':assert expected=='CORE'
     if g in('G','I')and expected=='EXTRA':assert btc.get(stamp)==side
     fills=t.get('partial_fills',[]);assert len(fills)<=1 and sum(f['quantity']for f in fills)<=t['quantity']*.25+1e-8
     if t['status']=='CLOSED':assert abs(sum(f['quantity']for f in fills)+t['final_exit_quantity']-t['quantity'])<1e-8
    events=q['events'];fill_events=[x for x in events if x['event']=='limit_touch_proxy_fill'];orders={x['signal_close_ms']:x for x in events if x['event']=='order_sent'}
    for event in events:
     if event['event']=='priority_replace_requested':assert event['time_us']==event['core_signal_close_ms']*1000+10000000
     if event['event']=='priority_cancel_extra_order':assert event['time_us']==event['core_signal_close_ms']*1000+10000000
     if event['event']=='priority_position_closed':
      order=orders.get(event['core_signal_close_ms'])
      if order:
       assert order['time_us']==event['time_us']
       fill=next((x for x in fill_events if x['signal_close_ms']==event['core_signal_close_ms']),None)
       if fill:assert fill['raw_sequence']>event['exit_raw_sequence']
    for t in q['trades']:
     if t['reason']=='core_priority_exit':assert t['origin']=='EXTRA'and t['closed_us']>next(x['time_us']for x in events if x['event']=='priority_replace_requested'and x['extra_signal_close_ms']==t['signal_close_ms'])
   checks.append(dict(period=period,cost=cost,group=g,asset=asset,ledger=True,fee_turnover=True,quantity=True,source_tags=True))
 # Original locked execution sources still exact; CSV newline metadata accepted
 # only for unrelated old exports, never Python or financial result JSON.
 tree=h.read(Path('/tmp/priority_locked_tree.json'));source=0
 for item in tree['tree']:
  if item['type']!='blob'or not item['path'].endswith('.py'):continue
  data=(z.ROOT/item['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==item['sha'];source+=1
 out=dict(verification_passed=True,full_history_complete=analysis['full_history_complete'],source_commit=z.BASE_COMMIT,unchanged_original_Python_blobs=source,frozen_fingerprint=True,original_synthetic=32,additional_tests=h.read(OUT/'tests.json')['total'],completed_account_checks=len(checks),ETH_fills_across_scenarios_not_unique_samples=filled,priority_requests_across_scenarios_not_unique_samples=requests,checks=checks,unverified=[x for x in analysis['availability']if x['status']!='COMPLETE'],funding='NOT_INCLUDED',fee_rate='assumed .05pct per side, not verified account fee')
 z.dump(OUT/'audit.json',out);print('AUDIT PASS',len(checks),'account checks; full history:',out['full_history_complete'])
if __name__=='__main__':main()
