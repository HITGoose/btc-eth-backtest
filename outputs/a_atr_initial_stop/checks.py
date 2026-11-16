from pathlib import Path
import math,json
import runner as r
np=r.np;model=r.E.r.model
raw=np.zeros((300,6));raw[:,2]=102;raw[:,3]=98;raw[:,4]=100
tr,a=r.features.atr96(raw);assert np.isnan(a[:95]).all()and a[95]==4
raw[96,2]=106;tr,a=r.features.atr96(raw);assert a[96]==(95*4+8)/96
b=raw.copy();b[200:,2]=200;_,aa=r.features.atr96(b);assert np.allclose(a[:200],aa[:200],equal_nan=True)
assert r.features.parameters(.1,100)['d']==.01 and r.features.parameters(10,100)['d']==.03
assert r.features.parameters(float('nan'),100)==dict(ATR96=None,d=.02,L=3.,fallback=True)
for side in [1,-1]:
 for atr in [.1,1.,2.]:
  x=r.E.book('ETH',0.,None,{0:side},False);x.__class__=r.Book;x.exit_policy='fixed';x.signal_ATR={0:atr};x.audit_timestamp=10.;r.E.activate(x);x.place(10000,100,side,nearest_tick=True)
  o=x.order;p=o.atr_parameters;P=o.price;expected=min(3.,.06/p['d']);assert p['L']==expected and o.qty*P<=500*expected+1e-8
  # Fill exactly at limit; all observers and original fees remain in chain.
  x.audit_timestamp=20.;x.visit(P,20000,True,advance_ladder=False);assert x.position and abs(x.position.stop-P*(1-side*p['d']))<1e-10
  old=x.position.stop;quantity=x.position.order.qty
  x.audit_timestamp=22.;x.update_ladder(P*(1+side*.04));assert x.position.rung==3 and side*(x.position.stop-old)>=0
  old=x.position.stop;x.update_ladder(P*(1-side*.02));assert x.position.stop==old
  x.audit_timestamp=40.;x.visit(P*(1-side*.04),40000,True,advance_ladder=False);assert not x.position;r.E.cash_check(x)
  assert x.journal[-1]['quantity']==quantity and x.journal[-1]['atr_initial_parameters']==p
# Fill then stop on SAME event must use new closer stop, not original2%.
x=r.E.book('ETH',.0002,None,{0:1},False);x.__class__=r.Book;x.exit_policy='fixed';x.signal_ATR={0:.1};x.audit_timestamp=10.;r.E.activate(x);x.place(10000,100,1,nearest_tick=True);P=x.order.price;x.audit_timestamp=20.;x.visit(P*.985,20000,True,advance_ladder=False);assert not x.position and x.journal[-1]['reason']=='hard_stop';r.E.cash_check(x)
r.dump(Path(__file__).with_name('checks.json'),dict(ATR_seed_recursion=True,closed_data_prefix_invariant=True,fixed_parameters_and_fallback=True,quantity_and_planned_risk=True,initial_stop_before_same_event_stop_check=True,original_ladder_and_monotonicity=True,fee_and_cash_checks=True,MRO=[c.__module__+'.'+c.__name__ for c in r.Book.__mro__]))
print('CHECKS_PASSED')
