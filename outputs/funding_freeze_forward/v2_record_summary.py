"""Read-only actual I25 EXTRA request/no-request cases; no invented confirmation."""
import json
import online as n
O=n.O;rows=[]
for p in(O/'historical/runs').glob('*/ETH/funded/results/STRICT/*I25*_result.json'):
 q=json.loads(p.read_text());events=q['events']
 for t in q['trades']:
  if t.get('origin')!='EXTRA':continue
  req=[e for e in events if e['event']=='adaptive_v2_request'and t['opened_us']<e['time_us']<=t['closed_us']];partial=t.get('partial_fills',[])
  for e in req:assert abs(e['budget']-e['realized_balance']*.03)<1e-8
  rows.append(dict(period=q['period'],key=q['key'],signal_close_ms=t['signal_close_ms'],side=t['side'],initial_quantity=t['quantity'],entry=t['entry'],exit=t['exit'],net=t['net'],V2_requests=len(req),partial_exits=len(partial),actual_reduced_initial_fraction=sum(f['quantity']for f in partial)/t['quantity'],budget_rate=.03,not_scaled_for_I25=True,no_request_reason='NO_RECORDED_REQUEST_FULL_GATE_NOT_RECONSTRUCTED'if not req else'ACTUAL_REQUEST',missing_condition_status='NOT_EVALUATED'if not req else'OBSERVED_EVENT'))
if rows:n.s.z.csv_dump(O/'I25_EXTRA_V2_cases.csv',rows)
(O/'I25_EXTRA_V2_summary.json').write_text(json.dumps(dict(rows=len(rows),no_request=sum(r['V2_requests']==0 for r in rows),request=sum(r['V2_requests']>0 for r in rows),reduction=sum(r['partial_exits']>0 for r in rows),modes_not_independent_samples=True,no_formula_change=True),indent=2));print('I25_CASES',len(rows))
