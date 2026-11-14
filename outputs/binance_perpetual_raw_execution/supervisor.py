from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,sys,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent
jobs=[(y,a) for y in (2024,2025) for a in ('BTC','ETH')]
def task(job):
 y,a=job;folder=OUT/str(y)/a;folder.mkdir(parents=True,exist_ok=True)
 with (folder/'run.log').open('w') as log:q=subprocess.run([sys.executable,str(OUT/'worker.py'),str(y),a],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
 return dict(year=y,asset=a,returncode=q.returncode)
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(task,j) for j in jobs]):
  print('FINISHED',f.result(),flush=True);subprocess.run([sys.executable,str(OUT/'collect.py')],cwd=ROOT,stdout=subprocess.DEVNULL)
print('ALL_RAW_PERPETUAL_JOBS_FINISHED',flush=True)
