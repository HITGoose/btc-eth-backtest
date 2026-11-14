from pathlib import Path
import importlib.util,sys,json
import numpy as np
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
sp=importlib.util.spec_from_file_location('density_analysis_worker',OUT/'worker.py');w=importlib.util.module_from_spec(sp);sys.modules[sp.name]=w;sp.loader.exec_module(w)
sp=importlib.util.spec_from_file_location('density_analysis_fixture',OUT/'validation32/tests.py');f=importlib.util.module_from_spec(sp);sp.loader.exec_module(f)
import analysis_helpers as h
checks=[]
for group in ('A','B'):
 for fee in (0.,.0005):
  for side in (1,-1):
   leg=f.leg_for(side)
   for j in (2,3,5,6):f.weak(leg,j,side)
   b=w.book('ETH',group,fee,leg);w.r.model.FEE=fee
   tape=f.synthetic_tape(0,side);market=w.e.Market(f.Native(),f.Cache(tape),b,True)
   signals={f.BASE*1000:side,(f.BASE+900)*1000:side}
   g=w.e.generator(b)('ETH',leg=leg,signals=signals,market=market,start=f.BASE*1000,end=(f.BASE+f.DURATION)*1000,poll_seconds=5,poll_phase=2,starting_cash=500.,leverage=3.,print_progress=False)
   for minute in range(f.BASE,f.BASE+f.DURATION,60):assert next(g)==minute
   try:next(g);raise AssertionError('overshot')
   except StopIteration as stop:result=stop.value
   assert b.position is None
   q=dict(asset='ETH',window=[w.r.local_s(f.BASE),w.r.local_s(f.BASE+f.DURATION)],trades=b.journal,events=b.events,place_attempts=b.place_attempts,cash_events=b.cash_events,fee=fee,cash=b.cash,ending_equity=b.cash,state_at_end=w.p.state(b),open_contribution=0.)
   marks=np.asarray(result['marks']);vec=h.curve(q,marks)
   assert np.allclose(vec['directions'][1]+vec['directions'][-1]-500,marks)
   assert abs(h.metrics(q['trades'],marks,500.,q['window'])['ending_equity']-b.cash)<1e-8
   features={stamp:dict(side=side,ER_regime='range',historical_minimum_bandwidth_pct=.2,aligned_lines=6,close_outside_six=True,MACD_direction_pass=True,current_bandwidth_pct=.3)for stamp in signals}
   decisions=h.diagnostic(q,features,signals,.25)
   assert decisions[(f.BASE+900)*1000]['execution_status']=='BLOCKED_POSITION'
   matched=h.compare(q,q,decisions);assert all(x['category']=='RETAINED'and x['actual_USDT_delta']==0 for x in matched)
   checks.append(dict(group=group,fee=fee,side=side,curve_balance=True,direction_reconciliation=True,occupancy=True,self_match=True))
(OUT/'analysis_tests.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2));print('PASS',len(checks),'curve/direction/occupancy/attribution cases')
