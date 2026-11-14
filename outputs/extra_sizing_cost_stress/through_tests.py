from types import SimpleNamespace
import shared as s
f=s.z.module('through_exact_fixture',s.b.PARENT/'validation32/tests.py')
import through_engine as T
import cost_engine as C
np=s.np;checks=[]
def test(n,fn):fn();checks.append(dict(name=n,passed=True));print('PASS',n)
def make(*,side=1,core=False):
 T.configure_feed('2020','ETH');x=T.book('ETH',.0005,.0002,f.leg_for(side),{f.BASE*1000:side}if core else{},True,.5,'F_THROUGH');s.activate(x)
 x.current_raw_id=10;x.audit_timestamp=f.BASE+10.5;x.observing_event=True
 if core:x.submitting_signal=f.BASE*1000
 x.place((f.BASE+10)*1000,100.,side,nearest_tick=True)
 return x
for side in(1,-1):
 def delayed(side=side):
  x=make(side=side);price=x.order.price-side*.01
  assert x.order.submitted_effective_us==(f.BASE+10)*1000000
  x.visit(price,round((f.BASE+10.5)*1000),True,advance_ladder=False)
  assert x.position and x.position.opened_us==round((f.BASE+10.5)*1000000)
 test('first eligible raw print after original+10 clock, no extra activation-print delay '+str(side),delayed)
def exact_same_event():
 x=make();x.current_raw_id=10;x.audit_timestamp=f.BASE+10;x.order.submitted_raw_id=10;x.visit(x.order.price-.01,(f.BASE+10)*1000,True,advance_ladder=False);assert x.order
 x.current_raw_id=11;x.visit(x.order.price-.01,(f.BASE+10)*1000,True,advance_ladder=False);assert x.position
test('same timestamp new event allowed, submission/exit event itself rejected',exact_same_event)
def threshold():
 x=make();x.audit_timestamp=f.BASE+11
 for d in(0.,.005):x.visit(x.order.price-d,(f.BASE+11)*1000,True,advance_ladder=False);assert x.order
 price=x.order.price;x.visit(price-.01,(f.BASE+11)*1000,True,advance_ladder=False);assert x.position.order.price==price
test('strict through threshold preserves original limit execution price',threshold)
def replacement():
 x=make();x.audit_timestamp=f.BASE+11;x.current_raw_id=20;x.visit(x.order.price-.01,(f.BASE+11)*1000,True,advance_ladder=False)
 stamp=(f.BASE+900)*1000;x.core[stamp]=-1;x.audit_timestamp=f.BASE+910;x.on_core(stamp,100,-1)
 x.audit_timestamp=f.BASE+911;x.current_raw_id=30;x.visit(100.5,(f.BASE+911)*1000,True,advance_ladder=False)
 assert x.position is None and x.order and x.order.origin=='CORE';exit_price=x.order.price+.01
 x.audit_timestamp=f.BASE+911;x.current_raw_id=31;x.visit(exit_price,(f.BASE+911)*1000,True,advance_ladder=False)
 assert x.position and x.position.order.side==-1
 T.cash_check(x)
test('CORE exit first, newly submitted limit uses a distinct real event at same timestamp',replacement)
def funded_mode():
 T.configure_feed('NOV','ETH');assert T.FULL and T.COST=='C2'and s.b.e.x.check_trend is T.F.funding_check
 T.configure_feed('2020','ETH');assert not T.FULL and T.COST=='C1'and s.b.e.x.check_trend is T.F.original_check
test('funded C2 versus explicit missing-price C1 fallback never silently zero-fills funding',funded_mode)
s.dump(s.OUT/'through_tests.json',dict(passed=True,total=len(checks),checks=checks));print('ALL',len(checks),'PASS')
