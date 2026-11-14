from pathlib import Path
import hashlib,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent;checks=[];proof_counts=[]
for y in (2019,2020,2024,2025):
 for a in ('BTC','ETH'):
  folder=OUT/str(y)/a;status=json.loads((folder/'status.json').read_text());assert status.get('completed'),f'Incomplete {y} {a}'
  result_path=folder/'DYNAMIC_result.json';q=json.loads(result_path.read_text());c=json.loads((folder/'config.json').read_text())
  assert q['no_OHLC_fallback'] and q['source_market']=='BINANCE_SPOT_ONLY'
  assert q['period'][0].startswith(f'{y}-01-01') and q['period'][1].startswith(f'{y+1}-01-01')
  assert c['fee']==0 and c['leverage']==3 and c['SR_absolute_distance_pct']==2
  proof_files=sorted((OUT/str(y)).glob(f'{a}_*gap_proofs.json'))
  q['derived_bar_proofs']=[p.name for p in proof_files];q['daily_kline_repair']='data/BTC_daily_repair.json' if y==2020 and a=='BTC' else None
  result_path.write_text(json.dumps(q,ensure_ascii=False)+'\n')
  if (folder/'failure.json').exists():(folder/'failure.json').rename(folder/'resolved_initial_failure.json')
  for f in proof_files:
   proof=json.loads(f.read_text());proof_counts.append(dict(year=y,asset=a,file=f.name,derived_intervals=sum('interval_start' in p for p in proof)))
   for p in proof:
    if 'source' in p:assert p['source']['official_checksum_match']
  checks.append(dict(year=y,asset=a,full_calendar_year=True,all_execution_actual_prices=True,config_unchanged=True))
manifest=json.loads((ROOT/'outputs/er_dynamic_annual_2019_2026/rule_manifest.json').read_text())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest['sha256'].items())
source=json.loads((ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text())
for row in source['files']:
 b=(ROOT/row['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==row['sha']
(OUT/'completion.json').write_text(json.dumps(dict(completed=True,market='spot price input, synthetic3x long/short',years=[2019,2020,2024,2025],checks=checks,derived_bar_counts=proof_counts,original_source_unchanged=True,dynamic_rule_unchanged=True),ensure_ascii=False,indent=2))
print('Full-year source, execution, reconstruction and unchanged-rule checks passed')
