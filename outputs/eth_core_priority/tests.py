from pathlib import Path
from types import SimpleNamespace
import importlib.util,sys,json,pickle,tempfile
import numpy as np
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
import strategy as z
import priority_engine as pe
f=z.module('priority_synthetic_fixtures',OUT/'validation32/tests.py')
checks=[]
def test(name,fn):
 fn();checks.append(dict(name=name,passed=True));print('PASS',name,flush=True)
def at(b,t):b.audit_timestamp=t;b.observing_event=True
def make(side=1,fee=0.,priority=True):
 leg=f.leg_for(side);b=pe.book('ETH',fee,leg,{},priority);z.r.model.FEE=fee
 at(b,f.BASE+10);b.place((f.BASE+10)*1000,100.,side,nearest_tick=True)
 return b,leg
def opened(side=1,fee=0.):
 b,l=make(side,fee);at(b,f.BASE+10.123);b.visit(b.order.price,round((f.BASE+10.123)*1000),True,advance_ladder=False);return b,l
def core(b,t,side=1,ref=100.):
 stamp=t*1000;b.core[stamp]=side;at(b,t+10);b.on_core(stamp,ref,side)
def classify():
 c={1000:1};w={1000:1,2000:-1,3000:1};btc={1000:-1,2000:-1,3000:-1}
 for g in ('G','I'):
  sig,rows=z.classify(c,w,btc,g);assert sig=={1000:1,2000:-1};assert rows[0]['origin']=='CORE'and rows[2]['origin']=='EXTRA'
  btc[99999999]=1;assert z.classify(c,w,btc,g)[0]==sig
 for g in ('D','H'):assert z.classify(c,w,{},g)[0]==w
 test_sig,_=z.classify(c,w,{2000:1},'G');assert test_sig==c

def pending():
 b,_=make();old=b.order;core(b,f.BASE+900,-1,101.)
 assert b.stats['priority_cancelled']==1 and b.order.time==(f.BASE+910)*1000
 assert b.order.price==z.r.model.limit_price('ETH',101.,-1,nearest_tick=True)
 assert b.order.origin=='CORE'and b.order.signal_close_ms==(f.BASE+900)*1000
 assert z.r.seconds.expiry(b)==f.BASE+4510
 core(b,f.BASE+1800,1);assert b.order.time==(f.BASE+910)*1000 and b.stats['submitted']==2

def replacement(side,nextside,fee,partial=False,stop=False):
 b,l=opened(side,fee);entry=b.position.order.price
 if partial:
  i=(f.BASE+1800-l.first//1000)//900-1
  f.weak(l,i-1,side);f.weak(l,i,side);at(b,f.BASE+1800);z.v.check(b,f.BASE+1800)
  at(b,f.BASE+1800.1);b.visit(entry+side*.1,round((f.BASE+1800.1)*1000),True,advance_ladder=False)
  assert len(b.position.partial_fills)==1
 core(b,f.BASE+2700,nextside)
 first=dict(b.replacement);core(b,f.BASE+3600,-nextside);assert b.replacement==first
 at(b,f.BASE+2710);b.visit(entry,round((f.BASE+2710)*1000),True,advance_ladder=False);assert b.position and b.replacement
 price=b.position.stop-side*2 if stop else entry+side*.2
 at(b,f.BASE+2710.123456);b.visit(price,round((f.BASE+2710.123456)*1000),True,advance_ladder=False)
 assert b.position is None and b.order is not None and b.replacement is None
 row=b.journal[-1];assert row['reason']==('hard_stop'if stop else'core_priority_exit')
 assert row['signal_close_ms']==f.BASE*1000 and row['origin']=='EXTRA'
 assert b.order.signal_close_ms==(f.BASE+2700)*1000
 assert abs(b.order.time*1000-round((f.BASE+2710.123456)*1e6))<.1
 assert abs(row['exit']-price*(1-side*.0002))<1e-9
 assert abs(b.cash-500-row['net'])<1e-8
 assert abs(sum(x['delta']for x in b.cash_events)-row['net'])<1e-8
 assert abs(b.stats['fees']-fee*(entry*row['quantity']+row['exit']*row['final_exit_quantity']+sum(x['quantity']*x['execution_price']for x in row['partial_fills'])))<1e-8
 # Expire the replacement without any fill; this is a genuine unfilled outcome.
 z.r.seconds.expire(b,b.order.time/1000+3600);assert b.order is None and not b.position
 assert b.stats['submitted']==b.stats['long']+b.stats['short']+b.stats['expired']+b.stats['priority_cancelled']

def core_not_replaced():
 b,l=opened();b.order_info['origin']='CORE';core(b,f.BASE+900,-1);assert b.replacement is None and b.position

def queue_priority():
 b,l=opened();b.position.partial_queue=[1];b.tranches=[(0.,.25)];core(b,f.BASE+900)
 at(b,f.BASE+910.1);b.visit(b.position.order.price,round((f.BASE+910.1)*1000),True,advance_ladder=False)
 assert not b.journal[-1]['partial_fills']

def fake_native(rows,end):
 class N:
  first=f.BASE-60
  def __getitem__(self,t):return [100,200,1,100,1]
 return N()
def loop_equivalence(side,optimized):
 # Actual request at +910; true first later print is .123, then same timestamp
 # next ID is eligible for the new order (but the exit print itself is not).
 corestamp=(f.BASE+900)*1000
 rows=np.array([[f.BASE-1,0,100.],[f.BASE+10.1,1,100-side*.3],[f.BASE+909.9,2,100.],[f.BASE+910.,3,100.],[f.BASE+910.123,4,100-side*.4],[f.BASE+910.123,5,100-side*.4],[f.BASE+950.,6,100.],[f.BASE+1100,7,100-side*5.]])
 b,l=make(side,0.);b.order=None;b.stats.clear();b.events=[];b.place_attempts=[];b.core={corestamp:side}
 m=pe.Market(fake_native(rows,f.BASE+1200),f.Cache(rows),b,optimized)
 g=pe.generator(b)('ETH',leg=l,signals={f.BASE*1000:side,corestamp:side},market=m,start=f.BASE*1000,end=(f.BASE+1200)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
 for t in range(f.BASE,f.BASE+1200,60):assert next(g)==t
 try:next(g)
 except StopIteration:pass
 assert len(b.journal)==2
 assert b.journal[0]['reason']=='core_priority_exit'
 assert b.journal[0]['closed_us']==round((f.BASE+910.123)*1e6)
 assert b.journal[1]['signal_close_ms']==corestamp
 fills=[x for x in b.events if x['event']=='limit_touch_proxy_fill'];assert len(fills)==2
 exitseq=next(x['exit_raw_sequence']for x in b.events if x['event']=='priority_position_closed')
 assert fills[1]['raw_sequence']>exitseq
 return b

def causal_real():
 info=z.prepare('2024','ETH');btc=z.prepare('2024','BTC')
 for threshold,key in[(.25,'core'),(.30,'wide')]:
  old=json.loads((z.OLD/'runs/2024/ETH/signals.json').read_text())[str(threshold)]
  assert info[key]=={int(k):v for k,v in old.items()}
 assert btc['core']==btc['wide']
 cutoff=info['start']+125*86400;data=info['data'];raw=np.loadtxt(data/'BTC_15m.csv',delimiter=',',skiprows=1)
 with tempfile.TemporaryDirectory(dir='/tmp')as tmp:
  file=Path(tmp)/'BTC_15m.csv';np.savetxt(file,raw[raw[:,0]<cutoff*1000],delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
  small=z.s.prepare('BTC',Path(tmp),btc['start'],cutoff,.25)[1]
  assert {k:v for k,v in small.items()if btc['start']*1000<=k<cutoff*1000}=={k:v for k,v in btc['core'].items()if btc['start']*1000<=k<cutoff*1000}
  full=z.classify(info['core'],info['wide'],btc['core'],'G')[0];prefix=z.classify(info['core'],info['wide'],small,'G')[0]
  assert {k:v for k,v in full.items()if info['start']*1000<=k<cutoff*1000}=={k:v for k,v in prefix.items()if info['start']*1000<=k<cutoff*1000}
 assert z.prepare('2024','ETH')['wide']==info['wide']

test('classification contemporaneous, CORE immune, BTC future ignored',classify)
test('CORE cancel EXTRA pending exact +10, reference and lifetime, CORE protected',pending)
test('CORE holding protected',core_not_replaced)
test('full replacement preempts queued discretionary V2 partial',queue_priority)
for side in (1,-1):
 for nextside in (side,-side):
  for fee in (0.,.0005):
   for partial,stop in [(False,False),(True,False),(False,True),(True,True)]:
    test(f'replace side{side} next{nextside} fee{fee} partial{partial} stop{stop}',lambda side=side,nextside=nextside,fee=fee,partial=partial,stop=stop:replacement(side,nextside,fee,partial,stop))
for side in(1,-1):
 def match(side=side):
  a=loop_equivalence(side,False);b=loop_equivalence(side,True)
  assert a.journal==b.journal and a.cash==b.cash
 test(f'full tape vs selection side{side}, exit and new fill different events',match)
test('real full-chain B/D, BTC fixed, prefix causality, isolated state',causal_real)
z.dump(OUT/'tests.json',dict(passed=True,total=len(checks),checks=checks));print('ALL',len(checks),'PASS')
