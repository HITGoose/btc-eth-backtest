"""Read-only primary ledger event exports; scenario rows are not independent samples."""
import json
import shared as s
O=s.OUT

def main():
 priority=[];v2=[];sizing=[];funding=[]
 for root in [O/'runs',O/'sizing_only/runs',O/'funded/runs',O/'through_exact_clock/runs']:
  for status in root.glob('*/*/*/status.json'):
   if not json.loads(status.read_text()).get('completed'):continue
   for p in status.parent.glob('results/*/*_result.json'):
    q=json.loads(p.read_text())
    if q['configuration']['fill']=='F_THROUGH'and root!=O/'through_exact_clock/runs':continue
    m=dict(period=q['period'],asset=q['asset'],scenario=q['scenario'],key=q['key'],source_ledger=str(p.relative_to(s.ROOT)))
    for i,e in enumerate(q['events']):
     r=dict(m,event_index=i,event=e['event'],time_us=e.get('time_us'),raw_event_json=json.dumps(e,sort_keys=True))
     if e['event'].startswith('priority_'):priority.append(r)
     if e['event'].startswith('adaptive_v2'):v2.append(r)
    for i,e in enumerate(q['sizing_audit']):sizing.append(dict(m,attempt_index=i,**e))
    for i,e in enumerate(q.get('funding_events',[])):funding.append(dict(m,settlement_index=i,**e))
 for name,rows in [('priority_events.csv.gz',priority),('V2_events.csv.gz',v2),('sizing_attempts.csv.gz',sizing),('funding_cash_events.csv.gz',funding)]:
  if rows:s.z.csv_dump(O/name,rows)
 s.dump(O/'event_export_summary.json',dict(priority=len(priority),V2=len(v2),sizing=len(sizing),funding=len(funding),legacy_prototype_excluded=True,duplicate_scenarios_not_independent_samples=True))
 print('EVENT_EXPORTS',len(priority),len(v2),len(sizing),len(funding))
if __name__=='__main__':main()
