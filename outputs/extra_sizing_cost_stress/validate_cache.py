"""Fail before completed-cache reuse if source, native data, window or funding changed."""
from pathlib import Path
import json,hashlib
import shared as s
import funded_replay as f
import sizing_only_replay as q
import through_replay as t
O=s.OUT

def main():
 s.b.verify_parent();native={};checks=[]
 roots=[(O/'runs',s.fp()),(O/'funded/runs',f.fund_fp()),(O/'sizing_only/runs',q.sizing_fp()),(O/'through_exact_clock/runs',t.through_fp())]
 for root,expected_fp in roots:
  for status in root.glob('*/*/*/status.json'):
   saved=json.loads(status.read_text());assert saved['fp']==expected_fp,('completed source mismatch',str(status))
   period=status.parent.parent.parent.name;asset=status.parent.parent.name;key=(period,asset)
   if key not in native:
    _,data,start,end,_,_=s.z.inputs(period,asset);hashes={n:hashlib.file_digest((data/n).open('rb'),'sha256').hexdigest()for n in[asset+'_15m.csv',asset+'_1m.npy']};native[key]=(hashes,start,end)
   hashes,start,end=native[key];prov=status.parent/'input_provenance.json'
   if prov.exists():assert json.loads(prov.read_text())['native_SHA256']==hashes,('native mismatch',str(prov))
   for p in status.parent.glob('results/*/*_result.json'):
    result=json.loads(p.read_text());assert list(map(s.z.h.us,result['window']))==[start*1000000,end*1000000]
    if 'funding_data_SHA256'in result:
     source=O/'funding_data'/period/asset/'result.json';assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()==result['funding_data_SHA256']
   checks.append(dict(path=str(status.relative_to(O)),source_fp=expected_fp,native_and_window_current=True))
 proof=O/'BTC_reuse_proof.json'
 if proof.exists():
  for row in json.loads(proof.read_text())['reused']:
   _,data,_,_,_,_=s.z.inputs(row['period'],'BTC')
   for name,sha in row['current_native_SHA256'].items():assert hashlib.file_digest((data/name).open('rb'),'sha256').hexdigest()==sha
   assert hashlib.file_digest(open(row['source_result'],'rb'),'sha256').hexdigest()==row['source_result_SHA256']
 s.dump(O/'cache_validation.json',dict(passed=True,checks=checks,original_code_unchanged=True));print('CACHE_VALIDATED',len(checks))
if __name__=='__main__':main()
