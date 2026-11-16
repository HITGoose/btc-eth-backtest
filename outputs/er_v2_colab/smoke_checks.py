"""Small deterministic boundary checks; not annual strategy evidence."""
from types import SimpleNamespace as NS
import json,time
from pathlib import Path
import variant_engine as v
np=v.np

def one(partial=False,stop=False,v2_only=False):
 leg=NS(first=0,up=np.full(30,6),down=np.zeros(30),histogram=np.ones(30),bars={i*900000:NS(c=99.)for i in range(30)})
 f=dict(time_ms=np.arange(30,dtype=np.int64)*900000,lower=np.full(30,98.),upper=np.full(30,100.),close=np.full(30,99.),multiplier=np.full(30,.5),valid=np.ones(30,dtype=bool),atr=np.ones(30),v=np.ones(30),reference=np.ones(30))
 b=v.make('ETH',leg,{-10000:1},f,'ER_V2_FAIL_EXIT');b.audit_timestamp=0.;v.s.activate(b);b.place(0,100.,1,nearest_tick=True);entry=b.order.price;b.visit(entry,0,True,advance_ladder=False);assert b.position.opened_us==0
 if partial:
  b.tranches.append((0.,.25));b.position.partial_queue=[1];b.audit_timestamp=1.;b.visit(110.,1000,True,advance_ladder=False)
 if v2_only:
  leg.up[:]=0;leg.histogram[:]=-1
  v.ORIGINAL_V2(b,14400);assert b.position.adaptive_v2_used and b.position.partial_queue
  event=next(e for e in b.events if e['event']=='adaptive_v2_request');assert event['requested_quantity']<=.25*b.position.initial_quantity+1e-9;return event
 v.check(b,14400);event=next(e for e in b.events if e['event']=='failed_exit_check')
 if partial:assert event['partial_gross']>0 and event['remaining_gross']<0 and not event['requested'];return event
 assert event['requested'];b.audit_timestamp=14459.9;b.visit(99.,14459900,True,advance_ladder=False);assert b.position
 b.audit_timestamp=14460.;b.visit(90. if stop else 99.,14460000,True,advance_ladder=False);assert not b.position
 reason=b.journal[-1]['reason'];assert(reason!='failed_breakout_exit')if stop else(reason=='failed_breakout_exit');v.E.cash_check(b)
 return dict(check=event,reason=reason)
def main():
 t=time.monotonic();out=dict(positive_V2_partial_not_ignored=one(True),next_minute_exit=one(),stop_priority=one(stop=True),original_V2_request=one(v2_only=True))
 out.update(checked_in_seconds=time.monotonic()-t,status='PASS',scope='synthetic mechanics, not historical profitability')
 import os
 p=Path(os.environ.get('BTC_OUTPUT_ROOT','/tmp'))/'smoke_mechanics.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2));print('Small mechanics checks PASS')
if __name__=='__main__':main()
