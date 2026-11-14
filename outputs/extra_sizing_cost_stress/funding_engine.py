"""Official exact funding events enter the live book before same-time raw/poll events."""
from pathlib import Path
import json,hashlib
import shared as s
import cost_engine as base
r=s.r;pe=s.pe;np=s.np
FEED=None
class Book(base.Book):
 def apply_funding(self,time_ms):
  # Sequential actual settlement records, never rounded to an8-hour grid.
  while self.funding_cursor<len(self.funding_feed)and self.funding_feed[self.funding_cursor]['time_ms']<=time_ms:
   event=self.funding_feed[self.funding_cursor];self.funding_cursor+=1;self.settle(event)
 def close(self,price,reason,t):
  held_funding=getattr(self.position,'funding_pnl',0.)
  super().close(price,reason,t)
  trade=self.journal[-1];trade['execution_net_excluding_funding']=trade['net'];trade['funding_net_USDT']=held_funding;trade['net']+=held_funding
class Market(base.Market):
 def events(self,minute,*args,**kw):
  for stamp,price,poll in super().events(minute,*args,**kw):
   self.book.apply_funding(round(stamp*1000000)//1000)
   yield stamp,price,poll
  # A settlement after the last poll still belongs to this minute mark.
  self.book.apply_funding((minute+60)*1000-1)
original_check=s.b.e.x.check_trend

def funding_check(book,t):
 book.apply_funding(t*1000)
 original_check(book,t)
s.b.e.x.check_trend=funding_check

def configure_feed(period,asset):
 global FEED
 path=s.OUT/'funding_data'/period/asset/'result.json';data=json.loads(path.read_text());assert data['status']=='COMPLETE','official funding incomplete'
 assert not data['invalid_records']and data['preceding_record']and data['following_record']
 assert all(e['complete']and e['source']=='BINANCE_USDT_PERPETUAL_OFFICIAL'for e in data['events'])
 FEED=data['events'];return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()

def book(*args,**kw):
 x=base.book(*args,**kw);x.__class__=Book;assert FEED is not None
 x.funding_feed=FEED;x.funding_cursor=0;return x

def cash_check(x):
 pos=x.position;part=getattr(pos,'partial_net',0.)if pos else 0.;openfund=getattr(pos,'funding_pnl',0.)if pos else 0.;entryfee=x.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.
 assert abs(x.cash-500-sum(t['net']for t in x.journal)-part-openfund+entryfee)<1e-7
 assert abs(x.cash-500-sum(t['delta']for t in x.cash_events))<1e-7
 assert abs(x.funding_total-sum(e['delta']for e in x.funding_events))<1e-7
 assert x.stats['long']+x.stats['short']==len(x.journal)+bool(pos)
 assert x.stats['submitted']==x.stats['long']+x.stats['short']+x.stats['expired']+x.stats['priority_cancelled']+bool(x.order)
 x.invariant()
