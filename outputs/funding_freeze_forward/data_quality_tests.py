"""Actual zero-NA message rejection is a safety pass, NOT a successful live sample."""
from pathlib import Path
import json,gzip,hashlib,copy
import online as n
O=n.O;p=next((O/'forward').glob('ws_closed_fix*/events.jsonl.gz'));sample=None
with gzip.open(p,'rt')as f:
 for line in f:
  r=json.loads(line);q=r['event']
  if q['type']=='TRADES'and q['data'][0]['price']=='0':sample=dict(tape=str(p),sequence=r['sequence'],chain_SHA256=r['chain_SHA256'],event=q);break
assert sample is not None;q=sample['event'];raw=json.loads(q['raw_UTF8'])['data'];assert raw['p']=='0'and raw['q']=='0'and raw['X']=='NA';assert hashlib.sha256(q['raw_UTF8'].encode()).hexdigest()==q['SHA256']
(O/'observed_zero_NA_event.json').write_text(json.dumps(sample,indent=2))
manifest=json.loads((O/'FREEZE_WS_V3.json').read_text());sg=n.Signals(manifest['T0_ms'],O/'quality_test_data')
for row in json.loads((O/'preflight_closed/warm_responses.json').read_text()):sg.add(row['asset'],row['data'],row['received_us'])
legs=sg.calculate();checks=[]
for side in [1,-1]:
 e=n.Engine(manifest,legs);x=e.books[('F_TOUCH','B','BTC')];t=manifest['T0_ms']*1000+1000000;x.audit_timestamp=t/1e6;x.observed_clock_us=t;x.submitting_signal=manifest['T0_ms'];x.core={manifest['T0_ms']:side};n.s.activate(x);x.place(t/1000,10000,side,nearest_tick=True);x.submitting_signal=None;x.audit_timestamp=(t+1000000)/1e6;x.visit(x.order.price,(t+1000000)//1000,True,advance_ladder=False)
 before=x.cash;pos=x.position;stop=pos.stop
 try:e.consume(q);raise RuntimeError('invalid price was accepted')
 except AssertionError:pass
 assert x.cash==before and x.position is pos and pos.stop==stop and not x.journal;e.audit();checks.append(dict(name='zero-NA rejected before any fake stop/profit; side'+str(side),passed=True))
(O/'data_quality_tests.json').write_text(json.dumps(dict(passed=True,total=len(checks),checks=checks,production_financial_block_remains=True,zero_NA_semantics_unverified=True,not_counted_as_forward_returns=True),indent=2));print('ZERO_NA_SAFETY_PASS',len(checks),'forward remains UNVERIFIED')
