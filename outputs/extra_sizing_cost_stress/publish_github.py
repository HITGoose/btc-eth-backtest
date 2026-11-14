"""Authenticated gh REST publication; only this independent branch, never main.
Requires the prepared /tmp/cost_publication snapshot (no raw input caches uploaded).
"""
from pathlib import Path
import concurrent.futures,subprocess,tempfile,json,hashlib,base64,datetime
R=Path('/workspace/btc-eth-backtest');O=R/'outputs/extra_sizing_cost_stress';P=Path('/tmp/cost_publication')
REPO='HITGoose/btc-eth-backtest';BRANCH='codex/extra-sizing-cost-stress-20261114';EXPECTED='602476b77c1b137c79fe492cc4a422c916a7ede7';BASE_TREE='cfa19ec10335c9522ac8882c37162f2324a68fae';SOURCE='87f94d2e29b9832526e0aa35c0400c7ed7496805'

def api(path,method='GET',body=None):
 args=['gh','api','repos/'+REPO+'/'+path,'--method',method]
 with tempfile.TemporaryDirectory(prefix='cost-git-api-')as td:
  if body is not None:
   p=Path(td)/'request.json';p.write_text(json.dumps(body));args+=['--input',str(p)]
  p=subprocess.run(args,capture_output=True,text=True,timeout=180)
  if p.returncode:raise RuntimeError(path+': '+p.stderr[:1500])
  return json.loads(p.stdout)
def blob_sha(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def main():
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==EXPECTED,'Inspect new head; do not force'
 main_before=api('git/ref/heads/main')['object']['sha'];source=api('git/trees/'+SOURCE+'?recursive=1');assert not source['truncated']
 files=json.loads((P/'manifest.json').read_text());inline=json.loads((P/'inline.json').read_text());large=json.loads((P/'blobs.json').read_text())
 for f in files:
  raw=(R/f['path']).read_bytes();assert blob_sha(raw)==f['git_blob_SHA']and hashlib.sha256(raw).hexdigest()==f['SHA256'],'Publication snapshot changed: '+f['path']
 events=[]
 def upload(f):
  raw=(P/(f['sha']+'.b64')).read_text();q=api('git/blobs','POST',dict(content=raw,encoding='base64'));assert q['sha']==f['sha'];return dict(path=f['path'],sha=q['sha'],bytes=f['bytes'])
 with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
  for e in pool.map(upload,large):
   events.append(e);print('BLOB_OK',e['path'],e['bytes'],flush=True);(O/'publication_transfers.json').write_text(json.dumps(events,indent=2))
 manifest=dict(source_commit=SOURCE,branch=BRANCH,parent_commit=EXPECTED,files=files,raw_market_inputs_in_Git=False,financial_results_frozen=True,publication_time_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
 manifest_raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode();(O/'publication_manifest.json').write_bytes(manifest_raw)
 elements=inline+[dict(path=f['path'],mode='100644',type='blob',sha=f['sha'])for f in large]+[dict(path='outputs/extra_sizing_cost_stress/publication_manifest.json',mode='100644',type='blob',content=manifest_raw.decode())]
 tree=api('git/trees','POST',dict(base_tree=BASE_TREE,tree=elements))['sha']
 full=api('git/trees/'+tree+'?recursive=1');assert not full['truncated'];by={f['path']:f for f in full['tree']if f['type']=='blob'}
 originals=[x for x in source['tree']if x['type']=='blob']
 for f in originals:assert by[f['path']]['sha']==f['sha'],'Original source/history changed: '+f['path']
 for f in files:assert by[f['path']]['sha']==f['git_blob_SHA'],'Uploaded blob mismatch: '+f['path']
 assert by['outputs/extra_sizing_cost_stress/publication_manifest.json']['sha']==blob_sha(manifest_raw)
 commit=api('git/commits','POST',dict(message='Complete fixed EXTRA sizing/cost matrix: B G H I100 I50 I25; preserve funding gaps and 2025 sensitivity',tree=tree,parents=[EXPECTED]))['sha']
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==EXPECTED,'Branch changed; refuse to overwrite'
 api('git/refs/heads/'+BRANCH,'PATCH',dict(sha=commit,force=False))
 assert api('git/ref/heads/'+BRANCH)['object']['sha']==commit
 assert api('git/ref/heads/main')['object']['sha']==main_before
 receipt=dict(commit=commit,tree=tree,branch=BRANCH,parent=EXPECTED,locked_source=SOURCE,original_blob_checks=len(originals),published_file_checks=len(files)+1,main_unchanged=main_before,all_remote_blob_hashes_verified=True,report_url='https://github.com/'+REPO+'/blob/'+commit+'/EXTRA_SIZING_COST_STRESS.md',large_files_uploaded_via_authenticated_gh=True)
 (O/'github_receipt.json').write_text(json.dumps(receipt,indent=2));print('PUBLISHED',json.dumps(receipt),flush=True)
if __name__=='__main__':main()
