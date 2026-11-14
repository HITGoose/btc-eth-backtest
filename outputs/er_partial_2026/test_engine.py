"""Synthetic accounting/gap tests, not historical validation."""
import json
from pathlib import Path
import run as e

checks=[]
for asset in ('BTC','ETH'):
 for side in (1,-1):
  b=e.new_book(asset,True);b.audit_timestamp=10.
  b.place(10000,100.,side,nearest_tick=True)
  entry=b.order.price;b.visit(entry,10000,True,advance_ladder=False)
  qty=b.position.order.qty
  b.audit_timestamp=12.;b.update_ladder(entry*(1+side*.035))
  assert b.position.partial_queue==[1,2] and b.stats['partial_exits']==0
  b.audit_timestamp=12.25;b.visit(entry*(1+side*.034),12250,True,advance_ladder=False)
  assert b.stats['partial_exits']==2 and not b.journal
  assert b.position.order.qty>0 and b.position.order.qty<qty
  b.audit_timestamp=13.;stop=b.position.stop
  b.visit(stop,13000,True,advance_ladder=False)
  assert b.position is None and len(b.journal)==1
  row=b.journal[0]
  assert abs(sum(v['quantity'] for v in row['partial_fills'])+row['final_exit_quantity']-qty)<1e-9
  assert abs(b.cash-500-row['net'])<1e-8
  checks.append(dict(asset=asset,side=side,passed=True,test='two tranches, lot conservation, one trade journal, PnL counted once'))
  # A gap beyond the protective stop takes priority over the requested partial.
  b=e.new_book(asset,True);b.audit_timestamp=10.;b.place(10000,100.,side,nearest_tick=True)
  entry=b.order.price;b.visit(entry,10000,True,advance_ladder=False)
  b.audit_timestamp=12.;b.update_ladder(entry*(1+side*.021))
  gap=entry*(1-side*.04);b.audit_timestamp=13.;b.visit(gap,13000,True,advance_ladder=False)
  assert b.position is None and b.stats['partial_exits']==0
  assert abs(b.journal[0]['exit']-gap*(1-side*e.r.model.SLIP))<1e-10
  checks.append(dict(asset=asset,side=side,passed=True,test='gap exits at actual print plus slip; stop priority'))
Path(__file__).with_name('synthetic_tests.json').write_text(json.dumps(dict(historical_validation=False,checks=checks),indent=2))
print('PASS',len(checks),'synthetic accounting/gap cases')
