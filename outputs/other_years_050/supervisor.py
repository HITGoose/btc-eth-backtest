from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,os,signal,sys
OUT=Path(__file__).resolve().parent;PY='/workspace/.venv-btc-eth-original/bin/python'
# Stop the prior sequential worker before launching replacements; finished
# asset/year status files are authoritative and never replayed.
try:os.kill(10806,signal.SIGKILL)
except ProcessLookupError:pass
jobs=[]
for y in range(2021,2026):
 for a in ['BTC','ETH']:
  f=OUT/str(y)/f'{a}_status.json'
  if not(f.exists() and json.loads(f.read_text()).get('completed')):jobs.append((y,a))
print('PENDING_ONLY',jobs,flush=True)
def run(job):
 y,a=job;folder=OUT/str(y);folder.mkdir(exist_ok=True)
 with (folder/f'{a}_run.log').open('w') as log:r=subprocess.run([PY,'-u',str(OUT/'batch.py'),'--year',str(y),'--asset',a],stdout=log,stderr=subprocess.STDOUT)
 return dict(year=y,asset=a,returncode=r.returncode)
finished=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,j) for j in jobs]):
  item=future.result();finished.append(item);print('FINISHED',item,flush=True)
  (OUT/'parallel_progress.json').write_text(json.dumps(finished))
  subprocess.run([PY,str(OUT/'collect.py')],stdout=subprocess.DEVNULL)
subprocess.run([PY,str(OUT/'collect.py')],stdout=subprocess.DEVNULL)
print('ALL_REQUESTED_YEARS_FINISHED',flush=True)
