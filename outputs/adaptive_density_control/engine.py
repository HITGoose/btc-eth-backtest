from pathlib import Path
import inspect,hashlib,json
import signals as sig
s=sig.s;r=s.r;np=s.np
# Retain the audited CORE-request event machinery, replacing only the monetary
# superclass with original CONTROL. Dynamic/V2 methods are never inherited.
source=inspect.getsource(s.pe.Book);assert source.count('class Book(w.Dynamic):')==1
source=source.replace('class Book(w.Dynamic):','class ControlPriority(w.Control):')
ns=dict(s.pe.__dict__);exec(compile(source,'<original priority event methods over CONTROL>','exec'),ns);ControlPriority=ns['ControlPriority']
class Book(ControlPriority):
 def capture_shadow(self,price):pass # no shadow accounts/tasks
 def place(self,t,ref,side,**kw):
  signal=getattr(self,'submitting_signal',None);signal=round(t-10000)if signal is None else signal;origin='CORE'if self.core.get(signal)==side else'EXTRA';scale=1/3 if self.hybrid and origin=='EXTRA'else 1.;kw['size_multiplier']=kw.get('size_multiplier',1.)*scale;super().place(t,ref,side,**kw)
  self.sizing_audit.append(dict(signal_close_ms=signal,time_ms=t,origin=origin,leverage=3*scale,realized_balance=self.cash,target_notional=max(0.,self.cash)*3*scale,accepted=bool(self.order),actual_notional=self.order.price*self.order.qty if self.order else 0.))
 def close(self,price,reason,t):
  self.slippage_cost+=abs(price)*self.position.order.qty*.0002;super().close(price,reason,t)
def book(asset,fee,leg,core,hybrid=False):
 x=Book(asset,'uncapped',cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[]);x.tranches=[];x.events=[];x.audit_timestamp=None;x.observing_event=False;x.profile='CONTROL';x.boundary_probes=[];x.leg=leg;x.fee=fee;x.slippage=.0002;x.cash_events=[];x.place_attempts=[];x.sizing_audit=[];x.slippage_cost=0.;x.hybrid=hybrid;x.configure(core,hybrid)
 assert isinstance(x,s.z.w.Control)and not isinstance(x,s.z.w.Dynamic)
 return x
Market=s.pe.Market
def activate(x):r.model.FEE=x.fee;r.model.SLIP=.0002
def cash_check(x):
 fee=x.fee*x.position.order.price*x.position.order.qty if x.position else 0.;assert abs(x.cash-500-sum(t['net']for t in x.journal)+fee)<1e-7;assert abs(x.cash-500-sum(t['delta']for t in x.cash_events))<1e-7;x.invariant();assert not any(e['event'].startswith('partial_')for e in x.events)
def generator(x):return s.pe.generator(x)
