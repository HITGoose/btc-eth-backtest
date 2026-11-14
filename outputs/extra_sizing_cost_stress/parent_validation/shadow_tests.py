from pathlib import Path
import copy,json
import strategy as z
import priority_engine as pe
OUT=z.OUT;f=z.module('priority_shadow_test_fixtures',OUT/'validation32/tests.py');checks=[]
def at(b,t):b.audit_timestamp=t;b.observing_event=True
for side in(1,-1):
 for fee in(0.,.0005):
  for partial in(False,True):
   leg=f.leg_for(side);b=pe.book('ETH',fee,leg,{},True);z.r.model.FEE=fee
   at(b,f.BASE+10);b.place((f.BASE+10)*1000,100.,side,nearest_tick=True);entry=b.order.price
   at(b,f.BASE+10.123);b.visit(entry,round((f.BASE+10.123)*1000),True,advance_ladder=False)
   if partial:
    j=(f.BASE+1800-leg.first//1000)//900-1;f.weak(leg,j-1,side);f.weak(leg,j,side);at(b,f.BASE+1800);z.v.check(b,f.BASE+1800)
    at(b,f.BASE+1800.123);b.visit(entry+side*.1,round((f.BASE+1800.123)*1000),True,advance_ladder=False)
   b.core[(f.BASE+2700)*1000]=side;at(b,f.BASE+2710);b.on_core((f.BASE+2700)*1000,100.,side)
   b.current_raw_id=42;at(b,f.BASE+2710.123);b.visit(entry+side*.2,round((f.BASE+2710.123)*1000),True,advance_ladder=False)
   original=copy.deepcopy(b.journal);cash=b.cash;pending=copy.deepcopy(b.order);snap=b.shadow_snapshots[-1]
   shadow=pe.book('ETH',fee,leg,{},False);shadow.position=copy.deepcopy(snap['position']);shadow.cash=snap['cash'];shadow.tranches=list(snap['tranches']);shadow.order_info=dict(snap['order_info'])
   price=shadow.position.stop-side*2;remaining=shadow.position.order.qty
   at(shadow,f.BASE+2720.456);shadow.visit(price,round((f.BASE+2720.456)*1000),True,advance_ladder=False)
   assert shadow.position is None and shadow.journal[-1]['reason']=='hard_stop'
   a=b.journal[-1];s=shadow.journal[-1];expected=(side-fee)*(a['exit']-s['exit'])*remaining
   assert abs(a['net']-s['net']-expected)<1e-8
   assert b.cash==cash and b.journal==original and b.order==pending
   assert s['signal_close_ms']==f.BASE*1000
   checks.append(dict(side=side,fee=fee,partial_before_replacement=partial,continuation_delta=expected,no_live_mutation=True))
for side in(1,-1):
 for fee in(0.,.0005):
  leg=f.leg_for(side);b=pe.book('ETH',fee,leg,{},True);z.r.model.FEE=fee
  at(b,f.BASE+10);b.place((f.BASE+10)*1000,100.,side,nearest_tick=True);entry=b.order.price
  at(b,f.BASE+10.123);b.visit(entry,round((f.BASE+10.123)*1000),True,advance_ladder=False)
  j=(f.BASE+2700-leg.first//1000)//900-1;f.weak(leg,j-1,side);f.weak(leg,j,side);at(b,f.BASE+2700);z.v.check(b,f.BASE+2700);assert b.position.partial_queue
  b.core[(f.BASE+2700)*1000]=side;at(b,f.BASE+2710);b.on_core((f.BASE+2700)*1000,100.,side)
  b.current_raw_id=42;price=entry+side*.2;at(b,f.BASE+2710.123);b.visit(price,round((f.BASE+2710.123)*1000),True,advance_ladder=False)
  assert not b.journal[-1]['partial_fills'];snap=b.shadow_snapshots[-1]
  shadow=pe.book('ETH',fee,leg,{},False);shadow.position=copy.deepcopy(snap['position']);shadow.cash=snap['cash'];shadow.tranches=list(snap['tranches']);shadow.order_info=dict(snap['order_info'])
  at(shadow,f.BASE+2710.123);shadow.visit(price,round((f.BASE+2710.123)*1000),True,advance_ladder=False)
  assert len(shadow.position.partial_fills)==1 and shadow.position.partial_fills[0]['trigger_print']==price
  assert shadow.position.partial_fills[0]['time_us']==snap['exit_us']
  at(shadow,f.BASE+2720);shadow.visit(shadow.position.stop-side*2,round((f.BASE+2720)*1000),True,advance_ladder=False)
  assert abs(shadow.cash-500-shadow.journal[-1]['net'])<1e-8
  assert not b.journal[-1]['partial_fills']
  checks.append(dict(side=side,fee=fee,queued_partial_at_forced_print_processed_by_shadow_only=True,no_live_mutation=True))
z.dump(OUT/'shadow_tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks),'independent shadow cash/quantity cases')
