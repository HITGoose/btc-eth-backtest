import inspect,textwrap
import features
# parent is supplied by runner; no global original-code mutation.
def build(E):
 model=E.r.model
 source=textwrap.dedent(inspect.getsource(model.Sleeve.visit))
 needle='stop_price(self.asset, o.price, o.side, 0)';assert source.count(needle)==1
 source=source.replace(needle,'self.frozen_initial_stop(o)')
 fee_needle='fee = o.price * o.qty * FEE';assert source.count(fee_needle)==1
 source=source.replace(fee_needle,'fee = o.price * o.qty * self.fee') # per-book same fee; avoid captured global in copied function
 ns=dict(model.__dict__);exec(compile(source,'<original visit; frozen ATR initial stop only>','exec'),ns)
 class ATRSleeve(model.Sleeve):
  visit=ns['visit']
  def frozen_initial_stop(self,o):
   p=o.atr_parameters
   return model.stop_price(self.asset,o.price,o.side,0)if p['fallback']else o.price*(1-o.side*p['d'])
  def update_ladder(self,quote):
   pos=self.position
   if not pos:return
   old=pos.stop;model.Sleeve.update_ladder(self,quote)
   pos.stop=max(old,pos.stop)if pos.order.side==1 else min(old,pos.stop)
   assert pos.order.side*(pos.stop-old)>=-1e-10
 class Book(E.Book,ATRSleeve):
  def place(self,t,ref,side,**kw):
   stamp=getattr(self,'submitting_signal',None);stamp=round(t-10000)if stamp is None else stamp
   atr=self.signal_ATR[stamp];P=model.limit_price(self.asset,ref,side,nearest_tick=kw.get('nearest_tick',False));p=features.parameters(atr,P);kw['size_multiplier']=p['L']/3
   super().place(t,ref,side,**kw)
   a=self.sizing_audit[-1];a.update(ATR96=p['ATR96'],d=p['d'],target_leverage=p['L'],leverage=p['L'],target_notional=max(a['realized_balance'],0.)*p['L'],fallback=p['fallback'],planned_initial_stop=P*(1-side*p['d'])if not p['fallback']else model.stop_price(self.asset,P,side,0),limit_price=P,actual_quantity=self.order.qty if self.order else 0.,planned_price_risk_fraction=a['actual_notional']*p['d']/a['realized_balance']if a['accepted']and a['realized_balance']>0 else 0.)
   assert a['planned_price_risk_fraction']<=.06+1e-10
   if self.order:self.order.atr_parameters=dict(p,initial_stop=a['planned_initial_stop'],submission_cash=a['realized_balance']);assert self.order.price==P
  def close(self,price,reason,t):
   p=dict(self.position.order.atr_parameters);super().close(price,reason,t);self.journal[-1].update(atr_initial_parameters=p)
 return Book
