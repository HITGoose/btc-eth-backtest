from pathlib import Path
import numpy as np
import strategy as z
import priority_engine as pe
OUT=z.OUT;f=z.module('priority_boundary_fixtures',OUT/'validation32/tests.py');checks=[]
def run(tape,signals,core,seconds):
 leg=f.leg_for(1);b=pe.book('ETH',0.,leg,core,True);z.r.model.FEE=0.
 market=pe.Market(f.Native(),f.Cache(np.array(tape,dtype=float)),b,True)
 g=pe.generator(b)('ETH',leg=leg,signals=signals,market=market,start=f.BASE*1000,end=(f.BASE+seconds)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
 for t in range(f.BASE,f.BASE+seconds,60):assert next(g)==t
 try:next(g);raise AssertionError('overshot')
 except StopIteration:pass
 return b
for oldside in(1,-1):
 for newside in(1,-1):
  core={(f.BASE+900)*1000:newside};tape=[[f.BASE-1,0,100],[f.BASE+10.1,1,100],[f.BASE+909.9,2,100],[f.BASE+910.,3,100],[f.BASE+920,4,100-newside*.3],[f.BASE+1100,5,100-newside*5]]
  b=run(tape,{f.BASE*1000:oldside,**core},core,1200)
  assert b.stats['priority_cancelled']==1 and b.stats['submitted']==2 and len(b.journal)==1
  assert b.journal[0]['signal_close_ms']==(f.BASE+900)*1000
  assert next(x['time_us']for x in b.events if x['event']=='priority_cancel_extra_order')==(f.BASE+910)*1000000
  checks.append(dict(case='pending_cancel_full_generator',oldside=oldside,newside=newside,passed=True))
for side in(1,-1):
 core={(f.BASE+3600)*1000:side};tape=[[f.BASE-1,0,100],[f.BASE+10.1,1,100],[f.BASE+3609,2,100],[f.BASE+3610,3,100-side*.3],[f.BASE+3610.1,4,100-side*.3],[f.BASE+3700,5,100-side*5]]
 b=run(tape,{f.BASE*1000:side,**core},core,3780)
 assert b.stats['expired']==1 and b.stats['priority_cancelled']==0 and len(b.journal)==1
 assert b.journal[0]['signal_close_ms']==(f.BASE+3600)*1000
 checks.append(dict(case='expiry_at_exact_CORE_clock_before_cancel',side=side,passed=True))
for side in(1,-1):
 core={(f.BASE+900)*1000:side,(f.BASE+1800)*1000:-side};tape=[[f.BASE-1,0,100],[f.BASE+10.1,1,100-side*.3],[f.BASE+899,2,100-side*.3],[f.BASE+1900,3,100-side*.4],[f.BASE+1900.1,4,100-side*.4],[f.BASE+2100,5,100-side*5]]
 b=run(tape,{f.BASE*1000:side,**core},core,2160)
 assert len([x for x in b.events if x['event']=='priority_replace_requested'])==1
 assert len([x for x in b.events if x['event']=='priority_duplicate_core_ignored'])==1
 assert len(b.journal)==2 and b.journal[0]['closed_us']==(f.BASE+1900)*1000000
 assert b.journal[1]['signal_close_ms']==(f.BASE+900)*1000 and b.journal[1]['side']==('LONG'if side==1 else'SHORT')
 checks.append(dict(case='lock_across_minutes_repeated_opposite_CORE_no_rewrite',side=side,passed=True))
z.dump(OUT/'boundary_tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks),'full event-loop cancellation/expiry/lock boundary cases')
