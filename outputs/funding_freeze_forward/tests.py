"""Pre-freeze causal, funding estimate, execution and tape integrity checks."""
from pathlib import Path
from types import SimpleNamespace
import json,tempfile,csv,copy,hashlib,pickle,dataclasses,math
import online as n
from live import Tape
O=n.O;checks=[]
def test(name,fn):fn();checks.append(dict(name=name,passed=True));print('PASS',name,flush=True)
sg=n.Signals(json.loads((O/'preflight/summary.json').read_text())['proposed_T0_ms'],O/'test_data');events=json.loads((O/'preflight/warm_responses.json').read_text())
for q in events:sg.add(q['asset'],q['data'],q['received_us'])
legs=sg.calculate();manifest=dict(T0_ms=sg.t0,run_id='SYNTHETIC_NOT_FORWARD')
def engine():return n.Engine(manifest,legs)
def estimates():
 for p in ['2020','2021','2022','2023']:
  for a in ['BTC','ETH']:
   q=json.loads((O/'funding_feeds'/p/a/'result.json').read_text());assert not q['missing']and q['strict_exact_status']=='UNVERIFIED'
   rows=list(zip(q['feeds']['OPEN'],q['feeds']['HIGH'],q['feeds']['LOW']))
   for op,hi,lo in rows:
    assert op['time_ms']==hi['time_ms']==lo['time_ms']and op['rate']==hi['rate']==lo['rate']
    assert 0<lo['mark_price']<=op['mark_price']<=hi['mark_price']
    if op['price_quality']=='EXACT_OFFICIAL_SETTLEMENT':assert op['mark_price']==hi['mark_price']==lo['mark_price']==float(op['official_rate_record']['markPrice'])
    else:assert op['mark_minute']['open_time_ms']<=op['time_ms']<=op['mark_minute']['close_time_ms']
test('all8 feeds: exact values preserved; approximate minute covers actual integer settlement',estimates)
for a in ['BTC','ETH']:
 for threshold in [.25,.30]:
  for extreme in [1.,1000000.]:
   def parity(a=a,threshold=threshold,extreme=extreme):
    path=O/'test_data'/(a+'_future_TEST_ONLY.csv');base=O/'test_data'/(a+'_closed.csv');last=legs[a]['last_close_ms']
    rows=list(csv.reader(base.open()));rows.append([last,extreme,extreme,extreme,extreme,1])
    with path.open('w',newline='')as f:csv.writer(f).writerows(rows)
    leg=n.r.model.build(path,legs[a]['leg'].start,last+900000)
    schedule,ctx=n.s.z.s.clone_schedule(threshold if a=='ETH'else .25)(a,leg,price_file=path,include_gate_confirmation=True,regime_thresholds=tuple(tuple(v)for v in json.loads(n.r.selected.FAST_WINDOW_REPORT.read_text())['cases'][n.r.selected.MODE]['er_windows_and_thresholds']),use_entry_crosses=False)
    policy=n.r.RegimeOverlay(**json.loads(n.r.selected.FAST_WINDOW_REPORT.read_text())['policy']);policy=dataclasses.replace(policy,range_squeeze_pct=threshold if a=='ETH'else .25)
    old=n.r.stacked_signals(schedule['baseline'],ctx,policy);actual=legs[a]['core'if threshold==.25 else'wide'];assert {t:v for t,v in old.items()if t<=last}==actual
    assert {t:v for t,v in ctx.items()if t<=last}==legs[a]['contexts'][threshold]
   test(f'closed-prefix parity and future independence {a}/{threshold}/{extreme}',parity)
def forming():
 before=len(sg.bars['BTC']);t=max(sg.bars['BTC'])+900000;sg.add('BTC',[[t,1,1000000,1,2,4,t+899999]],t*1000+1000);assert len(sg.bars['BTC'])==before
test('unclosed candle cannot enter indicators',forming)
def initial():
 e=engine();assert len(e.books)==16 and all(x.cash==500 and x.position is None and x.order is None for x in e.books.values());e.audit()
test('four versions two proxies two independently flat500 coin books',initial)
def event(ident=100,price='100',ms=None):return dict(type='TRADES',asset='BTC',received_us=sg.t0*1000-10,data=[dict(id=ident,time=sg.t0-1000 if ms is None else ms,price=price,qty='1')])
def dedup():
 e=engine();q=event();e.consume(q);e.consume(q);assert e.raw_count==1 and not e.halts and not any(x.order for x in e.books.values())
test('preT0 cannot trade and exact duplicate id is idempotent',dedup)
def conflict():
 e=engine();e.consume(event());e.consume(event(price='101'));assert e.halts[-1]['reason']=='RAW_ID_CONFLICT'
test('conflicting duplicate is rejected, not silently deduplicated',conflict)
def gap():
 e=engine();e.consume(event());e.consume(event(102));assert e.halts[-1]['reason']=='RAW_TRADE_ID_GAP'
test('raw ID gap halts financial path',gap)
def missingcost():
 e=engine();e.funding_due={'BTC':sg.t0+7456};e.advance((sg.t0+8000)*1000);assert e.halts[-1]['reason']=='EXACT_SETTLEMENT_COST_PENDING'
test('non-grid actual settlement deadline cannot be filled zero',missingcost)
def make(g='I100',side=1,fill='F_TOUCH',origin='EXTRA'):
 e=engine();x=e.books[(fill,g,'ETH')];t=sg.t0*1000+2000000;x.audit_timestamp=t/1e6;x.observed_clock_us=t;x.submitting_signal=sg.t0;x.core={sg.t0:side}if origin=='CORE'else{};n.s.activate(x);x.place(t/1000,2000,side,nearest_tick=True);x.submitting_signal=None;x.audit_timestamp=(t+1000000)/1e6;x.observed_clock_us=t+1000000;x.current_raw_id=123;x.visit(x.order.price,(t+1000000)//1000,True,advance_ladder=False);return x
def core_size():
 a=make('I100',origin='CORE');b=make('I25',origin='CORE');assert a.position.order.qty==b.position.order.qty
test('CORE sizing unchanged by EXTRA ratio',core_size)
for side in [1,-1]:
 def funding(side=side):
  x=make(side=side);before=x.cash;qty=x.position.order.qty;t=sg.t0+4000;x.settle(dict(time_ms=t,rate=.001,mark_price=2000.,complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL'));assert abs(x.cash-before+side*qty*2)<1e-8;x.audit_timestamp=(t+1000)/1000;x.close(2000,'test_exit',t+1000);n.F.cash_check(x)
 test('funding direction fee/slippage cash reconcile '+str(side),funding)
for g,expect in [('I100',True),('I25',False)]:
 def v2(g=g,expect=expect):
  x=make(g);t=(sg.t0//1000//900+1)*900;x.leg=SimpleNamespace(first=t*1000-1800000,up=[3,3],down=[3,3],histogram=[-1,-1],bars={t*1000-900000:SimpleNamespace(c=2000.)});before=len(x.events);n.F.original_check(x,t);requests=[e for e in x.events[before:]if e['event']=='adaptive_v2_request'];assert bool(requests)==expect
  if not expect:assert engine().no_v2_reason(x,t)=='REMAINING_REFERENCE_RISK_WITHIN_UNSCALED_3PCT_BUDGET'
  for r in requests:assert abs(r['budget']-x.cash*.03)<1e-9 and r['requested_quantity']<=x.position.initial_quantity*.25+1e-8
 test('unchanged3pct V2 budget; small EXTRA need not reduce '+g,v2)
def cashpickle():
 e=engine()
 with tempfile.TemporaryDirectory()as d:
  p=Path(d);e.save(p)
  with(p/'checkpoint.pkl').open('rb')as f:x=pickle.load(f)
  x.audit();assert x.manifest==e.manifest and x.last_clock==e.last_clock
 testdummy=0
test('checkpoint roundtrip code state and cash',cashpickle)
def tape():
 with tempfile.TemporaryDirectory()as d:
  t=Tape(Path(d));t.write(dict(type='TEST',received_us=1));t.write(dict(type='TEST',received_us=2));u=Tape(Path(d));assert u.seq==2 and u.prev==t.prev
test('compressed tape hash-chain verifies repeated restart',tape)
(O/'tests.json').write_text(json.dumps(dict(passed=True,total=len(checks),checks=checks,synthetic_or_prefix_checks_not_forward_performance=True),indent=2));print('ALL',len(checks))
