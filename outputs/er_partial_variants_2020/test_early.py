import json
from pathlib import Path
import run_variants as v
checks=[]
for side in (1,-1):
 b=v.book('BTC','EARLY_2');b.audit_timestamp=10.;b.place(10000,100,side,nearest_tick=True);entry=b.order.price;b.visit(entry,10000,True,advance_ladder=False);qty=b.position.order.qty
 favorable=entry*(1+side*.011);high=max(entry,favorable);low=min(entry,favorable)
 assert not v.r.seconds.has_price_event(b,high,low,entry)
 assert v.reachable(b,high,low,entry)
 b.audit_timestamp=12.;b.update_ladder(favorable)
 assert b.position.rung==0 and b.position.partial_queue==[1]
 b.audit_timestamp=12.1;b.visit(entry*(1+side*.0105),12100,True,advance_ladder=False)
 assert b.stats['partial_exits']==1 and b.position.rung==0
 checks.append(dict(side=side,passed=True,test='1pct partial wakes tape without ladder activation, exits only after poll'))
Path(__file__).with_name('early_validation.json').write_text(json.dumps(dict(historical_validation=False,checks=checks),indent=2))
print('PASS early threshold cases',len(checks))
