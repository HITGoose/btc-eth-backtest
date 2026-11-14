from pathlib import Path
from dataclasses import asdict
import sys,json,argparse,traceback,hashlib,pickle,gzip
from datetime import datetime
import numpy as np
import strategy as s
v=s.v;e=s.e;r=s.r;p=s.p;d=s.d;OUT=s.OUT
class Ledger:
 def visit(self,*args,**kwargs):
  self._visit_side=self.position.order.side if self.position else self.order.side if self.order else None
  try:return super().visit(*args,**kwargs)
  finally:self._visit_side=None
 def credit(self,amount):
  super().credit(amount)
  if amount:self.cash_events.append(dict(time_us=round(self.audit_timestamp*1e6),delta=amount,cash=self.cash,side=self.position.order.side if self.position else self.order.side if self.order else getattr(self,"_visit_side",None)))
 def place(self,t,ref,side,**kw):
  before=dict(scheduled_us=t*1000,observed_check_us=round(self.audit_timestamp*1e6)if self.observing_event else t*1000,cash=self.cash,has_position=bool(self.position),has_order=bool(self.order),side=side)
  super().place(t,ref,side,**kw);before['accepted']=bool(self.order);self.place_attempts.append(before)
 def close(self,price,reason,t):
  pos=self.position;initial=getattr(pos,'initial_quantity',pos.order.qty);remaining=pos.order.qty;entry=pos.order.price;before=self.cash
  super().close(price,reason,t);row=self.journal[-1]
  # Preserve actual cash execution. Only correct the inherited partial-journal
  # allocation of initial entry fees in the independent nonzero-fee pressure run.
  correction=self.fee*entry*(initial-remaining)
  if correction:row['net']-=correction
  row.update(actual_final_cash_credit=self.cash-before,entry_fee_usdt=self.fee*entry*initial,entry_fee_journal_correction=correction)
class Control(Ledger,p.AuditSleeve):pass
class Dynamic(Ledger,v.BoundedAdaptive):pass

def book(asset,group,fee,leg):
 cls=Dynamic if s.GROUPS[group][1] else Control
 b=cls(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
 b.tranches=[];b.events=[];b.audit_timestamp=None;b.observing_event=False;b.profile='DYNAMIC'if s.GROUPS[group][1]else'CONTROL';b.boundary_probes=[];b.leg=leg;b.fee=fee;b.cash_events=[];b.place_attempts=[];return b

def run(period,asset):
 folder=OUT/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True)
 fingerprint=hashlib.sha256(Path(__file__).read_bytes()+Path(s.__file__).read_bytes()).hexdigest()
 if (folder/'status.json').exists()and json.loads((folder/'status.json').read_text()).get('completed'):
  assert json.loads((folder/'status.json').read_text()).get('code_fingerprint')==fingerprint,'Completed result belongs to different code; preserve it and choose a fresh run directory'
  return
 ref,data,start,end,first,sources=s.inputs(period,asset);d.BASE='https://data.binance.vision/data/futures/um';d.DATA=data;d.START=start;d.END=end;d.FIRST1=first
 leg,base,contexts,basecore,policy,pair=p.prepare(asset,data/f'{asset}_15m.csv',start,end)
 maps={};diag={k:value for k,value in s.diagnose(asset,data,leg,policy,pair).items() if start*1000<=k<end*1000}
 for threshold in (.25,.30,.35):
  _,maps[threshold],_,_,_=s.prepare(asset,data,start,end,threshold,leg,policy,pair)
 assert maps[.25]==base['ER']
 if asset=='BTC':assert maps[.25]==maps[.30]==maps[.35]
 s.csv_dump(folder/'conditions.csv.gz',list(diag.values()))
 s.dump(folder/'config.json',dict(base_commit=s.BASE_COMMIT,period=[r.local_s(start),r.local_s(end)],asset=asset,groups=s.GROUPS,fee_scenarios={'ZERO':0.,'ASSUMED_005_SIDE':.0005},fee_assumption='uniform hypothetical0.05pct per side, not user-account fee; full cash-path replay',funding='NOT_INCLUDED',entry_parameter_only='ETH rolling96 minimum bandwidth .25/.30/.35; candidates and range overlay both parameterized',BTC_threshold=.25,ER=pair,policy=asdict(policy),data=str(data),source='BINANCE_USDT_PERPETUAL_ONLY',diagnostic_candidates='all baseline candidates with historical bandwidth gate disabled; bottom-level >=5lines, outside-band and MACD; final6-line filter recorded',diagnostic_readonly=True))
 s.dump(folder/'input_provenance.json',dict(cached_candle_sources=sources,derived_file_hashes={str(data/f):hashlib.sha256((data/f).read_bytes()).hexdigest()for f in (f'{asset}_15m.csv',f'{asset}_1m.npy')},cached_source_checksums='official ZIP matches recorded acquisition evidence; cached derived files grid and current SHA verified, raw originals not retained',minute_first=first,start=start,end=end))
 groups=['A','B']if asset=='BTC'else list(s.GROUPS);books={};markets={};gens={};signals={};prefix={};resume=start
 checkpoint=folder/'checkpoint.pkl.gz';saved=None
 if checkpoint.exists():
  with gzip.open(checkpoint,'rb')as f:saved=pickle.load(f)
  assert saved['code_fingerprint']==fingerprint,'Checkpoint code changed; preserve checkpoint and use a fresh run directory'
  resume=saved['next_time'];print('RESUME',r.local_s(resume),flush=True)
 native=p.Canonical(asset);cache=e.RawCache(asset,native,folder)
 if (folder/'raw_sources.json').exists():cache.sources=json.loads((folder/'raw_sources.json').read_text())
 if (folder/'candle_tick_disagreements.json').exists():cache.disagreements=json.loads((folder/'candle_tick_disagreements.json').read_text())
 for cost,fee in [('ZERO',0.),('ASSUMED_005_SIDE',.0005)]:
  for group in groups:
   key=cost+'_'+group;b=saved['books'][key]if saved else book(asset,group,fee,leg);b.leg=leg;prefix[key]=saved['marks'][key]if saved else np.array([],dtype=float);books[key]=b;markets[key]=e.Market(native,cache,b,True);threshold=s.GROUPS[group][0]if asset=='ETH'else .25;signals[key]=maps[threshold]
   gens[key]=e.generator(b)(asset,leg=leg,signals=signals[key],market=markets[key],start=resume*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
 s.dump(folder/'signals.json',{str(k):value for k,value in maps.items()})
 print('START',period,asset,{str(k):len(x)for k,x in maps.items()},flush=True)
 for t in range(resume,end,60):
  for key,g in gens.items():r.model.FEE=books[key].fee;assert next(g)==t
  if t%86400==0:s.dump(folder/'progress.json',dict(time=r.local_s(t),books={k:dict(cash=b.cash,opens=b.stats['long']+b.stats['short'])for k,b in books.items()},raw_days=len(cache.sources)))
  boundary=datetime.fromtimestamp(t+60,r.TZ)
  if boundary.day==1 and boundary.hour==0 and boundary.minute==0:
   marks={k:np.r_[prefix[k],np.asarray(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
   for b in books.values():b.leg=None
   try:
    with gzip.open(folder/'checkpoint.tmp','wb',compresslevel=1)as f:pickle.dump(dict(code_fingerprint=fingerprint,next_time=t+60,books=books,marks=marks),f,protocol=5)
    (folder/'checkpoint.tmp').replace(checkpoint)
   finally:
    for b in books.values():b.leg=leg
   del marks
 for key,g in gens.items():
  b=books[key];r.model.FEE=b.fee
  try:next(g);raise RuntimeError('calendar overshot')
  except StopIteration as stop:result=stop.value
  assert not result['approximated_minutes'];mark=markets[key][end-60][3];pos=b.position
  openpart=getattr(pos,'partial_net',0.) if pos else 0.;openentryfee=b.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.
  assert abs(b.cash-500-sum(t['net']for t in b.journal)-openpart+openentryfee)<1e-7,(key,'cash ledger mismatch')
  assert abs(b.cash-500-sum(t['delta']for t in b.cash_events))<1e-7
  q=dict(asset=asset,period=period,window=[r.local_s(start),r.local_s(end)],key=key,fee=b.fee,ending_equity=b.equity(mark),cash=b.cash,starting_equity=500.,trades=b.journal,events=b.events,place_attempts=b.place_attempts,cash_events=b.cash_events,stats=dict(b.stats),opens=result['opens'],state_at_end=p.state(b),actual_raw_last_mark=mark,open_contribution=b.equity(mark)-b.cash+openpart-openentryfee,no_OHLC_fallback=True,source='BINANCE_USDT_PERPETUAL_ONLY')
  if pos:q['open_partial_state']={k:getattr(pos,k,None)for k in ('initial_quantity','partial_net','partial_fills','partial_queue','partial_stage')}
  s.dump(folder/f'{key}_result.json',q);np.save(folder/f'{key}_equity.npy',np.r_[prefix[key],np.asarray(result['marks'])])
  if key in ('ZERO_A','ZERO_B'):
   oldname='CONTROL'if key.endswith('A')else'DYNAMIC';old=json.loads((ref/asset/f'{oldname}_result.json').read_text());assert abs(q['ending_equity']-old['ending_equity'])<1e-7,(period,asset,key,'baseline equity differs')
   assert len(q['trades'])==len(old['trades'])
   for actual,expected in zip(q['trades'],old['trades']):
    for field in expected:assert actual[field]==expected[field],(period,asset,key,field)
  print('COMPLETE',period,asset,key,q['ending_equity'],flush=True)
 s.dump(folder/'status.json',dict(completed=True,base_regression=True,keys=list(books),code_fingerprint=fingerprint))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('period');a.add_argument('asset',choices=['BTC','ETH']);q=a.parse_args()
 try:run(q.period,q.asset)
 except Exception as error:
  f=OUT/'runs'/q.period/q.asset;f.mkdir(parents=True,exist_ok=True);s.dump(f/'failure.json',dict(error=repr(error),traceback=traceback.format_exc()));raise
