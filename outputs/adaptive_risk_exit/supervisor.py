from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys
p=Path(__file__).resolve().parent
jobs=[(y,a) for y in (2024,2025) for a in ('BTC','ETH')]
def run(job):
 y,a=job;f=p/str(y)/a;f.mkdir(parents=True,exist_ok=True)
 with (f/'run.log').open('w') as log:r=subprocess.run([sys.executable,str(p/'worker.py'),str(y),a],stdout=log,stderr=subprocess.STDOUT)
 print(y,a,r.returncode,flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,jobs))
