from pathlib import Path
import concurrent.futures,subprocess,sys,json
O=Path(__file__).resolve().parent

def run(job):
 y,a=job;p=O/'logs'/f'{y}_{a}.log';p.parent.mkdir(exist_ok=True)
 with p.open('a')as f:
  cmd=[sys.executable,str(O/'runner.py'),y,a];f.write('COMMAND '+repr(cmd)+'\n');f.flush();r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 print('DONE'if r.returncode==0 else'FAILED',*job,flush=True)
 return dict(year=y,asset=a,returncode=r.returncode,log=str(p.relative_to(O)))
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as ex:results=list(ex.map(run,[(str(y),a)for y in range(2020,2027)for a in ['BTC','ETH']]))
(O/'execution_status.json').write_text(json.dumps(results,indent=2))
assert all(x['returncode']==0 for x in results)
print('ALL_28_NEW_ACCOUNTS_COMPLETE',flush=True)
