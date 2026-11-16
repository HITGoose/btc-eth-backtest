from pathlib import Path
import json,hashlib,math,csv
import runner
O=Path(__file__).resolve().parent;freeze=json.loads((O/'FREEZE.json').read_text());assert freeze['code_fingerprint']==runner.code_fp();allL=[]
for source in freeze['sources']:
 p=O/source['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==source['SHA256'];q=json.loads(p.read_text());allL.extend(a['target_leverage']for a in q['sizing_audit']if a['accepted'])
assert len(allL)==freeze['successful_submitted_orders']and math.fsum(allL)/len(allL)==freeze['L_fixed']
assert runner.sig.r.model.LADDER_CAP==5 and runner.sig.POLICY.pause_transition is True
assert runner.sig.POLICY.range_squeeze_pct==.25 and runner.sig.POLICY.range_entry_bandwidth_pct==.50
n=0
for year in range(2020,2027):
 for asset in ['BTC','ETH']:
  f=O/'runs'/str(year)/asset;assert(f/'status_final.json').exists()
  reuse=json.loads((f/'baseline_reuse.json').read_text())
  for a in reuse['sources']:assert runner.sig.digest_file(runner.R/a['source'])==a['SHA256']
  assert json.loads((f/'signals.json').read_text())['all_groups_identical']
  for fee in runner.FEES:
   for g in ['A_BASE','A_VOL','A_FIXED_LOW']:
    q=json.loads((f/f'{fee}_{g}_result.json').read_text());assert q['configuration']['exit_policy']=='fixed'and not q['V2']and q['starting_equity']==500
    assert not any(e['event'].startswith('partial_')or'stale_'in e['event']or'failed_breakout'in e['event']for e in q['events'])
    assert all(t['reason']not in ['failed_breakout_exit','core_priority_exit']for t in q['trades'])
    if g!='A_BASE':assert q['code_fingerprint']==runner.code_fp()
    if g=='A_FIXED_LOW':assert q['configuration']['fixed_L']==freeze['L_fixed']and q['configuration']['freeze_SHA256']==runner.sig.digest_file(O/'FREEZE.json')
    n+=1
ck=list(csv.DictReader((O/'ledger_checks.csv').open(encoding='utf-8-sig')));assert n==84 and len(ck)==84
for r in ck:assert max(abs(float(r[k]))for k in ['cash_residual','equity_residual','cash_event_residual'])<1e-7
runner.dump(O/'verification.json',dict(accounts=n,financial_runs_new=56,baseline_accounts_reused=28,freeze_verified=True,all_signals_identical=True,no_V2_no_early_exit_no_cancel=True,base_cap5_and_pause_transition_true=True,baseline_source_SHAs_unchanged=True,ledger_reconciled=True,rounding_checked_by_report=True,feature_checks=json.loads((O/'feature_checks.json').read_text()),code_fingerprint=runner.code_fp()))
matches=list(csv.DictReader((O/'trade_matching.csv').open(encoding='utf-8-sig')))
assert not any(r['category']in ['NEW','DISAPPEARED']for r in matches)
assert all(r['base_opened_us']==r['variant_opened_us']and r['base_closed_us']==r['variant_closed_us']for r in matches)
assert max(abs(float(r['r1000_difference']))for r in matches)<1e-10
z=json.loads((O/'verification.json').read_text());z.update(no_fill_set_or_time_changes=True,max_abs_matched_r1000_difference=max(abs(float(r['r1000_difference']))for r in matches));runner.dump(O/'verification.json',z)
print('VERIFIED',n,'accounts')
