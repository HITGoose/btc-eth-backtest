from pathlib import Path
from types import SimpleNamespace
import copy,json,sys
import shared as s
import cost_engine as E
b=s.b;r=s.r;np=s.np;checks=[]
f=s.z.module('cost_fixtures',b.PARENT/'validation32/tests.py')
def test(name,fn):fn();checks.append(dict(name=name,passed=True));print('PASS',name)
def make(asset='ETH',origin='EXTRA',ratio=.5,fee=.0005,slip=.0002,side=1,fill='F_TOUCH',cash=500.):
 core={f.BASE*1000:side}if origin=='CORE'else{}
 x=E.book(asset,fee,slip,f.leg_for(side),core,True,ratio,fill);x.cash=cash;s.activate(x);x.audit_timestamp=f.BASE+10;x.observing_event=True;x.place((f.BASE+10)*1000,100,side,nearest_tick=True);return x
def opened(**kw):
 x=make(**kw);x.audit_timestamp=f.BASE+11;x.visit(x.order.price,round(x.audit_timestamp*1000),True,advance_ladder=False);return x
for asset in ('BTC','ETH'):
 for origin in ('CORE','EXTRA'):
  def sizing(asset=asset,origin=origin):
   full=make(asset,origin,1);half=make(asset,origin,.5);quarter=make(asset,origin,.25)
   expected=.5 if asset=='ETH'and origin=='EXTRA'else 1
   step=full.sizing.btc_step if asset=='BTC'else r.model.RULES['ETH'][0]
   assert abs(half.order.qty-(int((full.sizing.leverage*500*expected/full.order.price+1e-12)/step)*step))<1e-8
   if expected==1:assert full.order.qty==half.order.qty==quarter.order.qty
  test(asset+' '+origin+' correct initial scale',sizing)
def minimum():
 x=make(ratio=.25,cash=1);assert x.order is None and x.sizing_audit[-1]['reason']=='MIN_NOTIONAL_OR_FUNDS'and x.stats['rejected']==1
 x=make(ratio=.25,cash=10.37);assert x.order.qty*x.order.price<=10.37*3*.25+1e-8
 assert abs(x.order.qty/.01-round(x.order.qty/.01))<1e-8
test('floor lots and never round minimum upward',minimum)
for side in (1,-1):
 def through(side=side):
  x=make(fill='F_THROUGH',side=side);limit=x.order.price;tick=1/r.model.SCALES['ETH']
  for offset in (0.,-.5*tick):
   x.audit_timestamp=f.BASE+11;x.visit(limit+side*offset,(f.BASE+11)*1000,True,advance_ladder=False);assert x.order
  x.audit_timestamp=f.BASE+10;x.visit(limit-side*tick,(f.BASE+10)*1000,True,advance_ladder=False);assert x.order
  x.audit_timestamp=f.BASE+12;x.visit(limit-side*tick,(f.BASE+12)*1000,True,advance_ladder=False);assert x.position and x.position.order.price==limit
 test('through one tick, original limit and strict submission '+str(side),through)
for slip in (.0002,.0005,.001):
 for reason in ('hard_stop','ladder_exit','core_priority_exit'):
  def exitfee(slip=slip,reason=reason):
   x=opened(slip=slip);qty=x.position.order.qty;entry=x.position.order.price;cash=x.cash;x.audit_timestamp=f.BASE+20;x.close(101,reason,(f.BASE+20)*1000)
   assert abs(x.journal[-1]['exit']-101*(1-slip))<1e-9
   assert abs(x.cash-cash-((101*(1-slip)-entry)*qty-x.fee*101*(1-slip)*qty))<1e-8
   E.cash_check(x)
  test('slippage/fees '+str(slip)+' '+reason,exitfee)
def partial_then_replace():
 x=opened();pos=x.position;qty=pos.initial_quantity;x.tranches.append((0.,.25));pos.partial_queue=[1];x.audit_timestamp=f.BASE+20;x.visit(101,(f.BASE+20)*1000,True,advance_ladder=False)
 assert 0<pos.order.qty<qty and len(pos.partial_fills)==1
 x.audit_timestamp=f.BASE+21;x.close(100,'core_priority_exit',(f.BASE+21)*1000);E.cash_check(x)
 assert abs(x.stats['fees']-x.fee*(qty*x.journal[0]['entry']+sum(v['quantity']*v['execution_price']for v in x.journal[0]['partial_fills'])+x.journal[0]['exit']*x.journal[0]['final_exit_quantity']))<1e-8
test('V2 partial then replacement full cash and turnover fee',partial_then_replace)
for side in (1,-1):
 def funding(side=side):
  x=opened(side=side);qty=x.position.order.qty;cash=x.cash;e=dict(complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',time_ms=(f.BASE+20)*1000,mark_price=101.,rate=.0001);x.settle(e)
  assert abs(x.cash-cash+side*qty*101*.0001)<1e-9
  try:x.settle(e);raise RuntimeError('duplicate accepted')
  except AssertionError:pass
  x.audit_timestamp=f.BASE+21;x.close(100,'hard_stop',(f.BASE+21)*1000);E.cash_check(x)
 test('funding sign exact event cash '+str(side),funding)
def funding_partial():
 x=opened();pos=x.position;x.tranches=[(0.,.25)];pos.partial_queue=[1];x.audit_timestamp=f.BASE+15;x.visit(101,(f.BASE+15)*1000,True,advance_ladder=False);qty=x.position.order.qty
 e=dict(complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',time_ms=(f.BASE+20)*1000,mark_price=101.,rate=-.0002);x.settle(e);assert abs(x.funding_total-qty*101*.0002)<1e-9
 x.audit_timestamp=f.BASE+20;x.close(100,'core_priority_exit',(f.BASE+20)*1000);E.cash_check(x)
test('funding before same-time exit uses already reduced quantity',funding_partial)
def ordinary():
 for fee in (0.,.0005):
  x=make(origin='CORE',ratio=1.,fee=fee);y=b.pe.book('ETH',fee,x.leg,x.core,True);y.audit_timestamp=f.BASE+10;y.observing_event=True;y.place((f.BASE+10)*1000,100,1,nearest_tick=True)
  for t,price in [(f.BASE+11,99.7),(f.BASE+22,101),(f.BASE+33,95)]:
   for v in (x,y):r.model.FEE=fee;r.model.SLIP=.0002;v.audit_timestamp=t;v.visit(price,t*1000,True,advance_ladder=False)
  assert x.cash==y.cash
  for new,old in zip(x.journal,y.journal):
   for k,v in old.items():assert new[k]==v
 test_dummy=1
test('C0 C1 normal proxy financial equivalence',ordinary)
def strict():
 s.b.verify_parent();s.a.validate_gate('ETH',s.b.DAY,s.b.EXPECTED_SHA,json.loads((s.OLD/'whitelist_manifest.json').read_text()))
 bad=json.loads((s.OLD/'whitelist_manifest.json').read_text())
 try:s.a.validate_gate('ETH',s.b.DAY,'0'*64,bad);raise RuntimeError('wrong SHA passed')
 except AssertionError:pass
test('original source and anomaly whitelist unchanged',strict)
s.dump(s.OUT/'tests.json',dict(passed=True,total=len(checks),checks=checks,synthetic_not_historical=True,funding_full_replay_unverified_until_official_complete_records=True));print('ALL',len(checks),'PASS')
def same_time_new_event():
 x=make(fill='F_THROUGH');x.current_raw_id=10;x.order.submitted_raw_id=10;x.order.submitted_effective_us=(f.BASE+10)*1000000;limit=x.order.price
 x.audit_timestamp=f.BASE+10;x.visit(limit-.01,(f.BASE+10)*1000,True,advance_ladder=False);assert x.order
 x.current_raw_id=11;x.visit(limit-.01,(f.BASE+10)*1000,True,advance_ladder=False);assert x.position and x.position.order.price==limit
test('same timestamp different new trade allowed; submission event itself forbidden',same_time_new_event)
def optimized_through():
 for side in (1,-1):
  x=make(fill='F_THROUGH',side=side);limit=x.order.price
  rows=np.array([[f.BASE-1,1,100],[f.BASE+11,2,limit],[f.BASE+12,3,limit-side*.005],[f.BASE+13,4,limit-side*.01],[f.BASE+14,5,limit-side*.02]])
  cache=SimpleNamespace(load=lambda t:rows);native=SimpleNamespace()
  market=E.Market(native,cache,x,True)
  for stamp,price,poll in market.events(f.BASE,2):
   if not poll:
    x.audit_timestamp=stamp;x.visit(price,round(stamp*1000),True,advance_ladder=False)
  assert x.position and x.position.opened_us==(f.BASE+13)*1000000
test('optimized real-event selector preserves first through fill in both directions',optimized_through)
s.dump(s.OUT/'tests.json',dict(passed=True,total=len(checks),checks=checks,synthetic_not_historical=True,funding_full_replay_unverified_until_official_complete_records=True));print('FINAL',len(checks),'PASS')
def core_requantifies_after_exit():
 x=opened(ratio=.25);side=x.position.order.side;old_signal=x.order_info['signal_close_ms'];oldqty=x.position.order.qty
 stamp=(f.BASE+900)*1000;x.core[stamp]=side;x.audit_timestamp=f.BASE+910;x.on_core(stamp,100.,side);assert x.replacement
 x.current_raw_id=77;x.audit_timestamp=f.BASE+911;x.visit(99.8,(f.BASE+911)*1000,True,advance_ladder=False)
 assert x.position is None and x.order and x.order_info['origin']=='CORE'
 step=r.model.RULES['ETH'][0];expected=int((3*x.cash/x.order.price+1e-12)/step)*step
 assert abs(x.order.qty-expected)<1e-8 and x.order.qty>oldqty
 assert x.journal[-1]['origin']=='EXTRA'and x.journal[-1]['signal_close_ms']==old_signal
 E.cash_check(x)
test('CORE exit first then re-quantity full size from updated cash, original EXTRA tag retained',core_requantifies_after_exit)
def small_v2_unchanged_budget():
 x=opened(ratio=.25);pos=x.position
 t=f.BASE+1800;i=(t*1000-x.leg.first)//900000-1
 f.weak(x.leg,i,1);f.weak(x.leg,i-1,1)
 x.leg.bars[t*1000-900000].c=pos.order.price+.1
 s.z.v.check(x,t)
 ev=[e for e in x.events if e['event']=='adaptive_v2_request']
 if ev:
  assert ev[-1]['budget']==max(0.,x.cash)*.03
  assert ev[-1]['requested_quantity']<=pos.initial_quantity*.25+1e-9
 else:assert not getattr(pos,'adaptive_v2_used',False)
test('small size keeps original V2 balance budget and25pct cap/no-request rule',small_v2_unchanged_budget)
s.dump(s.OUT/'tests.json',dict(passed=True,total=len(checks),checks=checks,synthetic_not_historical=True,funding_full_replay_unverified_until_official_complete_records=True));print('FINAL',len(checks),'PASS')
