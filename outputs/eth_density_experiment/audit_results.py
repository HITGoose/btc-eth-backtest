from pathlib import Path
import json,csv,gzip,hashlib,math
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def read(p):return json.loads(p.read_text())
base=read(OUT/'frozen_config.json');assert base['base_commit']=='0ad7902161b91e7cf5538c5c06195c4a39086c24'
for name,digest in base['code'].items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,'Frozen execution source changed: '+name
for path in ('entry_tests.json','financial_tests.json','analysis_tests.json'):assert read(OUT/path)['passed']
assert read(OUT/'validation32/test_results.json')['failed']==0
assert read(OUT/'baseline/status.json')['passed']
for y in (2024,2025):
 for asset in ('BTC','ETH'):assert read(OUT/f'baseline/{y}/{asset}/regression.json')['passed']
for x in read(ROOT/'handoff/astra_20261114/github_sync_manifest.json')['files']:assert hashlib.sha256((ROOT/x['path']).read_text().encode()).hexdigest()==x['sha256'],x['path']
for x in read(ROOT/'outputs/retry_nov9_nov12/source_restore.json')['files']:
 b=(ROOT/x['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['sha']
a=read(OUT/'analysis.json');assert len(a['metrics'])==792
assert set(a['completed_periods'])==set(('2020','2021','2022','2023','2024','2026','NOV'))
assert a['partial_periods']==[{'period':'2025','verified_groups':['A','B']}]
assert len(a['failures'])==4 and all(x['period']=='2025'and x['group']in'CDEF'for x in a['failures'])
assert all(x['return_pct']is not None and math.isfinite(x['return_pct'])for x in a['metrics'])
assert all(abs(x['actual_USDT_delta'])<1e-7 for x in a['impact']if x['asset']=='BTC')
assert all(x['new_signals']>=0 and x['disappeared_signals']==0 for x in a['impact'])
with(OUT/'trade_attribution.csv').open(encoding='utf-8-sig',newline='')as f:trades=list(csv.DictReader(f))
for category in ('added','disappeared','changed','retained'):
 with(OUT/f'trades_{category}.csv').open(encoding='utf-8-sig',newline='')as f:subset=list(csv.DictReader(f))
 assert len(subset)==sum(x['category']==category.upper()for x in trades)
for case in a['impact']:
 if case['direction']!='ALL':continue
 subset=[x for x in trades if x['period']==case['period']and x['cost']==case['cost']and x['asset']==case['asset']and x['variant']==case['variant']]
 assert abs(sum(float(x['actual_USDT_delta'])for x in subset)-case['actual_USDT_delta'])<1e-7
 for x in subset:
  for side in ('old','new'):
   if x[side+'_status']:
    assert abs(float(x[side+'_normalized_1000'])-float(x[side+'_contribution'])/(float(x[side+'_entry'])*float(x[side+'_quantity']))*1000)<1e-7
counts={}
for f in OUT.glob('diagnostics_*.csv.gz'):
 with gzip.open(f,'rt',encoding='utf-8-sig',newline='')as stream:
  total=unknown=0
  for row in csv.DictReader(stream):
   total+=1
   if 'unverified'in f.name and row['execution_status']=='NOT_EVALUATED_DATA_BLOCK':
    assert row['has_position']=='NOT_EVALUATED'and row['realized_balance_at_check']=='NOT_EVALUATED';unknown+=1
   elif row['execution_status']=='UNEXPLAINED_NO_ORDER':raise AssertionError(str(f))
 counts[f.name]=dict(rows=total,unknown_occupancy=unknown)
recovery=read(OUT/'recovery_20250829_ETH/result.json');assert not recovery['usable']and recovery['daily_monthly_day_exact_match']and recovery['nonincreasing_ids']==3
result=dict(verification_passed=True,full_history_experiment_complete=False,source_commit=base['base_commit'],frozen_execution_hashes_match=True,original_source_preserved=True,tests=dict(original_synthetic=32,entry_chain=6,fee_checkpoint=8,analysis=8),baseline_four_regressions=True,verified_periods=a['completed_periods'],partial_periods=a['partial_periods'],blocked_groups_2025=['C','D','E','F'],missing_2019='UNVERIFIED',funding='NOT_INCLUDED',fee_rate='assumed .05pct per side; actual account NOT_VERIFIED',metrics_rows=len(a['metrics']),attribution_records=len(trades),diagnostics=counts,cash_and_terminal_position_reconciliation='asserted in worker/curve/compare for every verified path',raw_price_execution='official Binance UM raw-print touch proxy; not real fills')
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='diagnostics'},ensure_ascii=False))
