"""Small boundary checks for only the transplanted interventions; no annual replay."""
import common as c
import suite_engine as e
from catalog import SPECS
from types import SimpleNamespace as NS
np=c.np

def make(key,asset='ETH',atr=1.):
 n=30;leg=NS(first=0,up=np.full(n,6),down=np.zeros(n),histogram=np.ones(n),bars={i*900000:NS(c=99.)for i in range(n)})
 f=dict(time_ms=np.arange(n)*900000,lower=np.full(n,98.),upper=np.full(n,100.),close=np.full(n,99.),atr=np.full(n,atr),v=np.ones(n),reference=np.ones(n),multiplier=np.ones(n),valid=np.ones(n,dtype=bool))
 core={}if key=='ADAPT_CORE_LIGHT'else{900000:1};b=e.make(asset,leg,core,f,key,SPECS[key],{},dict(D_source='Q15',L_fixed=2.));b.audit_timestamp=910.;c.s.activate(b);b.place(910000,100,1,nearest_tick=True);return b

def main():
 rows=[]
 b=make('ATR_STOP',atr=2.);p=b.order.price;qty=b.order.qty;b.visit(p,910000,True,advance_ladder=False);assert abs(b.position.stop-p*.97)<1e-10 and p*qty*.03/500<=.06+1e-9;old=b.position.stop;b.update_ladder(p*1.02);assert b.position.stop>=old;assert isinstance(b,c.s.z.w.Dynamic);rows.append('ATR frozen3pct risk<=6pct, monotonic stop, real V2 MRO')
 b=make('CANCEL');cash=b.cash;b.before_minute(1800);assert b.order and b.cancel_request;b.before_minute(1859);assert b.order;b.before_minute(1860);assert not b.order and b.stats['stale_cancelled']==1 and b.cash==cash;e.cash_check(b);rows.append('Cancellation T+60 before matching, cash unchanged, count closes')
 for key,expected in [('CAP5',5),('TRAIL8',9)]:
  b=make(key);p=b.order.price;b.visit(p,910000,True,advance_ladder=False);b.update_ladder(p*1.10);assert b.position.rung==expected;assert isinstance(b,c.s.z.w.Dynamic)
 rows.append('cap5 and trail_from_8pct preserve V2 and original rung semantics')
 b=make('ADAPT_CORE_LIGHT','BTC');assert b.order_info['origin']=='EXTRA'and b.order.price*b.order.qty<=500+1e-9 and b.order.price*b.order.qty>490;rows.append('dual-asset supplement size1x; no ETH-only ratio leak')
 c.dump(c.OUT/'short_mechanics.json',dict(passed=rows,full_year_replays=0));print('Targeted mechanics PASS',len(rows))
if __name__=='__main__':main()
