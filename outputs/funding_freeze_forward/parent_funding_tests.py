from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"extra_sizing_cost_stress"))
from types import SimpleNamespace
import json
import shared as s
import cost_engine as C
np=s.np;b=s.b;r=s.r;f=s.z.module('funding_fixtures',b.PARENT/'validation32/tests.py');checks=[]
import funding_engine as F
assert s.b.e.x.check_trend is F.funding_check

def test(n,fn):fn();checks.append(dict(name=n,passed=True));print('PASS',n)
def event(ms,rate=.001):return dict(time_ms=ms,rate=rate,mark_price=100.,complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL')
def make(side=1,opened=True,feed=None,slip=.0002):
 F.FEED=[]if feed is None else feed;leg=f.leg_for(side);x=F.book('ETH',.0005,slip,leg,{},True,.5);s.activate(x);x.audit_timestamp=f.BASE-30;x.observing_event=True;x.place((f.BASE-30)*1000,100.,side,nearest_tick=True)
 if opened:x.audit_timestamp=f.BASE-29;x.visit(x.order.price,(f.BASE-29)*1000,True,advance_ladder=False)
 return x
for side in(1,-1):
 def close_reconcile(side=side):
  x=make(side,feed=[event(f.BASE*1000)]);cash=x.cash;qty=x.position.order.qty;F.funding_check(x,f.BASE);assert abs(x.cash-cash+side*qty*.1)<1e-8
  x.audit_timestamp=f.BASE+1;x.close(100.,'core_priority_exit',(f.BASE+1)*1000);F.cash_check(x);assert abs(x.cash-500-x.journal[-1]['net'])<1e-8
 test('funded closed net and cash direction '+str(side),close_reconcile)
def partial():
 x=make(feed=[event((f.BASE+20)*1000)]);x.tranches=[(0.,.25)];x.position.partial_queue=[1];x.audit_timestamp=f.BASE+10;x.visit(100,(f.BASE+10)*1000,True,advance_ladder=False);qty=x.position.order.qty;x.apply_funding((f.BASE+20)*1000);assert abs(x.funding_total+qty*.1)<1e-8
 x.audit_timestamp=f.BASE+30;x.close(100,'hard_stop',(f.BASE+30)*1000);F.cash_check(x)
test('funding uses actual remainder after V2 partial; complete net reconciles',partial)
class Cache:
 def __init__(self,rows):self.rows=rows
 def load(self,t):return self.rows
class Native:
 def __getitem__(self,t):return [100.,101.,95.,100.,0.]
def market_case(feed,rows,opened=True):
 x=make(opened=opened,feed=feed);m=F.Market(Native(),Cache(np.array(rows,dtype=float)),x,False)
 for stamp,price,poll in m.events(f.BASE,2):
  if not poll:
   x.audit_timestamp=stamp;x.visit(price,round(stamp*1000),True,advance_ladder=False)
 return x

def before_same_exit():
 e=event((f.BASE+3)*1000);rows=[[f.BASE-1,1,100.],[f.BASE+3,2,95.],[f.BASE+20,3,100.]];x=market_case([e],rows)
 assert x.journal and x.journal[0]['funding_net_USDT']<0
 assert x.funding_events[0]['time_ms']==(f.BASE+3)*1000
 F.cash_check(x)
test('actual settlement is before same-time stop print',before_same_exit)
def before_same_entry():
 e=event((f.BASE+3)*1000);rows=[[f.BASE-1,1,100.],[f.BASE+3,2,99.7],[f.BASE+20,3,95.]];x=market_case([e],rows,opened=False)
 assert x.funding_total==0 and x.journal[0]['funding_net_USDT']==0
 F.cash_check(x)
test('same-time new entry is not retrospectively charged',before_same_entry)
def micro_before_boundary():
 e=event((f.BASE+3)*1000);x=make(feed=[e]);m=F.Market(Native(),Cache(np.array([[f.BASE-1,1,100.],[f.BASE+2.9999,2,95.],[f.BASE+4,3,100.]])),x,False)
 for stamp,p,kind in m.events(f.BASE,2):
  if not kind:x.audit_timestamp=stamp;x.visit(p,round(stamp*1000),True,advance_ladder=False)
 assert x.journal[0]['funding_net_USDT']==0 and x.funding_total==0
 F.cash_check(x)
test('microsecond raw before settlement cannot be rounded into future funding',micro_before_boundary)
def after_last_poll():
 x=market_case([event((f.BASE+59)*1000)],[[f.BASE-1,1,100.],[f.BASE+1,2,100.],[f.BASE+10,3,100.]])
 assert x.funding_total<0 and x.last_funding_ms==(f.BASE+59)*1000
 F.cash_check(x)
test('settlement after last poll is included before minute mark',after_last_poll)
def midnight_before_v2():
 x=make(feed=[event(f.BASE*1000)]);old=s.b.e.x.check_trend;cash=x.cash
 F.funding_check(x,f.BASE);assert x.cash<cash and x.last_funding_ms==f.BASE*1000
 F.cash_check(x)
test('minute-boundary funding precedes closed15m V2 check',midnight_before_v2)
def nofund_equivalent():
 a=make(feed=[]);leg=a.leg;c=C.book('ETH',.0005,.0002,leg,{},True,.5);s.activate(c);c.audit_timestamp=f.BASE-30;c.observing_event=True;c.place((f.BASE-30)*1000,100,1,nearest_tick=True);c.audit_timestamp=f.BASE-29;c.visit(c.order.price,(f.BASE-29)*1000,True,advance_ladder=False)
 for x in (a,c):x.audit_timestamp=f.BASE+10;x.close(100,'hard_stop',(f.BASE+10)*1000)
 assert a.cash==c.cash and a.journal[0]['net']==c.journal[0]['net']
test('empty feed leaves execution finances identical; never used to fill missing history',nofund_equivalent)
s.dump(Path(__file__).resolve().parent/'parent_funding_tests.json',dict(passed=True,total=len(checks),checks=checks,synthetic_not_archive_validation=True));print('ALL',len(checks),'PASS')
def full_loop_funding_v2_mark():
 x=make(feed=[event(f.BASE*1000),event((f.BASE+59)*1000)]);qty=x.position.order.qty;before=x.cash
 f.weak(x.leg,0,1);f.weak(x.leg,1,1)
 rows=np.array([[f.BASE-1,1,100.],[f.BASE+1,2,100.],[f.BASE+50,3,100.]])
 market=F.Market(Native(),Cache(rows),x,True)
 g=b.pe.generator(x)('ETH',leg=x.leg,signals={},market=market,start=f.BASE*1000,end=(f.BASE+60)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
 assert next(g)==f.BASE
 try:next(g);raise RuntimeError('overshot')
 except StopIteration as stop:q=stop.value
 request=next(e for e in x.events if e['event']=='adaptive_v2_request');assert abs(request['realized_balance']-(before-qty*.1))<1e-8
 assert len(x.funding_events)==2 and x.funding_events[1]['quantity']<x.funding_events[0]['quantity']
 assert abs(q['marks'][0]-x.equity(100))<1e-8
 F.cash_check(x)
test('actual original generator wires funding before V2, partial quantity and last-minute mark',full_loop_funding_v2_mark)
def future_feed():
 a=make(feed=[event(f.BASE*1000),event((f.BASE+3600)*1000,.9)]);a.apply_funding(f.BASE*1000)
 z=make(feed=[event(f.BASE*1000),event((f.BASE+3600)*1000,-.9)]);z.apply_funding(f.BASE*1000)
 assert a.cash==z.cash and a.position.order.qty==z.position.order.qty and a.funding_total==z.funding_total
test('future funding values cannot change current account decisions',future_feed)
def missing_history_guard():
 try:F.configure_feed('2020','ETH');raise RuntimeError('missing historical mark accepted')
 except AssertionError:pass
test('incomplete official historical prices cannot enable funded full-year mode',missing_history_guard)
s.dump(Path(__file__).resolve().parent/'parent_funding_tests.json',dict(passed=True,total=len(checks),checks=checks,synthetic_not_archive_validation=True));print('FINAL',len(checks),'PASS')
