import sys,importlib.util,json,hashlib
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import worker as w
sig=w.sig;E=w.E;checks=[]
def ok(name,passed):assert passed,name;checks.append(dict(name=name,passed=True))
x=np.arange(3000,dtype=float);q=sig.past_quantile(x,.2);ok('2880 threshold excludes current',q[2880]==np.quantile(x[:2880],.2));changed=x.copy();changed[2880:]=1e9;z=sig.past_quantile(changed,.2);ok('current and future changes cannot alter current threshold',q[2880]==z[2880]);bad=x.copy();bad[500]=np.inf;ok('inf excluded, full2880 finite observations required',np.isnan(sig.past_quantile(bad,.2)[2880]))
raw=np.column_stack([np.arange(200),np.full(200,10.),np.full(200,11.),np.full(200,9.),np.full(200,10.),np.ones(200)]);tr,atr=sig.atr_wilder(raw);ok('Wilder96 initialized from first96 valid TR',np.isnan(atr[95])and atr[96]==2. and atr[97]==2.)
for asset,core_side,stop in [('BTC',1,False),('ETH',-1,False),('ETH',1,True)]:
 b=E.book(asset,0.,None,{1000000:core_side},True);E.activate(b);b.audit_timestamp=10.;b.place(10000,1000.,1);ok(asset+' EXTRA at1x without added capital',b.sizing_audit[-1]['leverage']==1. and b.cash==500.);entry=b.order.price;b.audit_timestamp=10.001;b.visit(entry,10001,True,advance_ladder=False);b.audit_timestamp=1010.;old_position=b.position;b.on_core(1000000,1000.,core_side);ok(asset+' CORE request preserves existing exposure until next print',b.position is old_position and b.order is None and b.replacement is not None)
 price=b.position.stop-1 if stop else 997. if core_side==1 else 1003.;b.audit_timestamp=1010.001;b.visit(price,1010001,True,advance_ladder=False);ok(asset+' exit event cannot also fill new CORE',b.position is None and b.order is not None and len(b.journal)==1);ok(asset+' CORE new order uses3x updated cash',b.sizing_audit[-1]['leverage']==3. and abs(b.sizing_audit[-1]['target_notional']-3*b.cash)<1e-9)
 if stop:ok('original hard stop has precedence over replacement exit',b.journal[-1]['reason']=='hard_stop')
 b.visit(b.order.price,1010001,True,advance_ladder=False);ok(asset+' distinct next event may fill CORE',b.position is not None and b.order is None and b.order_info['origin']=='CORE');E.cash_check(b);ok(asset+' CONTROL has no V2 events',not any('partial'in e['event']for e in b.events))
# One real cached prefix, covering all7 preset variants; no account rerun.
ref,data,start,end,first,sources=w.s.z.inputs('2020','BTC');cut=start+31*86400;p=sig.make('BTC',data,start,cut);saved=json.loads((O/'runs/train/2020/BTC/signals.json').read_text())['candidates']
for name in sig.SPECS:ok(name+' closed-bar signals unaffected by later years/candles',p['maps'][name]=={int(t):v for t,v in saved[name].items()if int(t)<cut*1000})
(O/'minimal_checks.json').write_text(json.dumps(dict(passed=True,checks=checks,count=len(checks),not_historical_performance_validation=True),indent=2));print('PASS',len(checks))
