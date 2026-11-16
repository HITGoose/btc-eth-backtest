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
  pending={pool.submit(task,j):j for j in jobs}
  while pending:
   done,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    pending.pop(f);q=f.result();results.append(q);print(len(results),'/14',q['year'],q['asset'],'OK'if q['code']==0 else'FAILED',q['output'].strip(),flush=True)
   if not done:
    root=Path(os.environ['BTC_OUTPUT_ROOT']);progress=[]
    for y,a in pending.values():
     p=root/'runs'/y/a/'whole/progress.json'
     if p.exists():
      try:progress.append(y+' '+a+' '+json.loads(p.read_text()).get('next_time',''))
      except (ValueError,OSError):pass
    print('RUNNING',len(results),'/14;', '; '.join(progress[-4:])or'preparing indicators / downloading official data',flush=True)
 root=Path(os.environ['BTC_OUTPUT_ROOT']);(root/'batch_status.json').write_text(json.dumps(results,indent=2))
 if any(q['code']for q in results):print('Some tasks failed. Other results retained. Fix the recorded obstruction and rerun this cell; matching completed tasks skip.')
