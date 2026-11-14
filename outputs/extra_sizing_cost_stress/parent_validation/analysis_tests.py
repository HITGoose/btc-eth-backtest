from pathlib import Path
import sys,json,copy
import numpy as np
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
import strategy as z
import priority_engine as pe
h=z.module('priority_test_analysis_helpers',OUT/'analysis_helpers.py');f=z.module('priority_test_analysis_fixtures',OUT/'validation32/tests.py')
checks=[]
for priority in(False,True):
 for fee in(0.,.0005):
  for side in(1,-1):
   leg=f.leg_for(side)
   for j in(2,3,5,6):f.weak(leg,j,side)
   core={(f.BASE+900)*1000:side};b=pe.book('ETH',fee,leg,core,priority);z.r.model.FEE=fee
   tape=f.synthetic_tape(0,side);market=pe.Market(f.Native(),f.Cache(tape),b,True);signals={f.BASE*1000:side,**core}
   gen=pe.generator(b)('ETH',leg=leg,signals=signals,market=market,start=f.BASE*1000,end=(f.BASE+f.DURATION)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
   for t in range(f.BASE,f.BASE+f.DURATION,60):assert next(gen)==t
   try:next(gen);raise AssertionError('overshot')
   except StopIteration as stop:result=stop.value
   assert not b.position
   q=dict(asset='ETH',window=[z.r.local_s(f.BASE),z.r.local_s(f.BASE+f.DURATION)],trades=b.journal,events=b.events,place_attempts=b.place_attempts,cash_events=b.cash_events,fee=fee,cash=b.cash,ending_equity=b.cash,state_at_end=z.p.state(b),open_contribution=0.,stats=dict(b.stats))
   marks=np.asarray(result['marks']);vec=h.curve(q,marks);assert np.allclose(vec['directions'][1]+vec['directions'][-1]-500,marks)
   assert abs(sum(t['net']for t in q['trades'])-q['cash']+500)<1e-8
   match=h.compare(q,q,{});assert all(x['category']=='RETAINED'and abs(x['actual_USDT_delta'])<1e-8 for x in match)
   if priority:
    assert any(t['signal_close_ms']==(f.BASE+900)*1000 for t in q['events']if t['event']=='order_sent')
    assert b.stats['expired']==1, 'replacement CORE can expire without filling'
    assert b.journal[0]['reason']=='core_priority_exit'
   checks.append(dict(priority=priority,fee=fee,side=side,cash=True,fee_turnover=True,direction_curve=True,signal_key=True,self_match=True))
z.dump(OUT/'analysis_tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks),'analysis cases')
