from pathlib import Path
import importlib.util,sys,json
import numpy as np
O=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('stale_cancel_test_hooks',O/'cancel_engine.py');h=importlib.util.module_from_spec(sp);sys.modules[sp.name]=h;sp.loader.exec_module(h)
def create(side=1,close=101.):
 c=np.full(12,close);lo=np.full(12,99.);hi=np.full(12,101.);x=h.book('BTC',.0002,None,{0:side,3600000:side},c,lo,hi);h.E.activate(x);x.audit_timestamp=10.;x.place(10000,100/(1-side*.002),side,nearest_tick=True);assert x.order.price==100.;return x
x=create();x.before_minute(0);assert not x.order_checks;x.before_minute(900);assert x.cancel_requests[0]['ready_ms']==960000;x.before_minute(900);assert len(x.order_checks)==1
x.before_minute(960);assert x.order is None and x.stats['stale_cancelled']==1 and x.cash==500;x.audit_timestamp=960.;x.visit(100,960000,True,advance_ladder=False);assert x.position is None and x.stats['long']==0;h.E.cash_check(x)
y=create();y.before_minute(900);y.audit_timestamp=940.;y.visit(100,940000,True,advance_ladder=False);assert y.position and y.cancel_requests[0]['result']=='FILLED_BEFORE_CANCEL';y.before_minute(960);assert y.position and y.stats['stale_cancelled']==0 and not y.journal;h.E.cash_check(y)
z=create();z.before_minute(3600);h.expire_with_log(z,3610);assert z.cancel_requests[0]['result']=='EXPIRED_BEFORE_CANCEL'and z.stats['expired']==1;z.audit_timestamp=3612.;z.place(3610000,100/.998,1,nearest_tick=True);new=z.order;z.before_minute(3660);assert z.order is new and z.stats['stale_cancelled']==0;h.E.cash_check(z)
for side,close,expected in [(1,101,True),(1,98,True),(1,102,False),(-1,99,True),(-1,102,True),(-1,98,False)]:
 b=create(side,close);b.before_minute(900);assert b.order_checks[0]['stale']==expected
r=dict(passed=True,synthetic_only=True,checks=['Only new closed15m strictly after submission; no duplicate check','T+60 cancel precedes same-minute fill; cash unchanged and no rehang','Fill before cancel invalidates request and preserves position','Original expiry before cancel; stale request cannot cancel new original-signal order','Long/short inclusive boundary and crossing entire band']);(O/'checks.json').write_text(json.dumps(r,indent=2));print('PASS',len(r['checks']),'necessary checks')
