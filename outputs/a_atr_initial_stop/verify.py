from pathlib import Path
import json,csv,math
import runner as r
O=Path(__file__).resolve().parent;n=0;maxrisk=0.;maxres=0.;fallback=0;accepted=0
for year in range(2020,2027):
 for asset in ['BTC','ETH']:
  f=O/'runs'/str(year)/asset;assert json.loads((f/'status.json').read_text())['fingerprint']==r.fp();sigs=json.loads((f/'signals.json').read_text());assert sigs['A_BASE']==sigs['A_ATR_STOP'];diag={int(a['signal_close_ms']):a for a in csv.DictReader((f/'signal_ATR.csv').open(encoding='utf-8-sig'))}
  reuse=json.loads((f/'baseline_reuse.json').read_text())
  for a in reuse['sources']:assert r.sig.digest_file(r.R/a['source'])==a['SHA256']
  for fee in r.FEES:
   for g in ['A_BASE','A_ATR_STOP']:
    q=json.loads((f/f'{fee}_{g}_result.json').read_text());assert q['configuration']['exit_policy']=='fixed'and not q['V2']and q['starting_equity']==500
    assert not any(e['event'].startswith('partial_')or'stale_'in e['event']or'failed_breakout'in e['event']for e in q['events'])
    if g=='A_ATR_STOP':
     assert q['code_fingerprint']==r.fp();assert q['fee']==r.FEES[fee]
     for a in q['sizing_audit']:
      z=diag[int(a['signal_close_ms'])];assert abs(a['d']-float(z['d']))<1e-12 and abs(a['target_leverage']-float(z['L']))<1e-12 and abs(a['limit_price']-float(z['limit_price']))<1e-8
      if a['accepted']:
       accepted+=1;fallback+=a['fallback'];P=a['limit_price'];step=.0001 if asset=='BTC'else .01;expected=math.floor((max(0.,a['realized_balance']*a['target_leverage'])/P+1e-12)/step)*step;assert abs(expected-a['actual_quantity'])<1e-9;assert a['actual_notional']>=dict(BTC=100,ETH=5)[asset]-1e-8;maxrisk=max(maxrisk,a['planned_price_risk_fraction']);assert a['planned_price_risk_fraction']<=.06+1e-10
     for t in q['trades']:
      p=t['atr_initial_parameters'];side=1 if t['side']=='LONG'else-1;expected=r.E.r.model.stop_price(asset,t['entry'],side,0)if p['fallback']else t['entry']*(1-side*p['d']);assert abs(p['initial_stop']-expected)<1e-8;assert side*(t['stop_before_exit']-expected)>=-1e-8
      if t['reason']=='hard_stop':assert abs(t['stop_before_exit']-expected)<1e-8 and t['rung']==0
      assert t['opened_us']>=t['signal_close_ms']*1000+10000000
     p=q['state_at_end']['position']
     if p:assert p['order']['side']*(p['stop']-p['order']['atr_parameters']['initial_stop'])>=-1e-8
    n+=1
ck=list(csv.DictReader((O/'ledger_checks.csv').open(encoding='utf-8-sig')));assert n==56 and len(ck)==56
for a in ck:maxres=max(maxres,*(abs(float(a[k]))for k in ['cash_residual','equity_residual','cash_event_residual']))
assert maxres<1e-7
r.dump(O/'verification.json',dict(accounts=n,new_account_replays=28,reused_baselines=28,signals_unchanged=True,ATR_time_alignment_and_closed_bar_verified=True,original_source_and_baseline_SHAs_verified=True,quantities_floor_and_minimum_verified=True,max_submitted_planned_price_risk_fraction=maxrisk,all_frozen_initial_stops_verified=True,stops_never_relax=True,no_V2_no_early_exit_no_cancel=True,accepted_orders_both_fees=accepted,fallback_submitted_both_fees=fallback,max_ledger_residual=maxres,code_fingerprint=r.fp(),checks=json.loads((O/'checks.json').read_text())))
print('VERIFIED',n,'accounts','max_planned_risk',maxrisk,'residual',maxres)
