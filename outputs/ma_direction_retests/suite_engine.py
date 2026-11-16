"""Original non-V2 CONTROL lineage, with isolated historical interventions."""
import common as c
import inspect,textwrap
v=c.v;s=c.s;E=v.E;r=s.r;np=c.np
ORIGINAL_GENERATOR=s.pe.generator;ORIGINAL_CASH_CHECK=E.cash_check
# Copy unchanged priority/cost/declared exit methods, replacing real inheritance.
# No V2 class is present anywhere in the actual book MRO.
source=inspect.getsource(s.pe.Book);assert source.count('class Book(w.Dynamic):')==1
ns=dict(s.pe.__dict__);exec(compile(source.replace('class Book(w.Dynamic):','class PriorityControl(w.Control):'),'<original priority methods, non-V2 Control base>','exec'),ns);PriorityControl=ns['PriorityControl']
source=inspect.getsource(E.Book);assert source.count('class Book(pe.Book):')==1
ns=dict(E.__dict__,PriorityControl=PriorityControl);exec(compile(source.replace('class Book(pe.Book):','class CostControl(PriorityControl):'),'<original cost methods, non-V2 priority>','exec'),ns);CostControl=ns['CostControl']
source=inspect.getsource(v.VariantBook);assert source.count('class VariantBook(E.Book):')==1
ns=dict(v.__dict__,CostControl=CostControl);exec(compile(source.replace('class VariantBook(E.Book):','class VariantControl(CostControl):'),'<same declared fail/size intervention, non-V2>','exec'),ns);VariantControl=ns['VariantControl']
source=inspect.getsource(v.check);source=source.replace(' ORIGINAL_V2(book,t)\n','')
assert 'ORIGINAL_V2(book,t)'not in source
ns=dict(v.__dict__);exec(compile(source,'<same one-shot gross failure check; no V2 hook>','exec'),ns);failure_check=ns['check']
atr_features=c.module('retest_historical_atr_features',c.HERE/'history/a_atr_initial_stop/features.py')
# Same narrow source substitution as original ATR experiment, under the V2 chain.
source=textwrap.dedent(inspect.getsource(r.model.Sleeve.visit));assert source.count('stop_price(self.asset, o.price, o.side, 0)')==1
source=source.replace('stop_price(self.asset, o.price, o.side, 0)','self.frozen_initial_stop(o)').replace('fee = o.price * o.qty * FEE','fee = o.price * o.qty * self.fee')
ns=dict(r.model.__dict__);exec(compile(source,'<original visit, frozen ATR initial stop only>','exec'),ns);ATR_VISIT=ns['visit']
class InitialStop(r.model.Sleeve):
 def visit(self,*a,**kw):
  return ATR_VISIT(self,*a,**kw)if self.suite_key=='ATR_STOP'else r.model.Sleeve.visit(self,*a,**kw)
 def frozen_initial_stop(self,o):
  p=o.atr_parameters;return r.model.stop_price(self.asset,o.price,o.side,0)if p['fallback']else o.price*(1-o.side*p['d'])
 def update_ladder(self,price):
  pos=self.position;old=pos.stop if pos else None;r.model.Sleeve.update_ladder(self,price)
  if self.suite_key=='ATR_STOP'and pos:pos.stop=max(old,pos.stop)if pos.order.side==1 else min(old,pos.stop)
class Book(VariantControl,InitialStop):
 def place(self,t,ref,side,**kw):
  signal=getattr(self,'submitting_signal',None);signal=round(t-10000)if signal is None else signal;i=(signal-self.leg.first)//900000-1
  assert self.features['time_ms'][i]==signal-900000
  cfg=self.suite_config;key=self.suite_key;origin='CORE'if self.core.get(signal)==side else'EXTRA';p=None
  if key=='FIXED_LOW':kw['size_multiplier']=kw.get('size_multiplier',1.)*self.fixed_L/3
  if key=='REGIME_SIZE':kw['size_multiplier']=kw.get('size_multiplier',1.)*self.regime_weights[signal]
  if key=='ATR_STOP':
   price=r.model.limit_price(self.asset,ref,side,nearest_tick=kw.get('nearest_tick',False));p=atr_features.parameters(self.features['atr'][i],price);kw['size_multiplier']=p['L']/3
  if self.asset=='BTC'and origin=='EXTRA':kw['size_multiplier']=kw.get('size_multiplier',1.)*self.extra_ratio
  super().place(t,ref,side,**kw)
  if self.order and p:self.order.atr_parameters=p;self.sizing_audit[-1].update(ATR96=p['ATR96'],d=p['d'],target_notional=max(0,self.cash)*p['L'],target_leverage=p['L'],fallback=p['fallback'])
  if self.order:
   factor=kw.get('size_multiplier',1.)*(self.extra_ratio if self.asset=='ETH'and origin=='EXTRA'else 1.)
   self.sizing_audit[-1].update(suite_key=key,effective_size_multiplier=factor,origin=origin)
   if key!='VOL_SIZE':self.sizing_audit[-1].update(target_notional=max(0.,self.cash)*3*factor,target_leverage=3*factor)
 def before_minute(self,t):
  if self.suite_key!='CANCEL':return
  req=self.cancel_request
  if req:
   if self.order is not req['order']:
    req['record']['result']='FILLED_OR_EXPIRED_BEFORE_CANCEL';self.cancel_request=None
   elif t>=req['ready']:
    self.order=None;self.stats['stale_cancelled']+=1;req['record'].update(result='CANCELLED',actual_cancel_us=t*1000000);self.cancel_request=None
  o=self.order
  if t%900 or o is None or o.time>=t*1000 or self.cancel_request:return
  i=(t*1000-self.leg.first)//900000-1;f=self.features;assert f['time_ms'][i]==t*1000-900000
  stale=f['close'][i]<=f['upper'][i]if o.side==1 else f['close'][i]>=f['lower'][i]
  row=dict(event='stale_order_check',time_us=t*1000000,signal_close_ms=o.signal_close_ms,stale=bool(stale),planned_cancel_us=(t+60)*1000000,result='PENDING'if stale else'KEEP')
  self.events.append(row)
  if stale:self.cancel_request=dict(order=o,ready=t+60,record=row)

def check(book,t):
 if isinstance(book,Book):book.before_minute(t)
 failure_check(book,t) # one-shot declared check; no V2 or automatic partial exits
s.b.e.x.check_trend=check

def generator(book):
 if getattr(book,'suite_key',None)!='CANCEL':return ORIGINAL_GENERATOR(book)
 raw=s.pe.e;source=raw.source;needle='    source=inspect.getsource(r.seconds.replay_asset)\n'
 patch='    source=source.replace(\'fills + book.stats["expired"] + bool(book.order)\', \'fills + book.stats["expired"] + book.stats["stale_cancelled"] + bool(book.order)\')\n'
 assert source.count(needle)==1;source=source.replace(needle,needle+patch);ns=dict(raw.generator.__globals__);exec(compile(source,'<original loop; real cancellation count only>','exec'),ns);return ns['generator'](book)
def cash_check(x):
 if getattr(x,'suite_key',None)!='CANCEL':return ORIGINAL_CASH_CHECK(x)
 pos=x.position;part=getattr(pos,'partial_net',0.)if pos else 0.
 assert abs(x.cash-500-sum(t['net']for t in x.journal)-part)<1e-7
 assert abs(x.cash-500-sum(t['delta']for t in x.cash_events))<1e-7
 fills=x.stats['long']+x.stats['short'];assert fills==len(x.journal)+bool(pos)
 assert x.stats['submitted']==fills+x.stats['expired']+x.stats['priority_cancelled']+x.stats['stale_cancelled']+bool(x.order);x.invariant()
def make(asset,leg,core,features,key,cfg,parameters,freeze):
 x=Book(asset,cfg.get('exit_policy','uncapped'),cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
 x.tranches=[];x.events=[];x.audit_timestamp=None;x.observing_event=False;x.profile='CONTROL';x.boundary_probes=[];x.leg=leg;x.fee=0.;x.cash_events=[];x.place_attempts=[];x.configure(core,cfg.get('priority',False))
 x.extra_ratio=cfg.get('extra_ratio',1.);x.fill_mode='F_TOUCH';x.slippage=.0002;x.sizing_audit=[];x.slippage_cost=0.;x.funding_total=0.;x.funding_events=[];x.last_funding_ms=-1
 x.variant='ER_V2_FAIL_EXIT'if key=='FAIL_EXIT'else'ER_V2_VOL_SIZE'if key=='VOL_SIZE'else key
 x.features=features;x.suite_key=key;x.suite_config=cfg;x.fixed_L=freeze.get('L_fixed');x.regime_weights=parameters.get('regime_weights',{});x.cancel_request=None
 assert isinstance(x,s.z.w.Control)and not isinstance(x,s.z.w.Dynamic)
 assert not any(cls.__name__ in ['BoundedAdaptive','VariantSleeve','Dynamic']for cls in type(x).__mro__)
 return x
