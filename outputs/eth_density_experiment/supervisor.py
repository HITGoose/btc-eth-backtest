from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,json
OUT=Path(__file__).resolve().parent

def job(item):
 period,asset=item;folder=OUT/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True)
 for attempt in range(3):
  with (folder/f'run_attempt_{attempt}.log').open('w') as log:r=subprocess.run([sys.executable,str(OUT/'worker.py'),period,asset],stdout=log,stderr=subprocess.STDOUT)
  if r.returncode==0:print('DONE',period,asset,flush=True);return 0
  failure=json.loads((folder/'failure.json').read_text())if(folder/'failure.json').exists()else{}
  error=failure.get('traceback','')
  if not any(x in error for x in ('HTTPError','URLError','TimeoutError','ConnectionResetError','IncompleteRead')):break
  (folder/'failure.json').rename(folder/f'network_failure_attempt_{attempt}.json')
 print('FAILED',period,asset,flush=True);return r.returncode
if __name__=='__main__':
 assert json.loads((OUT/'baseline/status.json').read_text())['passed'],'First align 2024/2025 baseline'
 assert json.loads((OUT/'entry_tests.json').read_text())['passed']
 stages=[['2024','2025'],['2020','2021','2022','2023','2026'],['NOV']];failures=[]
 for periods in stages:
  with ThreadPoolExecutor(max_workers=4) as pool:
   jobs=[(y,a)for y in periods for a in ('BTC','ETH')]
   for item,code in zip(jobs,pool.map(job,jobs)):
    if code:failures.append(dict(period=item[0],asset=item[1],code=code))
  (OUT/'supervisor_status.json').write_text(json.dumps(dict(completed=False,finished_stage=periods,failures=failures)))
 (OUT/'supervisor_status.json').write_text(json.dumps(dict(completed=True,failures=failures)))
 sys.exit(1 if failures else 0)
