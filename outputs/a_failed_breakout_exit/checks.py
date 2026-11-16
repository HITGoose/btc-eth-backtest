from pathlib import Path
import importlib.util,sys,json
import numpy as np
O=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('failed_exit_test_hooks',O/'engine.py');h=importlib.util.module_from_spec(sp);sys.modules[sp.name]=h;sp.loader.exec_module(h)
assert h.due_second(0)==14400 and h.due_second(20000000)==15300 and h.due_second(900000000)==15300

def create(close=99.5):
 c=np.full(30,100.);c[15:17]=close;lo=np.full(30,99.);hi=np.full(30,101.);x=h.book('BTC',.0002,None,{0:1},c,lo,hi);h.E.activate(x);x.audit_timestamp=10.;x.place(10000,100/.998,1,nearest_tick=True);x.audit_timestamp=20.;x.visit(100.,20000,True,advance_ladder=False);assert x.position.opened_us==20000000 and x.position.fail_check_due_s==15300;return x
x=create();x.check_closed(14400);assert not x.exit_checks;x.check_closed(15300);assert len(x.exit_checks)==1 and x.fail_request['ready_s']==15360;x.check_closed(16200);assert len(x.exit_checks)==1
x.audit_timestamp=15320.;x.visit(99.6,15320000,True,advance_ladder=False);assert x.position
x.audit_timestamp=15360.;x.visit(99.4,15360000,True,advance_ladder=False);assert not x.position and len(x.journal)==1 and x.journal[0]['reason']=='failed_breakout_exit';assert abs(x.journal[0]['exit']-99.4*(1-.0002))<1e-10;h.E.cash_check(x)
y=create();y.check_closed(15300);y.audit_timestamp=15360.;y.visit(97.,15360000,True,advance_ladder=False);assert not y.position and y.journal[0]['reason']=='hard_stop'and len(y.journal)==1;assert y.exit_checks[0]['request_status']=='ORIGINAL_EXIT_FIRST';h.E.cash_check(y)
b=create();b.check_closed(15300);b.audit_timestamp=15322.;b.update_ladder(102.5);assert b.position.rung==1;b.audit_timestamp=15360.;b.visit(100.5,15360000,True,advance_ladder=False);assert b.journal[0]['reason']=='ladder_exit'and len(b.journal)==1 and b.exit_checks[0]['request_status']=='ORIGINAL_EXIT_FIRST';h.E.cash_check(b)
z=create(100.1);z.check_closed(15300);assert not z.exit_checks[0]['trigger'];z.closes[17:]=-200;z.check_closed(16200);assert len(z.exit_checks)==1 and z.fail_request is None
# Later bars cannot change a recorded closed-bar decision.
a=create();a.check_closed(15300);saved=dict(a.exit_checks[0]);a.closes[17:]=100000;assert a.exit_checks[0]==saved
result=dict(passed=True,synthetic_only=True,checks=['Due time uses actual fill and ceil to first eligible15m close','Both inclusive bands and strict negative gross; one check even when false','No exit at check close or before next minute','Original hard and ladder stops win on the same exit event; no duplicate close','Original slippage and fee cash reconciliation','Future bars cannot alter the frozen check']);(O/'checks.json').write_text(json.dumps(result,indent=2));print('PASS',len(result['checks']),'necessary checks')
