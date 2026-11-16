from pathlib import Path
import concurrent.futures,subprocess,sys,time
O=Path(__file__).resolve().parent
PYTHON=sys.executable

def run(job):
 y,a,stage=job;p=O/'logs'/f'{y}_{a}_{stage}.log';p.parent.mkdir(exist_ok=True)
 with p.open('a')as f:
  cmd=[PYTHON,str(O/'runner.py'),y,a,stage];f.write('COMMAND '+repr(cmd)+'\n');f.flush();r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(str(p))
 print('DONE',*job,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as ex:list(ex.map(run,[(str(y),a,'train')for y in range(2020,2023)for a in ['BTC','ETH']]))
subprocess.run([PYTHON,str(O/'freeze.py')],check=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as ex:list(ex.map(run,[(str(y),a,'final')for y in range(2020,2027)for a in ['BTC','ETH']]))
print('ALL_FINANCIAL_RUNS_COMPLETE',flush=True)
