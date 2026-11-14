from pathlib import Path
from types import SimpleNamespace
import copy,json,hashlib,inspect
import numpy as np
import bridge as b
import adapter as a
import observer as o
OUT=b.OUT;checks=[]
def test(name,fn):
 fn();checks.append(dict(name=name,passed=True));print('PASS',name,flush=True)
def rejects(fn):
 try:fn()
 except(AssertionError,RuntimeError,ValueError):return
 raise AssertionError('Expected a strict rejection')
views=a.Views();m=views.manifest

def strict_rejects():
 folder=OUT/'tests_strict_cache';folder.mkdir(exist_ok=True);cache=b.e.RawCache('ETH',None,folder);target=cache.temp/b.ARCHIVE.name
 if not target.exists():target.hardlink_to(b.ARCHIVE)
 original=b.d.acquire
 def fixture(url,path):
  assert path==target and hashlib.file_digest(path.open('rb'),'sha256').hexdigest()==b.EXPECTED_SHA
  return dict(url=url,sha256=b.EXPECTED_SHA,official_checksum_match=True)
 try:b.d.acquire=fixture;rejects(lambda:cache.load(1756425600))
 finally:b.d.acquire=original
 assert b.w.fingerprint()==b.PARENT_FP

test('unchanged original strict RawCache rejects real conflicting archive',strict_rejects)
for label,args in[('asset',('BTC',b.DAY,b.EXPECTED_SHA)),('date',('ETH','2025-08-28',b.EXPECTED_SHA)),('SHA',('ETH',b.DAY,'0'*64))]:test('whitelist rejects wrong '+label,lambda args=args:rejects(lambda:a.validate_gate(*args,m)))
def extra_rejected():
 bad=copy.deepcopy(m);bad['duplicate_ids']['123']=2;rejects(lambda:a.validate_gate('ETH',b.DAY,b.EXPECTED_SHA,bad))
 bad=copy.deepcopy(m);bad['confirmed_quote_issue_lines'].append(123);rejects(lambda:a.validate_gate('ETH',b.DAY,b.EXPECTED_SHA,bad))
test('extra unconfirmed anomalies are not globally waived',extra_rejected)
def integers():
 assert views.ids.dtype==np.int64 and views.time_ms.dtype==np.int64
 for item in m['conflicts']:
  for rec in item['records']:
   i=rec['source_line']-2;assert int(rec['fields'][0])==int(views.ids[i])and int(rec['fields'][4])==int(views.time_ms[i])
 assert np.max(views.ids)<2**53 and np.max(views.time_ms)<2**53
test('integer ID/time parsing matches complete raw string records',integers)
def all_retained():
 v=views.get('S_ALL');assert len(v['rows'])==m['rows'];assert np.array_equal(np.sort(v['lines']),np.arange(2,m['rows']+2))
 assert np.array_equal(v['rows'][:,2],views.price[v['indices']])
 ties=np.flatnonzero(np.diff(views.time_ms[v['indices']])==0);assert np.all(v['lines'][ties+1]>v['lines'][ties])
test('S_ALL retains every original row and stable integer-time ties',all_retained)
for scenario in b.SCENARIOS[1:]:
 def selection(scenario=scenario):
  v=views.get(scenario);assert len(v['rows'])==m['rows']-3
  for trade,bit in zip(b.IDS,scenario[2:]):
   line=views.pairs[trade][int(bit)]+2;assert v['metadata']['retained_conflict_lines'][str(trade)]==[line]
   assert views.pairs[trade][1-int(bit)]+2 in v['metadata']['dropped_original_lines']
  assert np.array_equal(v['rows'][:,1].astype(np.int64),views.ids[v['indices']]);assert np.array_equal(v['rows'][:,2],views.price[v['indices']])
 test(scenario+' selects exactly its three specified records; fields unchanged',selection)
test('all nine pre-fork and post-merge inputs and last quotes match',lambda:views.equivalence_proof())

f=b.z.module('sensitivity_synthetic_fixtures',b.PARENT/'validation32/tests.py')
class FakeStrict:
 asset='ETH'
 def __init__(self,rows):self.rows=rows
 def load(self,t):return self.rows
class TinyViews:
 def __init__(self,rows,drop=None):self.original=rows;self.drop=drop
 def get(self,scenario):
  keep=np.arange(len(self.original));keep=keep[keep!=self.drop]if scenario=='S_111'and self.drop is not None else keep
  return dict(rows=self.original[keep],indices=keep,lines=keep+2)
 def identity(self,scenario,index):
  v=self.get(scenario);i=int(v['indices'][index]);row=self.original[i]
  return dict(original_source_line=i+2,original_trade_id=int(row[1]),timestamp_integer=round(row[0]*1000),time_unit='ms',price=float(row[2]),internal_event_id='SYNTHETIC_ONLY:line:'+str(i+2))
 def latest(self,scenario,t):
  rows=self.get(scenario)['rows'];i=int(np.searchsorted(rows[:,0],t,side='right'))-1
  return self.identity(scenario,i)if i>=0 else None

def sim(rows,scenario,*,opened=False,priority=False,fee=0.,side=1,queued=False,plain=False):
 leg=f.leg_for(side);core={f.BASE*1000:side}if priority else{}
 book=b.pe.book('ETH',fee,leg,core,priority);b.r.model.FEE=fee
 if not plain:o.instrument(book,(f.BASE*1000000,(f.BASE+60)*1000000))
 if opened or queued:
  book.audit_timestamp=f.BASE-100;book.observing_event=True;book.place((f.BASE-100)*1000,100.,side,nearest_tick=True)
  book.visit(book.order.price,round((f.BASE-99)*1000),True,advance_ladder=False)
  if queued:
   f.weak(leg,0,side);f.weak(leg,1,side)
 strict=FakeStrict(rows);tiny=TinyViews(rows,2);native=f.Native()
 if plain:market=b.pe.Market(native,strict,book,True)
 else:market=a.Market(native,a.ScenarioCache(strict,tiny,scenario),book,True)
 sig={f.BASE*1000:side}if not opened and not queued else core
 g=b.pe.generator(book)('ETH',leg=leg,signals=sig,market=market,start=f.BASE*1000,end=(f.BASE+60)*1000,poll_seconds=5,poll_phase=2,print_progress=False)
 assert next(g)==f.BASE
 try:next(g);raise AssertionError('overshot')
 except StopIteration as stop:result=stop.value
 return book,result,market

def ordinary_equivalent():
 f.BASE=1704067200
 rows=np.array([[f.BASE-1,0,100],[f.BASE+10.001,1,99.7],[f.BASE+20,2,100.1],[f.BASE+50,3,95]],dtype=float)
 for fee in(0.,.0005):
  old,r0,_=sim(rows,'S_ALL',fee=fee,plain=True);new,r1,_=sim(rows,'S_ALL',fee=fee)
  assert old.journal==new.journal and old.events==new.events and old.cash==new.cash and r0['marks']==r1['marks']
test('ordinary data delegates strict and financial trace is behavior-neutral',ordinary_equivalent)

def latest_poll_and_stop():
 f.BASE=1756425600
 rows=np.array([[f.BASE-1,1,100],[f.BASE+1,2,100],[f.BASE+3,3,102],[f.BASE+23,3,100],[f.BASE+50,4,95]],dtype=float)
 allbook,_,_=sim(rows,'S_ALL',opened=True);late,_,_=sim(rows,'S_111',opened=True)
 assert allbook.journal[0]['reason']=='ladder_exit'and late.journal[0]['reason']=='hard_stop'
 traces=allbook._sensitivity_trace;seven=next(x for x in traces if x['input']['kind']=='POLL'and x['input']['time_us']==(f.BASE+7)*1000000)
 assert seven['input']['price']==102 and seven['input']['latest_real_quote']['original_source_line']==4
 assert seven['pre_state']['position']['rung']!=seven['post_state']['position']['rung']
test('conflicting print can change latest poll, ladder and eventual stop',latest_poll_and_stop)

def limit_time():
 f.BASE=1756425600
 rows=np.array([[f.BASE-1,1,100],[f.BASE+1,2,100],[f.BASE+13,3,99.7],[f.BASE+23,3,100],[f.BASE+50,4,95]],dtype=float)
 x,_,_=sim(rows,'S_ALL');y,_,_=sim(rows,'S_111')
 assert x.journal[0]['opened_us']!=y.journal[0]['opened_us']
 assert x.journal[0]['opened_us']==(f.BASE+13)*1000000
test('conflicting print can change limit fill and its real timestamp',limit_time)

def partial_fees():
 f.BASE=1756425600
 rows=np.array([[f.BASE-1,1,100],[f.BASE+1,2,100],[f.BASE+3,3,100.5],[f.BASE+23,3,100],[f.BASE+50,4,95]],dtype=float)
 for mode in('S_ALL','S_111'):
  book,_,_=sim(rows,mode,queued=True,fee=.0005)
  assert len(book.journal[0]['partial_fills'])==1 and abs(book.cash-500-book.journal[0]['net'])<1e-8
  fee=book.fee;trade=book.journal[0];turn=trade['entry']*trade['quantity']+trade['exit']*trade['final_exit_quantity']+sum(x['execution_price']*x['quantity']for x in trade['partial_fills']);assert abs(book.stats['fees']-fee*turn)<1e-8
test('changed V2 partial prices/times retain full fee and cash reconciliation',partial_fees)

def core_replacement():
 f.BASE=1756425600
 rows=np.array([[f.BASE-1,1,100],[f.BASE+1,2,100],[f.BASE+13,3,99.7],[f.BASE+14,4,99.7],[f.BASE+23,3,100],[f.BASE+50,5,95]],dtype=float)
 x,_,_=sim(rows,'S_ALL',opened=True,priority=True,fee=.0005);y,_,_=sim(rows,'S_111',opened=True,priority=True,fee=.0005)
 assert x.journal[0]['reason']=='core_priority_exit'and y.journal[0]['reason']=='core_priority_exit'
 assert x.journal[0]['closed_us']!=y.journal[0]['closed_us']
 for book in(x,y):
  assert abs(book.cash-500-sum(t['net']for t in book.journal))<1e-8
  exit_event=next(v for v in book.events if v['event']=='priority_position_closed');newfill=next(v for v in book.events if v['event']=='limit_touch_proxy_fill'and v['signal_close_ms']==f.BASE*1000)
  assert newfill['raw_sequence']>exit_event['exit_raw_sequence']
test('anomaly can change CORE replacement timing; no same-event refilling; fees balanced',core_replacement)

def pool_guard():
 f.BASE=1756425600;leg=f.leg_for(1);book=o.instrument(b.pe.book('ETH',0.,leg,{},True),(f.BASE*1000000,(f.BASE+60)*1000000));reference=o.full_state(book)
 for field,value in [('cash',499.),('replacement',{'requested_us':1}),('raw_sequence',3)]:
  copybook=o.clone(book,leg);setattr(copybook,field,value);assert o.full_state(copybook)!=reference
 same=o.clone(book,leg);assert o.full_state(same)==reference
 # Pool future state, preserve different equity histories and their peaks.
 a0=np.array([500.,550.,510.]);a1=np.array([500.,520.,510.]);suffix=np.array([512.,515.])
 def dd(x):v=np.r_[500.,x];return float(np.max(100*(1-v/np.maximum.accumulate(v))))
 assert np.r_[a0,suffix][-1]==np.r_[a1,suffix][-1]and dd(np.r_[a0,suffix])!=dd(np.r_[a1,suffix])
 pos1=SimpleNamespace(stop=99.,partial_queue=[1]);pos2=SimpleNamespace(stop=99.,partial_queue=[]);same.position=pos1;other=o.clone(same,leg);other.position=pos2;assert o.full_state(same)!=o.full_state(other)
 assert o.digest(dict(book=reference,last_poll={'price':100}))!=o.digest(dict(book=reference,last_poll={'price':101}))
test('pooling checks full book, queue/request/poll state and preserves historical drawdown',pool_guard)

def source_unchanged():assert b.w.fingerprint()==b.PARENT_FP
test('all parent financial source hashes remain unchanged',source_unchanged)
def checkpoint_guard():
 runner=b.z.module('sensitivity_checkpoint_test_runner',OUT/'run.py')
 base=dict(runtime_fingerprint='source',data_fingerprint='data',start=0,end=120,keys=['ZERO_B'],next_time=60)
 runner.validate_checkpoint(base,'source','data',0,120,['ZERO_B'])
 for field,value in [('runtime_fingerprint','other'),('data_fingerprint','other'),('start',1),('end',180),('keys',['ZERO_D']),('next_time',61)]:
  changed=dict(base);changed[field]=value;rejects(lambda changed=changed:runner.validate_checkpoint(changed,'source','data',0,120,['ZERO_B']))
 leg=f.leg_for(1);book=b.pe.book('ETH',0.,leg,{},False);other=o.clone(book,leg);other.fee=.0005;assert runner.immutable_book(book)!=runner.immutable_book(other)
 other=o.clone(book,leg);other.core={123:1};assert runner.immutable_book(book)!=runner.immutable_book(other)
test('checkpoint source/data/window/fee/signal compatibility cannot be bypassed',checkpoint_guard)
b.dump(OUT/'tests.json',dict(passed=True,total=len(checks),checks=checks,synthetic_effect_tests_are_not_historical_results=True,real_full_day_views_and_integer_audit_tested=True));print('ALL',len(checks),'PASS')
