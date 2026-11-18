"""Restricted stage10/11 runner and read-only merger; same pinned MA engine."""
from pathlib import Path
import os,sys,json,argparse,hashlib,shutil,subprocess,concurrent.futures,fcntl,time
HERE=Path(__file__).resolve().parent

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def copy_verified(source,target):
 st=json.loads((source/'status.json').read_text());assert st.get('complete')
 assert sha(source/'result.json')==st['result_SHA256']and sha(source/'equity.npz')==st['equity_SHA256']
 q=json.loads((source/'result.json').read_text());assert q.get('baseline')=='MA_DIRECTION_REFERENCE'or q.get('key')=='MA_DIRECTION_REFERENCE','Not an MA reference/account'
 assert not any(x.get('event')in ['adaptive_v2_request','partial_exit','partial_exit_requested']for x in q['events'])
 if(target/'status.json').exists():
  t=json.loads((target/'status.json').read_text());assert t['result_SHA256']==st['result_SHA256']and t['equity_SHA256']==st['equity_SHA256'];return
 target.mkdir(parents=True,exist_ok=True)
 for p in source.iterdir():
  if p.is_file()and p.suffix in ['.json','.npz']and p.name!='status.json':shutil.copy2(p,target/p.name)
 shutil.copy2(source/'status.json',target/'status.json')

def setup(q):
 main=Path(q.main_drive);assert(main/'data_revision.json').is_file()
 target=Path(os.environ['BTC_OUTPUT_ROOT']);target.mkdir(parents=True,exist_ok=True)
 for name in ['data_revision.json']:
  src=main/name;dst=target/name
  if dst.exists():assert sha(dst)==sha(src)
  else:shutil.copy2(src,dst)
 sys.path.insert(0,str(Path(os.environ['BTC_REPO_ROOT'])/'outputs/ma_direction_retests'));import common as c
 sys.path.insert(0,str(Path(os.environ['BTC_REPO_ROOT'])/'outputs/ma_direction_resume'));import revision
 revision.install(c)
 assert c.revision_parent_fingerprint()=='107ee4449dd8c439547e2cfd5e5378735e19ef74344e15e5fd82de8c13fbca1d','Pinned MA source differs'
 for asset in ['BTC','ETH']:
  for year in range(2020,2027):
   found=None
   for sub in ['runs','imported']:
    src=main/sub/'REF'/str(year)/asset
    if(src/'status.json').exists():found=src;break
   if found:copy_verified(found,target/'imported/REF'/str(year)/asset)
   assert c.existing('REF',year,asset),('MA reference missing',year,asset)
 for stage,keys in [(10,['BTC_CONFIRM','CORE_PRIORITY','BOTH100','BOTH50','BOTH25']),(11,['REBOUND'])]:
  if stage!=q.stage:continue
  for key in keys:
   for year in range(2020,2027):
    for asset in ['BTC','ETH']:
     for sub in ['runs','imported']:
      src=main/sub/key/str(year)/asset
      if(src/'status.json').exists():copy_verified(src,target/'runs'/key/str(year)/asset);break
 plan=dict(stage=q.stage,baseline='MA_DIRECTION_REFERENCE',V2=False,fingerprint=c.fingerprint(),data_manifest_sha256=sha(target/'data_revision.json'),parallel_drive_results=os.environ['BTC_DRIVE_RESULTS'],implementation_commit='cad3c8c2828bae06d3ac0649850235cfba21d843')
 p=main/f'delegate_stage{q.stage}.json'
 if p.exists():assert json.loads(p.read_text())==plan,'Different plan already installed; preserve directories'
 else:p.write_text(json.dumps(plan,indent=2))
 c.dump(target/'parallel_plan.json',plan);c.backup(target)
 print('PARALLEL_SETUP_READY',q.stage,'fingerprint',plan['fingerprint'],flush=True)
 return c

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',type=int,choices=[10,11],required=True);p.add_argument('--main-drive',required=True);p.add_argument('--setup-only',action='store_true');p.add_argument('--merge',action='store_true');q=p.parse_args()
 if q.merge:merge(q);return
 c=setup(q)
 if q.setup_only:return
 import psutil
 from catalog import SPECS,canonical
 target=c.OUT
 with(target/'parallel_coordinator.lock').open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  c.dump(target/'parallel_state.json',dict(status='RUNNING',stage=q.stage));c.backup(target)
  # Site adapter supplies existing read-only-property and bounded network fixes.
  import runpy
  boot=target/'parallel_runtime';boot.mkdir(exist_ok=True)
  helper=Path(os.environ['BTC_REPO_ROOT'])/'outputs/recovery_fixes/scenario_cache_sources.py';shutil.copy2(helper,boot/helper.name)
  retry=(Path(os.environ['BTC_REPO_ROOT'])/'outputs/recovery_fixes/network_retry_fragment.py').read_text()
  code='''import importlib.machinery,os
from pathlib import Path
original=importlib.machinery.SourceFileLoader.exec_module
def hook(self,module):
 original(self,module)
 if Path(self.path).resolve()==Path(os.environ['BTC_REPO_ROOT']).resolve()/'outputs/ma_direction_resume/migration.py':
  import scenario_cache_sources as fix
  fix.install(module)
importlib.machinery.SourceFileLoader.exec_module=hook
'''
  (boot/'sitecustomize.py').write_text(code+'\n'+retry)
  env=os.environ.copy();env['PYTHONPATH']=str(boot)+os.pathsep+env.get('PYTHONPATH','');env['BTC_REVISION_PREVIOUS']=str(target/'no_previous_state');env.pop('BTC_DRIVE_DATA',None)
  keys=[k for k,z in SPECS.items()if z['stage']==q.stage];tasks=[]
  for year in range(2020,2027):
   for asset in ['BTC','ETH']:
    ks=list(dict.fromkeys(canonical(k,asset)for k in keys));ks=[k for k in ks if k!='REF']
    if any(not c.existing(k,year,asset)for k in ks):tasks.append((year,asset,ks))
  workers=max(1,min(4,os.cpu_count()or 1,int(psutil.virtual_memory().available/2**30//6)))
  print('ONLY_STAGE',q.stage,'asset-year tasks',len(tasks),'CPU workers',workers,flush=True)
  def one(task):
   year,asset,ks=task;log=target/'runner_logs'/f'{year}_{asset}.txt';log.parent.mkdir(exist_ok=True)
   with log.open('a')as f:done=subprocess.run([sys.executable,'-u',str(Path(os.environ['BTC_REPO_ROOT'])/'outputs/ma_direction_resume/worker.py'),str(year),asset,*ks],env=env,stdout=f,stderr=subprocess.STDOUT)
   return year,asset,done.returncode,log
  failed=[]
  with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
   pending={pool.submit(one,t):t for t in tasks}
   while pending:
    done,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
    for future in done:
     pending.pop(future);year,asset,code,log=future.result();print('DONE',year,asset,'FAILED'if code else'OK',flush=True)
     if code:failed.append(str(log));print(log.read_text()[-2500:],flush=True)
    if not done:
     for future,(year,asset,ks)in list(pending.items()):
      if not future.running():continue
      prog=target/'tasks'/str(year)/asset/('-'.join(ks))/'whole/progress.json';print('RUNNING',year,asset,prog.read_text()if prog.exists()else'loading official data',flush=True)
  c.dump(target/'parallel_state.json',dict(status='FAILED'if failed else'COMPLETE',stage=q.stage,failures=failed));c.backup(target)
  if failed:raise RuntimeError('Parallel errors preserved; rerun same notebook to resume: '+str(failed))
  print('STAGE_COMPLETE',q.stage,'main handoff will import verified results.',flush=True)

def merge(q):
 main=Path(q.main_drive);assert main.is_dir();target=Path(os.environ['BTC_OUTPUT_ROOT']);assert target.resolve()!=main.resolve(),'Merge in a separate output directory'
 sys.path.insert(0,str(Path(os.environ['BTC_REPO_ROOT'])/'outputs/ma_direction_retests'));import common as c
 sys.path.insert(0,str(Path(os.environ['BTC_REPO_ROOT'])/'outputs/ma_direction_resume'));import revision
 shutil.copy2(main/'data_revision.json',target/'data_revision.json');revision.install(c)
 for p in main.glob('freeze_*.json'):shutil.copy2(p,target/p.name)
 for root in [main/'runs',main/'imported',main/'parallel_stage10/runs',main/'parallel_stage11/runs']:
  for st in root.glob('*/*/*/status.json'):
   copy_verified(st.parent,target/'imported'/st.parent.relative_to(root))
 import runpy
 funcs=runpy.run_path(str(Path(os.environ['BTC_REPO_ROOT'])/'outputs/ma_direction_resume/run.py'));funcs['report']()
 print('MERGED_READ_ONLY',target,'See incomplete.csv; no accounts replayed.',flush=True)
if __name__=='__main__':main()
