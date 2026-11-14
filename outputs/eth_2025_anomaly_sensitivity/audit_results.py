from pathlib import Path
import json,csv,gzip,hashlib
import numpy as np
import bridge as b
import observer as o
OUT=b.OUT

def rows(name):
 op=gzip.open if name.endswith('.gz')else open
 with op(OUT/name,'rt',encoding='utf-8-sig',newline='')as f:return list(csv.DictReader(f))
if __name__=='__main__':
 state=json.loads((OUT/'status.json').read_text());analysis=json.loads((OUT/'analysis.json').read_text());freeze=json.loads((OUT/'frozen_runtime.json').read_text());manifest=json.loads((OUT/'whitelist_manifest.json').read_text());pool=json.loads((OUT/'pooling.json').read_text())
 for name,sha in freeze['files'].items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==sha
 assert state['runtime_fingerprint']==freeze['runtime_fingerprint']and state['completed']and state['status']=='COMPLETED_WITH_DATA_ANOMALY'
 assert hashlib.file_digest(b.ARCHIVE.open('rb'),'sha256').hexdigest()==b.EXPECTED_SHA
 assert json.loads((OUT/'parent_tests.json').read_text())['passed']and json.loads((OUT/'tests.json').read_text())['passed']
 for group in ['D','G','H','I']:
  m=json.loads((OUT/f'compatibility_{group}.json').read_text());assert m['source_financial_fingerprint']==b.PARENT_FP and hashlib.sha256(Path(m['source_checkpoint']).read_bytes()).hexdigest()==m['source_checkpoint_SHA256']
  assert len(m['checks'])==2 and all(x['native_and_complete_signals_exact']and x['fee_sizing_exit_profile_exact']for x in m['checks'])
 checks=rows('cash_reconciliation.csv');assert len(checks)==90 and all(abs(float(x['equity_residual']))<1e-7 and abs(float(x['cash_residual']))<1e-7 for x in checks)
 assert len(rows('B_exact_comparison.csv'))==18 and all(x['trades_cash_equity_and_minute_curve_exact']=='True'for x in rows('B_exact_comparison.csv'))
 assert len(rows('annual_scenarios.csv'))==270
 assert not any(x['B_anomaly_day_financial_reads']=='True'for x in rows('archive_access_evidence.csv')if x['group']=='B')
 start=int(__import__('datetime').datetime.fromisoformat(json.loads((OUT/'configuration.json').read_text())['period'][0]).timestamp());prefix_n=(manifest['merge_second']-start)//60
 result_manifest=[]
 for r in pool['records']:
  curve=np.load(OUT/'results'/r['scenario']/(r['key']+'_equity.npy'));assert hashlib.sha256(curve[:prefix_n].tobytes()).hexdigest()==r['prefix_marks_SHA256']
  assert len(curve)==525600
 for file in sorted((OUT/'results').rglob('*')):
  if file.is_file():result_manifest.append(dict(path=str(file.relative_to(OUT)),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
 differences=rows('anomaly_event_differences.csv.gz');price_changes=[]
 for x in differences:
  old=json.loads(x['baseline_input'])if x['baseline_input']else None;new=json.loads(x['scenario_input'])if x['scenario_input']else None
  if old and new and old['price']!=new['price']:price_changes.append(dict(scenario=x['scenario'],key=x['key'],time_us=x['time_us'],time_Beijing=x['time_Beijing'],kind=x['kind'],baseline_price=old['price'],scenario_price=new['price'],baseline_latest_raw=json.dumps(old.get('latest_real_quote'),ensure_ascii=False),scenario_latest_raw=json.dumps(new.get('latest_real_quote'),ensure_ascii=False),financial_state_difference_observed=x['financial_state_difference_observed']))
 b.csv_dump(OUT/'poll_price_differences.csv.gz',price_changes)
 b.dump(OUT/'result_file_manifest.json',result_manifest)
 audit=dict(checks_passed=True,source_commit=b.BASE_COMMIT,runtime_fingerprint=freeze['runtime_fingerprint'],original_financial_fingerprint_unchanged=True,original_raw_SHA256_unchanged=True,parent_checkpoints_SHA256_unchanged=True,parent_tests=107,new_tests=24,ETH_scenarios_complete=90,annual_metric_rows=270,fee_cash_equity_checks=90,B_full_trade_cash_equity_minute_regressions=18,own_equity_prefixes_verified=90,pools_after_full_state_comparison=pool['groups_after'],strict_DGHI_status='UNVERIFIED',sensitivity_status='COMPLETED_WITH_DATA_ANOMALY',annual_metrics_identical=analysis['all_annual_primary_metrics_identical_across_scenarios'],all_minute_paths_identical=False,changed_trade_records=analysis['trade_differences'],changed_financial_event_records=analysis['financial_event_difference_rows'],changed_poll_prices=len(price_changes),price_change_scenarios=sorted({x['scenario']for x in price_changes}),first_price_change=min(x['time_Beijing']for x in price_changes)if price_changes else None,last_price_change=max(x['time_Beijing']for x in price_changes)if price_changes else None,changed_minute_equity_rows=analysis['minute_equity_difference_rows'],max_abs_equity_difference_USDT=analysis['max_abs_minute_equity_difference'],official_data_repaired=False,all_possible_data_errors_covered=False,old_seven_strict_intervals_not_combined=True)
 b.dump(OUT/'audit.json',audit);print(json.dumps(audit,ensure_ascii=False,indent=2))
