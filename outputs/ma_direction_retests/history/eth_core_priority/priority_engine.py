"""Priority is an explicit clock event; raw prints and original stops retain order."""
import inspect,pickle,copy
import numpy as np
import strategy as z
w=z.w;e=z.e;r=z.r

class Book(w.Dynamic):
 def configure(self,core,priority):
  self.core=core;self.priority=priority;self.replacement=None;self.order_info={};self.decision_events=[];self.raw_sequence=0;self.shadow_snapshots=[]
 def invariant(self):
  assert not(self.order and self.position),'overlapping exposure'
  if self.replacement:assert not self.order,'priority lock must not add another order'
 def record(self,event,**kw):
  row=dict(event=event,time_us=round(self.audit_timestamp*1e6),**kw);self.events.append(row);return row
 def place(self,t,ref,side,**kw):
  if self.order or self.position or self.replacement:raise AssertionError('place while occupied/locked')
  signal=getattr(self,'submitting_signal',None)
  if signal is None:signal=round(t-10000)
  origin='CORE'if self.core.get(signal)==side else'EXTRA'
  super().place(t,ref,side,**kw)
  if self.order:
   self.order_info=dict(signal_close_ms=signal,origin=origin,submitted_us=round(t*1000),side=side)
   self.order.signal_close_ms=signal;self.order.origin=origin
   self.events[-1].update(self.order_info,time_us=round(t*1000),effective_submission_us=round(t*1000)if getattr(self,'submitting_signal',None)is not None else self.events[-1].get('effective_submission_us'))
  self.invariant()
 def close(self,price,reason,t):
  info=dict(self.order_info);super().close(price,reason,t)
  self.journal[-1].update({k:v for k,v in info.items()if k!='side'})
  self.events[-1].update(signal_close_ms=info['signal_close_ms'],origin=info['origin'])
 def visit(self,price,t,at_open,**kw):
  self.raw_sequence+=1
  request=self.replacement
  if request and round(self.audit_timestamp*1e6)>request['requested_us']:
   assert self.position and not self.order
   if self.position.order.side*(price-self.position.stop)<=0:
    super().visit(price,t,at_open,**kw)
    assert self.position is None
    self.record('priority_stop_first',core_signal_close_ms=request['signal_close_ms'])
   else:
    self.capture_shadow(price)
    self.close(price,'core_priority_exit',t)
    self.record('priority_position_closed',core_signal_close_ms=request['signal_close_ms'],extra_signal_close_ms=request['extra_signal_close_ms'],same_direction=request['same_direction'],closed_net=self.journal[-1]['net'],exit_raw_sequence=self.raw_sequence)
   self.replacement=None
   self.submit_core(request,round(self.audit_timestamp*1e6))
   self.invariant();return # The exit event is NEVER offered to the new order.
  old_pos=self.position;before=len(self.events)
  super().visit(price,t,at_open,**kw)
  for event in self.events[before:]:
   if event['event']=='limit_touch_proxy_fill':event.update(self.order_info,raw_sequence=self.raw_sequence)
  self.invariant()
 def capture_shadow(self,price):
  # Only the financial state of this one existing EXTRA is copied, without
  # account history or mutable strategy state. It never feeds live books.
  snapshot=dict(asset=self.asset,fee=self.fee,cash=self.cash,position=copy.deepcopy(self.position),order_info=dict(self.order_info),tranches=list(self.tranches),exit_us=round(self.audit_timestamp*1e6),exit_raw_sequence=self.raw_sequence,exit_print=price,exit_raw_id=getattr(self,'current_raw_id',None),request=dict(self.replacement))
  self.shadow_snapshots.append(snapshot)
 def submit_core(self,request,time_us):
  self.submitting_signal=request['signal_close_ms']
  self.record('priority_core_submit',core_signal_close_ms=request['signal_close_ms'],scheduled_us=request['signal_close_ms']*1000+10000000,actual_submission_us=time_us,reference_close=request['ref'],side=request['side'])
  try:self.place(time_us/1000,request['ref'],request['side'],nearest_tick=True)
  finally:self.submitting_signal=None
  self.record('priority_core_submit_result',core_signal_close_ms=request['signal_close_ms'],accepted=bool(self.order),expires_us=time_us+3600000000 if self.order else None)
 def on_core(self,signal,ref,side):
  self.invariant()
  if self.replacement:
   self.record('priority_duplicate_core_ignored',core_signal_close_ms=signal,locked_signal_close_ms=self.replacement['signal_close_ms']);return
  request=dict(signal_close_ms=signal,ref=ref,side=side,requested_us=signal*1000+10000000)
  if not self.position and not self.order:self.submit_core(request,request['requested_us']);return
  if self.order_info.get('origin')=='CORE':
   self.record('priority_core_already_occupies',core_signal_close_ms=signal);return
  if self.order:
   self.record('priority_cancel_extra_order',extra_signal_close_ms=self.order_info['signal_close_ms'],core_signal_close_ms=signal,extra_price=self.order.price)
   self.order=None;self.stats['priority_cancelled']+=1
   self.submit_core(request,request['requested_us']);return
  request.update(extra_signal_close_ms=self.order_info['signal_close_ms'],same_direction=self.position.order.side==side)
  self.replacement=request
  self.record('priority_replace_requested',core_signal_close_ms=signal,extra_signal_close_ms=request['extra_signal_close_ms'],same_direction=request['same_direction'],remaining_quantity=self.position.order.qty)
  self.invariant()

def book(asset,fee,leg,core,priority=False):
 b=Book(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
 b.tranches=[];b.events=[];b.audit_timestamp=None;b.observing_event=False;b.profile='DYNAMIC';b.boundary_probes=[];b.leg=leg;b.fee=fee;b.cash_events=[];b.place_attempts=[];b.configure(core,priority);return b

class Market(e.Market):
 def events(self,minute,phase,*,side=None,poll_seconds=5):
  b=self.book
  marker=bool(b.priority and b.core.get(minute*1000) and (b.replacement or ((b.order or b.position) and b.order_info.get('origin')=='EXTRA')))
  rows=self.cache.load(minute);times=rows[:,0];lo,hi=np.searchsorted(times,[minute,minute+60]);previous=float(rows[lo-1,2])if lo else float(self[minute-60][3]);cursor=int(lo)
  boundaries=[int(np.searchsorted(times,minute+10,side=x))for x in ('left','right')]
  def wanted(a,c):
   if a>=c:return None
   if not self.optimized:return a
   candidates=[i for i in boundaries if a<=i<c]
   if b.replacement:
    idx=max(a,int(np.searchsorted(times,b.replacement['requested_us']/1e6,side='right')))
    if idx<c:candidates.append(idx)
   if b.order:
    idx=int(np.searchsorted(times,(b.order.time+r.model.ORDER_LIFETIME)/1000,side='left'))
    if a<=idx<c:candidates.append(idx)
    hit=np.flatnonzero((times[a:c]>=b.order.time/1000)&(b.order.side*(rows[a:c,2]-b.order.price)<=0))
    if len(hit):candidates.append(a+int(hit[0]))
   if b.position:
    if getattr(b.position,'partial_queue',[]):candidates.append(a)
    hit=np.flatnonzero(b.position.order.side*(rows[a:c,2]-b.position.stop)<=0)
    if len(hit):candidates.append(a+int(hit[0]))
   return min(candidates)if candidates else None
  poll=minute+(phase-minute)%poll_seconds
  clocks=[(float(t),True)for t in range(int(poll),minute+60,poll_seconds)]
  if marker:clocks.append((minute+10.,'CORE'))
  clocks.sort(key=lambda x:x[0])
  for clock,kind in clocks+[(minute+60.,None)]:
   end=min(int(hi),int(np.searchsorted(times,clock,side='right'if kind is not None else'left')))
   while True:
    i=wanted(cursor,end)
    if i is None:break
    b.current_raw_id=int(rows[i,1]);yield float(times[i]),float(rows[i,2]),False;cursor=i+1
   cursor=end
   quote=float(rows[end-1,2])if end else previous
   if kind is not None:yield clock,quote,kind

def generator(b):
 if not b.priority:return e.generator(b)
 # Build from the exact frozen financial event loop, changing only the explicit
 # CORE clock hook, request observation, and cancellation accounting invariant.
 source=e.source
 # e.generator constructs replay source at runtime; replace the inner injection.
 needle='    source=inspect.getsource(r.seconds.replay_asset)\n'
 extra='''    source=source.replace("                expire(book, stamp)\\n", "                if poll == 'CORE':\\n                    book.on_core(t * 1000, leg.bars[t * 1000 - BAR].c, side)\\n                    pending_submission = False\\n                    continue\\n                expire(book, stamp)\\n")
    source=source.replace("if pending_submission and stamp > submit_at:", "if pending_submission and stamp > submit_at and poll != 'CORE':")
    source=source.replace('fills + book.stats["expired"] + bool(book.order)', 'fills + book.stats["expired"] + book.stats["priority_cancelled"] + bool(book.order)')
'''
 assert source.count(needle)==1
 source=source.replace(needle,needle+extra)
 namespace=dict(e.generator.__globals__);exec(compile(source,'<fixed priority hook; original finances>','exec'),namespace)
 return namespace['generator'](b)
