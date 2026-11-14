from pathlib import Path
import zipfile,json,hashlib,shutil
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
if __name__=='__main__':
 artifacts=OUT/'artifacts';artifacts.mkdir(exist_ok=True)
 def pack(target,files):
  with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as archive:
   for path in files:archive.write(path,str(path.relative_to(OUT)))
  with zipfile.ZipFile(target)as archive:assert archive.testzip()is None
  return dict(path=str(target.relative_to(ROOT)),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
 ignored={'.npy','.pkl','.zip','.part'}
 files=[p for p in OUT.iterdir()if p.is_file()and p.suffix in('.csv','.gz','.json','.md','.py','.log')]
 # Explicit exclude own pickled execution state, native inputs and archives.
 files=[p for p in files if not p.name.endswith('.pkl.gz')and p.name not in('delivery_manifest.json','publication_manifest.json','github_receipt.json','analysis_smoke_2024_result.json','report_smoke_2024.md','publication_prepare.log')]
 reports=[p for p in files if p.suffix in('.md','.json')or p.name in('comparison_five_groups.csv','yearly_metrics.csv','monthly.csv','impact.csv','priority_summary.csv','cash_reconciliation.csv','concentration.csv')]
 receipts=[pack(artifacts/'REPORTS_SMALL.zip',reports)]
 receipts.append(pack(artifacts/'TRADE_ATTRIBUTION.zip',[p for p in files if p.name.startswith('trade')or p.name in('priority_events.csv','btc_filter_audit.csv','shadow_results.csv')]))
 for period in['2020','2021','2022','2023','2024','2025','2026','NOV']:
  ledgers=[]
  for scope in[OUT/'runs'/period,OUT/'shadows'/period]:
   if scope.exists():ledgers.extend(p for p in scope.rglob('*')if p.is_file()and (p.suffix in('.json','.log')or p.name.endswith(('.csv.gz','.json.gz')))and'development_run_before_shadow_snapshot'not in p.parts)
  if period=='2025':
   for p in(OUT/'cost_isolation').rglob('*')if(OUT/'cost_isolation').exists()else[]:
    if p.is_file()and(p.suffix in('.json','.log')or p.name.endswith(('.csv.gz','.json.gz'))):ledgers.append(p)
   for scope in[OUT/'data_evidence',OUT/'download_recovery']:
    if scope.exists():ledgers.extend(p for p in scope.rglob('*')if p.is_file()and p.suffix in('.json','.log'))
  receipts.append(pack(artifacts/f'period_{period}_ledgers.zip',ledgers))
 receipts.append(pack(artifacts/'ALL_DERIVED_RESULTS.zip',files+[p for p in artifacts.glob('period_*_ledgers.zip')]))
 (OUT/'delivery_manifest.json').write_text(json.dumps(receipts,indent=2)+'\n')
 print(json.dumps(receipts,indent=2))
