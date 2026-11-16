"""I/O-only recovery for the existing ER checkout. Do not modify source/fingerprints.
Run AFTER the old fifth cell has stopped. Exact original archives only.
"""
from pathlib import Path
import os,sys,json,subprocess,hashlib,argparse,fcntl,shutil,time
import cache_doctor as doctor

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo-root',required=True);p.add_argument('--results-root',required=True);p.add_argument('--data-root',default='/content/btc_eth_market_cache');p.add_argument('--drive-results');p.add_argument('--resume',action='store_true');q=p.parse_args()
 repo=Path(q.repo_root).resolve();out=Path(q.results_root).resolve();data=Path(q.data_root).resolve();assert(repo/'outputs/er_v2_retests/pipeline.py').exists()and out.exists(),'Use the ORIGINAL ER runtime and original result directory'
 lock=(out/'coordinator.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('Original ER task still running. Wait for completion; do not interrupt to run this recovery.')
 receipts=[]
 for asset in ['BTC','ETH']:
  name=asset+'USDT-trades-2026-10-29.zip';url=f'https://data.binance.vision/data/futures/um/daily/trades/{asset}USDT/{name}';path=data/'archives/daily/trades'/f'{asset}USDT'/name;source=repo/f'outputs/baseline_registry/reused/ER_V2_REFERENCE/2026/{asset}/raw_sources.json';known=json.loads(source.read_text()).get('2026-10-29',{}).get('sha256');assert known==doctor.FROZEN_SNAPSHOTS[name]
  path.parent.mkdir(parents=True,exist_ok=True)
  with path.with_suffix('.lock').open('a')as filelock:
   fcntl.flock(filelock,fcntl.LOCK_EX)
   result=doctor.recover(url,path,known)if q.resume else doctor.inspect_archive(url,path,known);receipts.append(result)
   if q.resume:
    valid=doctor.sha(path);assert valid==known
    for temp in out.glob('tasks/**/temporary/'+name):
     if doctor.sha(temp)!=known:temp.rename(temp.with_name(temp.name+'.quarantine.io_recovery.'+str(time.time_ns())))
  print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
 record=dict(mode='PINNED_ORIGINAL_SNAPSHOT_IO_ONLY',source_unmodified=True,financial_fingerprint_checks_not_bypassed=True,doctor_SHA256=doctor.sha(Path(doctor.__file__)),driver_SHA256=doctor.sha(Path(__file__)),files=receipts)
 (out/'io_recovery.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
 if not q.resume:return
 boot=out/'io_recovery_bootstrap';boot.mkdir(exist_ok=True);shutil.copy2(Path(doctor.__file__),boot/'cache_doctor.py')
 text='''import importlib.machinery,importlib.util,os
from pathlib import Path
original=importlib.machinery.SourceFileLoader.exec_module
def hook(self,module):
 original(self,module)
 if Path(self.path).resolve()==Path(os.environ['BTC_REPO_ROOT']).resolve()/'outputs/er_v2_colab/data.py':
  spec=importlib.util.spec_from_file_location('pinned_cache_doctor',Path(__file__).parent/'cache_doctor.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d);d.install_safe_acquire(module)
importlib.machinery.SourceFileLoader.exec_module=hook
'''
 (boot/'sitecustomize.py').write_text(text)
 env=os.environ.copy();env.update(BTC_REPO_ROOT=str(repo),BTC_OUTPUT_ROOT=str(out),BTC_DATA_ROOT=str(data),PYTHONUNBUFFERED='1');env['PYTHONPATH']=str(boot)+os.pathsep+env.get('PYTHONPATH','')
 if q.drive_results:env['BTC_DRIVE_RESULTS']=q.drive_results
 fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
 subprocess.run([sys.executable,'-u',str(repo/'outputs/er_v2_retests/pipeline.py')],cwd=repo,env=env,check=True)
if __name__=='__main__':main()
