from pathlib import Path
import sys
R=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(R/'outputs/adaptive_density_floors'));import experiment as parent
E=parent.E;sig=parent.sig;s=parent.s;np=parent.np;original_expire=sig.r.seconds.expire

def expire_with_log(book,second):
 order=book.order;original_expire(book,second)
 if order is not None and book.order is None:book.on_expired(order,second)

class CancelBook(E.Book):
 def visit(self,price,t,at_open,**kw):
  order=self.order;before=self.stats['long']+self.stats['short'];super().visit(price,t,at_open,**kw)
  if order is not None and self.stats['long']+self.stats['short']>before:
   r=self.cancel_request
   if r and r['order']is order:
    self.cancel_requests[r['index']].update(result='FILLED_BEFORE_CANCEL',result_us=round(self.audit_timestamp*1e6),fill_price=float(price));self.cancel_request=None
 def on_expired(self,order,second):
  r=self.cancel_request
  if r and r['order']is order:
   self.cancel_requests[r['index']].update(result='EXPIRED_BEFORE_CANCEL',result_us=round(second*1e6),observed_us=round(self.audit_timestamp*1e6)if self.observing_event else round(second*1e6));self.cancel_request=None
 def before_minute(self,t):
  self.observing_event=False
  expire_with_log(self,t)
  r=self.cancel_request
  if r and t>=r['ready_s']:
   assert t==r['ready_s'];row=self.cancel_requests[r['index']]
   if self.order is r['order']:
    cash=self.cash;self.order=None;self.stats['stale_cancelled']+=1;row.update(result='CANCELLED',result_us=t*1000000,cash_before=cash,cash_after=self.cash);assert self.cash==cash;self.actual_cancel_times.append(t*1000000)
   else:raise AssertionError('Request lost its order without fill or expiry observation')
   self.cancel_request=None
  o=self.order
  if t%900 or o is None or o.time>=t*1000 or getattr(o,'stale_last_check_s',None)==t:return
  o.stale_last_check_s=t;i=(t*1000-self.band_first)//900000-1;assert i>=0 and i<len(self.closes);c=float(self.closes[i]);lo=float(self.band_low[i]);hi=float(self.band_high[i]);assert np.isfinite([c,lo,hi]).all();stale=bool(c<=hi if o.side==1 else c>=lo);row=dict(signal_close_ms=int(o.signal_close_ms),side=o.side,submitted_us=int(o.time*1000),check_ms=t*1000,bar_close_ms=self.band_first+(i+1)*900000,close=c,band_low=lo,band_high=hi,stale=stale);assert row['bar_close_ms']==t*1000;self.order_checks.append(row)
  if stale:
   assert self.cancel_request is None;request=dict(**row,ready_ms=(t+60)*1000,order_price=o.price,order_quantity=o.qty,result='PENDING');self.cancel_requests.append(request);self.cancel_request=dict(order=o,index=len(self.cancel_requests)-1,ready_s=t+60)

def book(asset,fee,leg,core,c,lo,hi):
 x=E.book(asset,fee,leg,core,False);x.__class__=CancelBook;x.exit_policy='fixed';x.cancel_request=None;x.cancel_requests=[];x.order_checks=[];x.actual_cancel_times=[];x.closes=c;x.band_low=lo;x.band_high=hi;x.band_first=leg.first if leg else 0;return x

def generator(book):
 raw=E.s.pe.e;source=raw.source;needle='    source=inspect.getsource(r.seconds.replay_asset)\n';assert source.count(needle)==1
 patch='    source=source.replace(\'fills + book.stats["expired"] + bool(book.order)\', \'fills + book.stats["expired"] + book.stats["stale_cancelled"] + bool(book.order)\')\n'
 source=source.replace(needle,needle+patch);assert source.count('namespace.update(')==1;source=source.replace('namespace.update(', 'namespace.update(expire=expire_with_log,');namespace=dict(raw.generator.__globals__,expire_with_log=expire_with_log);exec(compile(source,'<unchanged event loop; observe expiry and account stale cancellations>','exec'),namespace);return namespace['generator'](book)
