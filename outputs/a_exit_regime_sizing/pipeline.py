from pathlib import Path
import subprocess,concurrent.futures,json
O=Path(__file__).resolve().parent;PY='/workspace/.venv-btc-eth-original/bin/python'
def task(p,a):
 with(O/f'{p}_{a}.log').open('a')as f:r=subprocess.run([PY,str(O/'runner.py'),p,a],stdout=f,stderr=subprocess.STDOUT)
 return dict(period=p,asset=a,exit_code=r.returncode)
done=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as ex:
 for f in concurrent.futures.as_completed([ex.submit(task,str(y),a)for y in range(2020,2027)for a in ['BTC','ETH']]):
  x=f.result();done.append(x);(O/'execution_status.json').write_text(json.dumps(done,indent=2));print(x,flush=True)
  if(O/'report.py').exists():subprocess.run([PY,str(O/'report.py')])
print('FINISHED_ALL',flush=True)
