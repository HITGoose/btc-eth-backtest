"""Binance native closed candles for signals; official raw prints for execution.
No financial tick is rejected because it lies outside a native candle envelope.
Vectorization skips only prints proven unable to change the current book state.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import OrderedDict
import sys,inspect,json
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_dynamic_compare'))
import dynamic as x
p=x.p;r=x.r;d=x.d;e=x.e
OUT=Path(__file__).resolve().parent

class RawCache:
 def __init__(self,asset,native,folder):
  self.asset=asset;self.native=native;self.folder=folder;self.cache=OrderedDict();self.sources={};self.disagreements={}
  self.temp=folder/'temporary';self.temp.mkdir(exist_ok=True)
 def load(self,minute):
  day=datetime.fromtimestamp(minute,timezone.utc).strftime('%Y-%m-%d')
  if day in self.cache:self.cache.move_to_end(day);return self.cache[day]
  symbol=self.asset+'USDT';path=self.temp/f'{symbol}-trades-{day}.zip'
  meta=d.acquire(f'{d.BASE}/daily/trades/{symbol}/{symbol}-trades-{day}.zip',path)
  raw=d.read_zip(path,[0,1,4]);scale=1e6 if raw[0,2]>1e14 else 1000
  rows=np.column_stack((raw[:,2]/scale,raw[:,0],raw[:,1]));del raw
  if not np.all(np.isfinite(rows)) or np.any(rows[:,2]<=0):raise RuntimeError('Invalid raw print fields')
  id_steps=np.diff(rows[:,1]);id_jumps=int((id_steps!=1).sum())
  if np.any(id_steps<=0):raise RuntimeError('Duplicate or unordered raw trade IDs')
  time_reversals=int((np.diff(rows[:,0])<0).sum())
  if time_reversals:rows=rows[np.argsort(rows[:,0],kind='stable')]
  lower=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
  assert lower<=rows[0,0]<=rows[-1,0]<lower+86400
  used=rows[(rows[:,0]>=self.native.first)&(rows[:,0]<self.native.end)]
  index=((used[:,0]//60*60-self.native.first)//60).astype(int)
  lows=self.native.rows[index,2];highs=self.native.rows[index,1];bad=(used[:,2]<lows-1e-8)|(used[:,2]>highs+1e-8)
  if bad.any():
   ii=np.flatnonzero(bad)[:8]
   self.disagreements[day]=dict(records=int(bad.sum()),samples=[dict(time_beijing=r.local_s(float(used[i,0])),price=float(used[i,2]),native_low=float(lows[i]),native_high=float(highs[i])) for i in ii])
   d.dump(self.folder/'candle_tick_disagreements.json',self.disagreements)
  meta.update(asset=self.asset,date=day,rows=len(rows),raw_IDs_strictly_increasing=True,non_contiguous_ID_steps=id_jumps,timestamp_reversals_sorted=time_reversals,timestamp_scale=scale,disagreement_records=int(bad.sum()),source_market='BINANCE_USDT_PERPETUAL',price_rewritten=False)
  self.sources[day]=meta;d.dump(self.folder/'raw_sources.json',self.sources);path.unlink()
  self.cache[day]=rows
  while len(self.cache)>2:self.cache.popitem(last=False)
  if len(self.sources)%20==0:print(self.asset,'RAW_DAYS',len(self.sources),'LATEST',day,flush=True)
  return rows

class Market:
 def __init__(self,native,cache,book,optimized=True):self.native=native;self.cache=cache;self.book=book;self.market=self;self.close_discrepancies={};self.optimized=optimized
 def __getitem__(self,minute):
  values=list(self.native[minute]);rows=self.cache.load(minute);i=np.searchsorted(rows[:,0],minute+60,side='left')-1
  if i<0:
   rows=self.cache.load(minute-60);i=np.searchsorted(rows[:,0],minute+60,side='left')-1
   if i<0:raise RuntimeError('No actual latest print for mark')
  values[3]=float(rows[i,2]);return values
 def events(self,minute,phase,*,side=None,poll_seconds=5):
  rows=self.cache.load(minute);times=rows[:,0];lo,hi=np.searchsorted(times,[minute,minute+60]);previous=float(rows[lo-1,2]) if lo else float(self[minute-60][3])
  if not self.optimized:
   yield from p.polled_events(minute,phase,((float(t),float(price)) for t,_,price in rows[lo:hi]),previous,poll_seconds=poll_seconds);return
  # All same-time actual prints precede a quote poll. Include both submission
  # boundaries so the original exact+10s behavior is preserved.
  boundaries=[int(np.searchsorted(times,minute+10,side='left')),int(np.searchsorted(times,minute+10,side='right'))]
  cursor=int(lo);poll=minute+(phase-minute)%poll_seconds
  def wanted(start,end):
   if start>=end:return None
   candidates=[i for i in boundaries if start<=i<end]
   b=self.book
   if b.order:
    deadline=(b.order.time+r.model.ORDER_LIFETIME)/1000
    i=int(np.searchsorted(times,deadline,side='left'))
    if start<=i<end:candidates.append(i)
    mask=(times[start:end]>=b.order.time/1000)&(b.order.side*(rows[start:end,2]-b.order.price)<=0)
    hit=np.flatnonzero(mask)
    if len(hit):candidates.append(start+int(hit[0]))
   if b.position:
    if getattr(b.position,'partial_queue',[]):candidates.append(start)
    hit=np.flatnonzero(b.position.order.side*(rows[start:end,2]-b.position.stop)<=0)
    if len(hit):candidates.append(start+int(hit[0]))
   return min(candidates) if candidates else None
  while poll<minute+60:
   end=min(int(hi),int(np.searchsorted(times,poll,side='right')))
   while True:
    i=wanted(cursor,end)
    if i is None:break
    yield float(times[i]),float(rows[i,2]),False;cursor=i+1
   cursor=end
   quote=float(rows[end-1,2]) if end else previous
   yield float(poll),quote,True;poll+=poll_seconds
  while True:
   i=wanted(cursor,int(hi))
   if i is None:break
   yield float(times[i]),float(rows[i,2]),False;cursor=i+1

# Same original financial event loop; wake every minute with an order/position.
source=inspect.getsource(e.generator)
source=source.replace('    source=inspect.getsource(r.seconds.replay_asset)','    source=inspect.getsource(r.seconds.replay_asset)\n    source=source.replace("        expire(book, t)\\n", "        expire(book, t)\\n        check_trend(book, t)\\n")')
source=source.replace('    source=inspect.getsource(r.seconds.replay_asset)\n', '    source=inspect.getsource(r.seconds.replay_asset)\n    source=source.replace("events = list(market.events(t, poll_phase, side=order.side, poll_seconds=poll_seconds))", "events = market.events(t, poll_phase, side=order.side, poll_seconds=poll_seconds)")\n')
source=source.replace('original_can_move=r.seconds.has_price_event','original_can_move=lambda b,*args: bool(b.position or b.order)')
source=source.replace('namespace.update(Sleeve=', 'namespace.update(check_trend=x.check_trend,Sleeve=')
ns=dict(e.__dict__);ns['x']=x;exec(compile(source,'<original finances, all active minutes, causal raw-event selection>','exec'),ns);generator=ns['generator']

def new_book(asset,profile,leg):
 if profile=='CONTROL':b=p.new_book(asset,profile)
 else:
  b=x.Dynamic(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
  b.tranches=[(1.,.25),(0.,.25)];b.events=[];b.audit_timestamp=None;b.observing_event=False;b.profile=profile;b.boundary_probes=[]
 b.leg=leg;return b
