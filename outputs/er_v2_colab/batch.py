"""Process-isolated tasks; each task shares one tape between the two variants."""
from pathlib import Path
import os,sys,json,subprocess,concurrent.futures,time
import psutil
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
 memory=psutil.virtual_memory().available/2**30;automatic=max(1,min(4,(os.cpu_count()or 1)//2,int(memory//6)))
 workers=int(os.environ.get('BTC_WORKERS',automatic));workers=max(1,min(workers,automatic));print('CPU workers:',workers,'available GB:',round(memory,1),flush=True)
 jobs=[(str(y),a)for y in range(2020,2027)for a in ['BTC','ETH']]
 def task(job):
  y,a=job;p=subprocess.run([sys.executable,str(HERE/'run.py'),y,a],capture_output=True,text=True);return dict(year=y,asset=a,code=p.returncode,output=(p.stdout+p.stderr)[-2500:])
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
  for f in concurrent.futures.as_completed([pool.submit(task,j)for j in jobs]):
   q=f.result();results.append(q);print(len(results),'/14',q['year'],q['asset'],'OK'if q['code']==0 else'FAILED',q['output'].strip(),flush=True)
 root=Path(os.environ['BTC_OUTPUT_ROOT']);(root/'batch_status.json').write_text(json.dumps(results,indent=2))
 if any(q['code']for q in results):print('Some tasks failed. Other results retained. Fix the recorded obstruction and rerun this cell; matching completed tasks skip.')
