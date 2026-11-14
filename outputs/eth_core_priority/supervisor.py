from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,json,time
OUT=Path(__file__).resolve().parent

def job(item):
 period,asset,groups=item;folder=OUT/'runs'/period/asset/groups;folder.mkdir(parents=True,exist_ok=True)
 for attempt in range(3):
  with(folder/f'run_attempt_{attempt}.log').open('w')as log:proc=subprocess.run([sys.executable,str(OUT/'worker.py'),period,asset,'--groups',groups],stdout=log,stderr=subprocess.STDOUT)
  if proc.returncode==0:print('DONE',*item,flush=True);return dict(period=period,asset=asset,groups=groups,code=0)
  failure=json.loads((folder/'failure.json').read_text())if(folder/'failure.json').exists()else{}
  if not any(x in failure.get('traceback','')for x in ('HTTPError','URLError','TimeoutError','ConnectionResetError','IncompleteRead')):break
  (folder/'failure.json').rename(folder/f'network_attempt_{attempt}.json')
 print('FAILED',*item,flush=True);return dict(period=period,asset=asset,groups=groups,code=proc.returncode)
if __name__=='__main__':
 assert json.loads((OUT/'tests.json').read_text())['passed'];assert json.loads((OUT/'validation32/test_results.json').read_text())['failed']==0
 results=[]
 # Reproduce B and D on 2024 first; B on 2025. Known 2025 D data block is
 # attempted separately and never used to block other independent cohorts.
 stage0=[('2024','BTC','B'),('2024','ETH','BD'),('2025','BTC','B'),('2025','ETH','B')]
 with ThreadPoolExecutor(max_workers=3)as pool:results+=list(pool.map(job,stage0))
 (OUT/'baseline_status.json').write_text(json.dumps(dict(passed=all(x['code']==0 for x in results),jobs=results),indent=2))
 if any(x['code']for x in results):raise SystemExit('B/D baseline alignment not complete; new experiments prohibited')
 stages=[[('2024','ETH','GHI')],[(year,asset,'B'if asset=='BTC'else'BDGHI')for year in ['2020','2021','2022','2023','2026','NOV']for asset in ['BTC','ETH']], [('2025','ETH',group)for group in 'DGHI']]
 for stage in stages:
  with ThreadPoolExecutor(max_workers=3)as pool:results+=list(pool.map(job,stage))
  (OUT/'supervisor_status.json').write_text(json.dumps(dict(completed=False,jobs=results),indent=2))
 (OUT/'supervisor_status.json').write_text(json.dumps(dict(completed=True,jobs=results,failures=[x for x in results if x['code']]),indent=2))
 raise SystemExit(1 if any(x['code']for x in results)else 0)
