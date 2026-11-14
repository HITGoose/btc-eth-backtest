from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import sys,subprocess,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent
jobs=[(y,a) for y in (2019,2024,2021,2022,2023,2025) for a in ('BTC','ETH')]
def run(job):
 year,asset=job;folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'status.json').exists():
  q=json.loads((folder/'status.json').read_text())
  if q.get('completed'):return dict(year=year,asset=asset,reused=True)
 with (folder/'run.log').open('w') as log:p=subprocess.run([sys.executable,str(OUT/'worker.py'),str(year),asset],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
 return dict(year=year,asset=asset,returncode=p.returncode)
with ThreadPoolExecutor(max_workers=4) as pool:
 for future in as_completed([pool.submit(run,j) for j in jobs]):
  print('FINISHED',future.result(),flush=True)
  subprocess.run([sys.executable,str(OUT/'collect.py')],cwd=ROOT,stdout=subprocess.DEVNULL)
print('ALL_REQUESTED_RUNS_FINISHED',flush=True)
