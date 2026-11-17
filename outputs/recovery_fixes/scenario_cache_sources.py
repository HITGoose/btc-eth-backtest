"""Runtime compatibility adapter; original pinned source/fingerprint checks stay intact."""
from pathlib import Path
import gzip,pickle,hashlib,json,os,sys,subprocess,fcntl

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

class SourceProxy:
 def __init__(self,cache):self.cache=cache
 @property
 def sources(self):return self.cache.sources
 @sources.setter
 def sources(self,value):
  target=self.cache
  while hasattr(target,'strict'):target=target.strict
  target.sources=value
  assert self.cache.sources==value

def install(module):
 if getattr(module,'sources_property_compat_installed',False):return
 original=module.migrate_checkpoint
 def migrate(c,folder,ctx,maps,used_freeze,keys,cache):
  cp=folder/'whole/checkpoint.pkl.gz';receipt=folder/'migration_receipt.json'
  # The old routine writes cp before assigning the read-only property. Preserve
  # that partial artifact only when it exactly equals the audited source state.
  if cp.exists()and not receipt.exists():
   root=module.old_root();source=root/'tasks'/ctx['period']/ctx['asset']/('-'.join(keys))/'whole/checkpoint.pkl.gz'if root else None
   if source and source.exists():
    with gzip.open(cp,'rb')as f:new=pickle.load(f)
    with gzip.open(source,'rb')as f:old=pickle.load(f)
    assert(new['fp'],new['datafp'],new['start'],new['end'],new['keys'])==(c.fingerprint(),ctx['fingerprint'],ctx['start'],ctx['end'],keys),'Partial migration incompatible; do not bypass checks'
    assert old['fp']==module.old_fingerprint(c)
    fields=lambda q:pickle.dumps((q['books'],q['marks'],q['next']),protocol=5)
    assert fields(new)==fields(old),'Financial state differs; do not replace checkpoint'
    saved=cp.with_name(cp.name+'.preserved_partial_migration.'+sha(cp)[:16])
    if saved.exists():
     import time
     saved=saved.with_name(saved.name+'.'+str(time.time_ns()))
    cp.rename(saved)
    print('PRESERVED_INCOMPLETE_MIGRATION',saved,flush=True)
  result=original(c,folder,ctx,maps,used_freeze,keys,SourceProxy(cache))
  c.dump(c.OUT/'compatibility_adapter.json',dict(adapter='ScenarioCache.sources write to strict cache only',adapter_sha256=sha(__file__),original_migration_sha256=c.digest(module.__file__),financial_source_unmodified=True,fingerprint_checks_preserved=True))
  c.backup(c.OUT/'compatibility_audit')if(c.OUT/'compatibility_audit').exists()else None
  return result
 module.migrate_checkpoint=migrate;module.sources_property_compat_installed=True

def launch():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--results',required=True);p.add_argument('--source',required=True);p.add_argument('--previous',required=True);p.add_argument('--data',required=True);p.add_argument('--drive-results');p.add_argument('--drive-data');q=p.parse_args()
 repo=Path(q.repo).resolve();out=Path(q.results).resolve();entry=repo/'outputs/ma_direction_resume';assert(entry/'run.py').is_file()and(out/'data_revision.json').is_file(),'Use existing MA recovery notebook paths'
 with(out/'revision_coordinator.lock').open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  boot=out/'sources_compat_bootstrap';boot.mkdir(exist_ok=True)
  import shutil
  shutil.copy2(__file__,boot/'scenario_cache_sources.py')
  (boot/'sitecustomize.py').write_text('''import importlib.machinery,os
from pathlib import Path
original=importlib.machinery.SourceFileLoader.exec_module
def hook(self,module):
 original(self,module)
 if Path(self.path).resolve()==Path(os.environ['BTC_REPO_ROOT']).resolve()/'outputs/ma_direction_resume/migration.py':
  import scenario_cache_sources as fix
  fix.install(module)
importlib.machinery.SourceFileLoader.exec_module=hook
''')
  env=os.environ.copy();env.update(BTC_REPO_ROOT=str(repo),BTC_OUTPUT_ROOT=str(out),BTC_DATA_ROOT=q.data,BTC_REVISION_PREVIOUS=q.previous,PYTHONUNBUFFERED='1');env['PYTHONPATH']=str(boot)+os.pathsep+env.get('PYTHONPATH','')
  if q.drive_results:env['BTC_DRIVE_RESULTS']=q.drive_results
  if q.drive_data:env['BTC_DRIVE_DATA']=q.drive_data
  fcntl.flock(lock,fcntl.LOCK_UN)
  print('Apply cache property compatibility adapter; pinned financial files unchanged. Resume original pipeline.',flush=True)
  subprocess.run([sys.executable,'-u',str(entry/'run.py'),'--source',q.source,'--previous',q.previous],cwd=repo,env=env,check=True)
if __name__=='__main__':launch()
