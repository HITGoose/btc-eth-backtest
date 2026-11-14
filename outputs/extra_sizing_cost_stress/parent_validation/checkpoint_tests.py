from pathlib import Path
import pickle,copy
import numpy as np
import strategy as z
import priority_engine as pe
OUT=z.OUT;f=z.module('priority_checkpoint_fixtures',OUT/'validation32/tests.py');checks=[]
def generator(b,leg,rows,start,end):
 m=pe.Market(f.Native(),f.Cache(rows),b,True)
 return pe.generator(b)('ETH',leg=leg,signals={f.BASE*1000:1,(f.BASE+900)*1000:1},market=m,start=start*1000,end=end*1000,poll_seconds=5,poll_phase=2,print_progress=False)
for side in(1,-1):
 for priority in(False,True):
  leg=f.leg_for(side);rows=np.array([[f.BASE-1,0,100],[f.BASE+10.1,1,100-side*.3],[f.BASE+899,2,100-side*.3],[f.BASE+1900,3,100-side*.4],[f.BASE+1900.1,4,100-side*.4],[f.BASE+2100,5,100-side*5]],dtype=float)
  # Signal side follows fixture; both fee books share the same immutable tape.
  signals={f.BASE*1000:side,(f.BASE+900)*1000:side};core={(f.BASE+900)*1000:side};books={};gens={}
  for fee in(0.,.0005):
   b=pe.book('ETH',fee,leg,core,priority);books[fee]=b
   m=pe.Market(f.Native(),f.Cache(rows),b,True);gens[fee]=pe.generator(b)('ETH',leg=leg,signals=signals,market=m,start=f.BASE*1000,end=(f.BASE+2400)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
  for t in range(f.BASE,f.BASE+960,60):
   for fee,g in gens.items():z.r.model.FEE=fee;assert next(g)==t
  isolated={}
  for fee,b in books.items():
   b.leg=None;isolated[fee]=pickle.loads(pickle.dumps(b,protocol=5));b.leg=leg;isolated[fee].leg=leg
   assert bool(isolated[fee].replacement)==priority
  for t in range(f.BASE+960,f.BASE+2400,60):
   for fee,g in gens.items():z.r.model.FEE=fee;assert next(g)==t
  for fee,g in gens.items():
   z.r.model.FEE=fee
   try:next(g)
   except StopIteration:pass
  for fee,b in isolated.items():
   z.r.model.FEE=fee;m=pe.Market(f.Native(),f.Cache(rows),b,True);g=pe.generator(b)('ETH',leg=leg,signals=signals,market=m,start=(f.BASE+960)*1000,end=(f.BASE+2400)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
   for t in range(f.BASE+960,f.BASE+2400,60):assert next(g)==t
   try:next(g)
   except StopIteration:pass
   expected=books[fee];assert b.cash==expected.cash and b.journal==expected.journal and b.events==expected.events and b.cash_events==expected.cash_events and b.stats==expected.stats
   checks.append(dict(side=side,priority=priority,fee=fee,shared_fee_interleaving_equals_single_cost_checkpoint=True,priority_lock_survives=True))
z.dump(OUT/'checkpoint_tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks),'same-fingerprint fee isolation/checkpoint cases')
