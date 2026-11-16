"""Two independent extensions of actual cost_engine.Book -> Dynamic -> V2."""
import portable
from pathlib import Path
import sys,math
import numpy as np
import pandas as pd
ROOT=portable.ROOT
sys.path.insert(0,str(ROOT/'outputs/extra_sizing_cost_stress'))
import replay as w
s=w.s;r=s.r;E=w.E
BASE_FINANCIAL_FP=s.fp()
ORIGINAL_V2=s.b.e.x.check_trend

def indicators(leg):
 bars=list(leg.bars.values());close=np.array([b.c for b in bars]);hi=np.array([b.h for b in bars]);lo=np.array([b.l for b in bars])
 lines=np.stack([r.model.sma(close,n)for n in (20,60,120)]+[r.model.ema(close,n)for n in (20,60,120)])
 tr=np.maximum(hi-lo,np.maximum(abs(hi-np.r_[close[0],close[:-1]]),abs(lo-np.r_[close[0],close[:-1]])))
 atr=np.full(len(tr),np.nan)
 if len(tr)>=96:
  atr[95]=np.mean(tr[:96])
  for i in range(96,len(tr)):atr[i]=(95*atr[i-1]+tr[i])/96
 v=atr/close;valid=np.flatnonzero(np.isfinite(v)&(v>0));ref=np.full(len(v),np.nan)
 med=pd.Series(v[valid]).rolling(2880,min_periods=2880).median().to_numpy()
 before=np.searchsorted(valid,np.arange(len(v)),side='left')-1;ok=before>=0;ref[ok]=med[before[ok]]
 multiplier=np.ones(len(v));good=np.isfinite(ref)&np.isfinite(v)&(v>0);multiplier[good]=np.clip(ref[good]/v[good],.5,1.)
 return dict(lower=lines.min(axis=0),upper=lines.max(axis=0),close=close,multiplier=multiplier,valid=good,atr=atr,v=v,reference=ref)

class VariantBook(E.Book):
 def place(self,t,ref,side,**kw):
  size_event=None
  signal=round(t-10000);i=(signal-self.leg.first)//900000-1
  if self.variant=='ER_V2_VOL_SIZE':
   valid=0<=i<len(self.features['valid'])and bool(self.features['valid'][i]);m=float(self.features['multiplier'][i])if valid else 1.
   kw['size_multiplier']=kw.get('size_multiplier',1.)*m
   size_event=dict(event='volatility_sizing',time_us=round(t*1000),signal_close_ms=signal,multiplier=m,fallback=not valid,base_target_notional=3*max(0.,self.cash),target_notional=3*max(0.,self.cash)*kw['size_multiplier'],ATR96=float(self.features['atr'][i])if valid else None,v=float(self.features['v'][i])if valid else None,v_ref=float(self.features['reference'][i])if valid else None);self.events.append(size_event)
  super().place(t,ref,side,**kw)
  if size_event is not None:
   size_event.update(accepted=bool(self.order),actual_quantity=self.order.qty if self.order else 0.,actual_notional=self.order.qty*self.order.price if self.order else 0.)
   self.sizing_audit[-1].update(volatility_multiplier=size_event['multiplier'],target_notional=size_event['target_notional'])
 def visit(self,price,t,at_open,**kw):
  pos=self.position
  request=getattr(pos,'failed_request',None)if pos else None
  super().visit(price,t,at_open,**kw) # original stop and queued V2 first
  if request and self.position is pos and round(self.audit_timestamp*1e6)>=request['eligible_us']:
   self.close(price,'failed_breakout_exit',t)
   self.events.append(dict(event='failed_exit_executed',time_us=round(self.audit_timestamp*1e6),signal_close_ms=self.order_info['signal_close_ms'],check_us=request['check_us']))

def check(book,t):
 ORIGINAL_V2(book,t)
 pos=book.position
 if getattr(book,'variant',None)!='ER_V2_FAIL_EXIT'or not pos or t%900 or getattr(pos,'failed_checked',False):return
 eligible=((int(pos.opened_us)+14400000000+899999999)//900000000)*900000000
 if t*1000000<eligible:return
 pos.failed_checked=True;i=(t*1000-book.leg.first)//900000-1
 assert i>=1
 f=book.features;inside=all(bool(f['lower'][j]<=f['close'][j]<=f['upper'][j])for j in (i-1,i))
 side=pos.order.side;entry=pos.order.price
 partial=sum(side*(x['execution_price']-entry)*x['quantity']for x in getattr(pos,'partial_fills',[]))
 floating=side*(f['close'][i]-entry)*pos.order.qty;gross=float(partial+floating)
 event=dict(event='failed_exit_check',time_us=t*1000000,opened_us=pos.opened_us,signal_close_ms=book.order_info['signal_close_ms'],two_closes_inside=inside,partial_gross=float(partial),remaining_gross=float(floating),whole_trade_gross=gross,requested=bool(inside and gross<0),eligible_exit_us=(t+60)*1000000)
 book.events.append(event)
 if event['requested']:pos.failed_request=dict(check_us=t*1000000,eligible_us=(t+60)*1000000)

s.b.e.x.check_trend=check
class Market(E.Market):
 def events(self,minute,*args,**kw):
  p=self.book.position;req=getattr(p,'failed_request',None)if p else None
  old=self.optimized
  if req and minute*1000000>=req['eligible_us']:self.optimized=False
  try:yield from super().events(minute,*args,**kw)
  except (OSError,ValueError) as error:raise RuntimeError('RAW_DATA_UNAVAILABLE_NO_OHLC_FALLBACK: '+repr(error)) from error
  finally:self.optimized=old

def make(asset,leg,core,features,variant):
 x=E.book(asset,0.,.0002,leg,core,False,1.,'F_TOUCH');x.__class__=VariantBook;x.variant=variant;x.features=features
 assert isinstance(x,s.z.w.Dynamic) and x.profile=='DYNAMIC' and x.exit_policy=='uncapped'
 return x
