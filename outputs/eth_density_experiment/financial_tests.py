from pathlib import Path
import importlib.util,sys,pickle,json
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
sp=importlib.util.spec_from_file_location('density_worker_test',OUT/'worker.py');w=importlib.util.module_from_spec(sp);sys.modules[sp.name]=w;sp.loader.exec_module(w)
sp=importlib.util.spec_from_file_location('locked_synthetic_fixtures',OUT/'validation32/tests.py');f=importlib.util.module_from_spec(sp);sp.loader.exec_module(f)
checks=[]
for group in ('A','B'):
 for fee in (0.,.0005):
  for side in (1,-1):
   leg=f.leg_for(side);b=w.book('ETH',group,fee,leg);w.r.model.FEE=fee
   f.at(b,f.BASE+10);b.place((f.BASE+10)*1000,100.,side,nearest_tick=True);entry=b.order.price
   f.at(b,f.BASE+10.123);b.visit(entry,round((f.BASE+10.123)*1000),True,advance_ladder=False)
   if group=='B':
    i=(f.BASE+1800-leg.first//1000)//900-1
    f.weak(leg,i-1,side);f.weak(leg,i,side);f.at(b,f.BASE+1800);w.v.check(b,f.BASE+1800);assert b.position.partial_queue
   b.leg=None;copy=pickle.loads(pickle.dumps(b,protocol=5));b.leg=leg;copy.leg=leg
   for obj in (b,copy):
    f.at(obj,f.BASE+1800.123);obj.visit(entry+side*.1,round((f.BASE+1800.123)*1000),True,advance_ladder=False)
    f.at(obj,f.BASE+2000);obj.close(entry+side*2,'synthetic_close',round((f.BASE+2000)*1000))
    t=obj.journal[-1];assert abs(obj.cash-500-t['net'])<1e-8
    assert abs(sum(x['delta']for x in obj.cash_events)-t['net'])<1e-8
    assert all(x['side']==side for x in obj.cash_events)
    assert bool(t['entry_fee_journal_correction'])==(fee>0 and group=='B')
   assert b.cash==copy.cash and b.journal==copy.journal and b.events==copy.events and b.cash_events==copy.cash_events
   checks.append(dict(group=group,fee=fee,side=side,cash_ledger=True,checkpoint_roundtrip=True))
(OUT/'financial_tests.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2));print('PASS',len(checks),'fee/cash/checkpoint cases')
