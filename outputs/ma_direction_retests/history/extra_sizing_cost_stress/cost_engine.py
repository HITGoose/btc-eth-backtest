"""Only prespecified EXTRA quantity, per-book costs, and conservative fill proxy."""
import shared as s
import inspect,copy,math
b=s.b;r=s.r;pe=s.pe;np=s.np
class Book(pe.Book):
 def place(self,t,ref,side,**kw):
  signal=getattr(self,'submitting_signal',None)
  if signal is None:signal=round(t-10000)
  origin='CORE'if self.core.get(signal)==side else'EXTRA'
  scale=self.extra_ratio if self.asset=='ETH'and origin=='EXTRA'else 1.
  kw['size_multiplier']=kw.get('size_multiplier',1.)*scale
  super().place(t,ref,side,**kw)
  if self.order:self.order.submitted_effective_us=self.order_info['submitted_us'] if getattr(self,'submitting_signal',None) is not None else self.events[-1]['effective_submission_us']
  if self.order:self.order.submitted_raw_id=getattr(self,'current_raw_id',None)
  self.sizing_audit.append(dict(time_ms=t,signal_close_ms=signal,origin=origin,extra_ratio=scale,realized_balance=self.cash,target_notional=max(0.,self.cash)*3*scale,accepted=bool(self.order),actual_quantity=self.order.qty if self.order else 0.,actual_notional=self.order.qty*self.order.price if self.order else 0.,reason=None if self.order else 'MIN_NOTIONAL_OR_FUNDS'))
 def visit(self,price,t,at_open,**kw):
  if self.order and self.fill_mode=='F_THROUGH':
   tick=1./r.model.SCALES[self.asset]
   if self.order.side*(price-self.order.price)>-tick+1e-9:return
   now=round(self.audit_timestamp*1e6);submitted=getattr(self.order,'submitted_effective_us',round(self.order.time*1000))
   if now<submitted:return
   if now==submitted and getattr(self,'current_raw_id',None)==getattr(self.order,'submitted_raw_id',None):return
  n=len(self.journal);e0=len(self.events)
  super().visit(price,t,at_open,**kw)
  for ev in self.events[e0:]:
   if ev.get('event')=='partial_exit':self.slippage_cost+=abs(ev['trigger_print'])*ev['quantity']*self.slippage
  # Per-trade slippage is derived from actual raw/exit fills in reporting.
 def close(self,price,reason,t):
  qty=self.position.order.qty;side=self.position.order.side
  self.slippage_cost+=abs(price)*qty*self.slippage
  super().close(price,reason,t)
 def settle(self,event):
  assert event['complete'] and event['source']=='BINANCE_USDT_PERPETUAL_OFFICIAL'
  assert event['time_ms']>self.last_funding_ms
  self.last_funding_ms=event['time_ms']
  if not self.position:return
  pos=self.position;delta=-pos.order.side*pos.order.qty*event['mark_price']*event['rate']
  self.audit_timestamp=event['time_ms']/1000.;self.credit(delta);self.funding_total+=delta
  self.funding_events.append(dict(event,delta=delta,quantity=pos.order.qty,side=pos.order.side))
  # Funding belongs to the held trade, separate from execution PnL.
  pos.funding_pnl=getattr(pos,'funding_pnl',0.)+delta

def book(asset,fee,slip,leg,core,priority,extra_ratio=1.,fill='F_TOUCH'):
 x=pe.book(asset,fee,leg,core,priority);x.__class__=Book
 x.extra_ratio=extra_ratio;x.fill_mode=fill;x.slippage=slip;x.sizing_audit=[];x.slippage_cost=0.;x.funding_total=0.;x.funding_events=[];x.last_funding_ms=-1
 return x
# The parent optimized selector needs the same through threshold as Book.visit;
# otherwise it could discard the first qualifying later raw event.
market_source=inspect.getsource(pe.Market).replace('class Market(e.Market):','class Market(pe.Market):')
needle='(b.order.side*(rows[a:c,2]-b.order.price)<=0)'
assert market_source.count(needle)==1
market_source=market_source.replace(needle,"(b.order.side*(rows[a:c,2]-b.order.price)<=(-1./r.model.SCALES[b.asset]+1e-9 if b.fill_mode=='F_THROUGH' else 0))")
namespace=dict(pe.__dict__,pe=pe);exec(compile(market_source,'<fixed through selection; unchanged order/priority clock>','exec'),namespace);Market=namespace['Market']

def cash_check(x):
 pos=x.position;part=getattr(pos,'partial_net',0.)if pos else 0.;fee=x.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.
 assert abs(x.cash-500-sum(t['net']for t in x.journal)-part+fee-x.funding_total)<1e-7
 assert abs(x.cash-500-sum(t['delta']for t in x.cash_events))<1e-7
 assert x.stats['long']+x.stats['short']==len(x.journal)+bool(pos)
 assert x.stats['submitted']==x.stats['long']+x.stats['short']+x.stats['expired']+x.stats['priority_cancelled']+bool(x.order)
 x.invariant()
