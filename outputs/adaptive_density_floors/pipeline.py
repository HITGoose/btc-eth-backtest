from pathlib import Path
import subprocess,concurrent.futures,json,time
O=Path(__file__).resolve().parent;PY='/workspace/.venv-btc-eth-original/bin/python'
def task(p,a):
 with(O/f'{p}_{a}.log').open('a')as f:r=subprocess.run([PY,str(O/'experiment.py'),p,a],stdout=f,stderr=subprocess.STDOUT)
 return dict(period=p,asset=a,exit_code=r.returncode)
jobs=[(str(y),a)for y in range(2020,2027)for a in ['BTC','ETH']if not(y==2020 and a=='BTC')]
completed=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as ex:
 for fu in concurrent.futures.as_completed([ex.submit(task,*j)for j in jobs]):
  x=fu.result();completed.append(x);(O/'execution_status.json').write_text(json.dumps(completed,indent=2));print('FINISHED',x,flush=True);subprocess.run([PY,str(O/'report.py')])
subprocess.run([PY,str(O/'report.py')]);print('PIPELINE_FINISHED',flush=True)
