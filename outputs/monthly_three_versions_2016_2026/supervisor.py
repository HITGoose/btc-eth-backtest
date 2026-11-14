from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,sys,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent
jobs=[(y,a) for y in range(2018,2026) for a in ('BTC','ETH')]
def task(job):
 y,a=job;p=OUT/str(y)/a;p.mkdir(parents=True,exist_ok=True);status=p/'status.json'
 if status.exists() and json.loads(status.read_text()).get('completed'):return dict(year=y,asset=a,reused=True)
 with (p/'two_version_run.log').open('w') as f:q=subprocess.run([sys.executable,str(OUT/'worker.py'),str(y),a],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 return dict(year=y,asset=a,returncode=q.returncode)
with ThreadPoolExecutor(max_workers=4) as pool:
 for future in as_completed([pool.submit(task,j) for j in jobs]):
  print('FINISHED',future.result(),flush=True);subprocess.run([sys.executable,str(OUT/'collect.py')],cwd=ROOT,stdout=subprocess.DEVNULL)
print('ALL_MONTHLY_COMPARISONS_FINISHED',flush=True)
