"""Publish auditable derived evidence; large raw inputs/checkpoints remain immutable cloud caches."""
from pathlib import Path
import json,hashlib,zipfile
import shared as s
O=s.OUT;R=s.ROOT;np=s.np
ROOTS=[O/'runs',O/'sizing_only/runs',O/'funded/runs',O/'through_exact_clock/runs']

def hfile(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def zip_files(path,items,metadata=None):
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for file,name in sorted(items,key=lambda x:x[1]):z.write(file,name)
  if metadata is not None:z.writestr('MANIFEST.json',json.dumps(metadata,ensure_ascii=False,indent=2))
def main():
 cov=json.loads((O/'coverage_audit.json').read_text());assert cov['all_executable_cases_completed'],'Do not package a false complete result'
 A=O/'artifacts';A.mkdir(exist_ok=True);byperiod={};eq=[];primary=[];legacy=[]
 for root in ROOTS:
  for status in root.glob('*/*/*/status.json'):
   if not json.loads(status.read_text()).get('completed'):continue
   for p in status.parent.glob('results/*/*_result.json'):
    q=json.loads(p.read_text());islegacy=q['configuration']['fill']=='F_THROUGH'and root!=O/'through_exact_clock/runs'
    bucket=legacy if islegacy else primary;bucket.append(p)
    scene=q['scenario'];period=q['period'];tag='legacy_prototype_NOT_PRIMARY'if islegacy else'primary_or_explicit_nofunding_supplement'
    key=(period,scene)if period=='2025'and q['asset']=='ETH'else(period,'shared_BTC'if period=='2025'else'ALL')
    byperiod.setdefault(key,[]).append((p,tag+'/'+str(p.relative_to(R))))
    ep=p.with_name(p.name.replace('_result.json','_equity.npz'));arr=np.load(ep)['marks'];eq.append(dict(path=str(ep.relative_to(R)),period=period,asset=q['asset'],key=q['key'],scenario=scene,legacy_not_primary=islegacy,minute_rows=len(arr),dtype=str(arr.dtype),equity_array_SHA256=hashlib.sha256(arr.tobytes()).hexdigest(),ending_equity=float(arr[-1]),cloud_file_SHA256=hfile(ep),included_in_Git_artifact=False))
 s.dump(O/'equity_array_manifest.json',dict(arrays=eq,large_minute_arrays_retained_in_cloud=True,not_reconstructible_from_trade_ledgers_alone=True))
 for(period,scene),files in byperiod.items():
  zip_files(A/(f'ledgers_{period}_{scene}.zip'),files,dict(period=period,scenario=scene,source_commit='87f94d2e29b9832526e0aa35c0400c7ed7496805',source_market='BINANCE_USDT_PERPETUAL_ONLY',unverified_funding_old_periods=['2020','2021','2022','2023'],legacy_prototype_separate_never_primary=True,year2025_status='COMPLETED_WITH_DATA_ANOMALY',files=[dict(path=n,SHA256=hfile(p))for p,n in files]))
 shared=[]
 excluded={'publication_manifest.json','github_receipt.json','publication_prepare.log','artifact_index.json'}
 for p in O.iterdir():
  if p.is_file()and p.name not in excluded and p.suffix in('.py','.md','.csv','.json','.log'):shared.append((p,str(p.relative_to(R))))
 for scope in ['parent_validation','anomaly_validation']:
  for p in(O/scope).rglob('*'):
   if p.is_file()and p.suffix in('.py','.md','.csv','.json','.log')and'raw_audit'not in p.parts:shared.append((p,str(p.relative_to(R))))
 for root in ROOTS:
  for name in ['status.json','pooling.json','input_provenance.json','raw_sources.json','candle_tick_disagreements.json','failure.json','progress.json']:
   for p in root.rglob(name):
    if'whole'not in p.parts and'prefix'not in p.parts and'fork'not in p.parts and'suffix'not in p.parts:shared.append((p,str(p.relative_to(R))))
 zip_files(A/'audit_source_logs.zip',shared)
 funding=[(p,str(p.relative_to(R)))for p in(O/'funding_data').rglob('*.json')];zip_files(A/'official_funding_sources.zip',funding,dict(source='https://www.binance.com/fapi/v1/fundingRate',wire_checksums_not_available=True,recorded_response_SHA256=True,missing_marks_preserved=True))
 names=['SCENARIO_RECHECK.md','RERUN.md','DECISION_NOTES.md','CONCLUSION.md','report.md','mobile_annual.csv','advantage_retention.csv','funding_coverage.csv','configuration.json','coverage_audit.json','FUNDING.md','ISSUES.md']
 zip_files(A/'mobile_report.zip',[(O/n,n)for n in names if(O/n).exists()])
 files=[dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,SHA256=hfile(p))for p in sorted(A.glob('*.zip'))]
 s.dump(O/'artifact_index.json',dict(files=files,original_raw_inputs_not_uploaded=True,large_equity_arrays_not_uploaded=True,original_source_and_history_not_overwritten=True,primary_ledgers=len(primary),legacy_diagnostic_ledgers=len(legacy),full_matrix_strict_verified=False))
 print('PACKAGED',len(files),'ZIPs',sum(p.stat().st_size for p in A.glob('*.zip')),'bytes')
if __name__=='__main__':main()
