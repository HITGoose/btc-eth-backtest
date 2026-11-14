"""Compare causal event selection against every raw print, including bad OHLC."""
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import engine as e
BASE=1704067200;DURATION=1200
class Native:
 def __init__(self):
  self.first=BASE-60;self.end=BASE+DURATION
  self.rows=np.tile([100.,100.001,99.999,100.,1.],((DURATION+60)//60,1))
 def __getitem__(self,t):return self.rows[(t-self.first)//60]
class Cache:
 def __init__(self,rows):self.rows=rows
 def load(self,t):return self.rows

def execute(rows,profile,optimized,side):
 native=Native();cache=Cache(rows)
 leg=SimpleNamespace(first=(BASE-9000)*1000,up=np.full(32,6.),down=np.full(32,6.),histogram=np.full(32,float(side)),bars={BASE*1000-900000:SimpleNamespace(c=100.),(BASE+900)*1000-900000:SimpleNamespace(c=100.)})
 leg.histogram[10:]=-side
 book=e.new_book('BTC',profile,leg);market=e.Market(native,cache,book,optimized)
 g=e.generator(book)('BTC',leg=leg,signals={BASE*1000:side,(BASE+900)*1000:side},market=market,start=BASE*1000,end=(BASE+DURATION)*1000,print_progress=False,poll_seconds=5,poll_phase=2,starting_cash=500.,leverage=3.)
 for minute in range(BASE,BASE+DURATION,60):assert next(g)==minute
 try:next(g);raise AssertionError('Overshot')
 except StopIteration as stop:result=stop.value
 assert not result['approximated_minutes']
 return book,result
checks=[]
for seed in range(16):
 rng=np.random.default_rng(seed);offset=np.sort(np.r_[np.arange(0,DURATION,.37),2.,7.,10.,10.,10.001,12.,17.,900.,902.])
 prices=100+np.cumsum(rng.normal(0,.11,len(offset)))
 if seed%2==0:prices[(offset>15)&(offset<50)]+=4
 if seed%3==0:prices[(offset>60)&(offset<80)]-=8
 rows=np.column_stack((np.r_[BASE-1,BASE+offset],np.arange(len(offset)+1),np.r_[100.,prices]))
 for side in (1,-1):
  for profile in ('CONTROL','DYNAMIC'):
   a,qa=execute(rows,profile,False,side);b,qb=execute(rows,profile,True,side)
   assert a.journal==b.journal,(seed,side,profile,'trade mismatch')
   assert a.events==b.events,(seed,side,profile,'event mismatch')
   assert abs(a.cash-b.cash)<1e-9 and qa['marks']==qb['marks']
   checks.append(dict(seed=seed,side=side,profile=profile,passed=True))
Path(__file__).with_name('event_selection_validation.json').write_text(json.dumps(dict(synthetic_only=True,historical_validation=False,checks=checks,tests='Every actual print vs causal selected prints; exact submission boundaries, polling ties, fills, stop gaps, partial fills, dynamic closed15m, wrong OHLC bounds'),indent=2))
print('PASS',len(checks),'full-raw vs optimized financial/event comparisons')
