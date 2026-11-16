from pathlib import Path
import subprocess,sys,concurrent.futures,json
O=Path(__file__).resolve().parent
# Every interval scheduled; order only prioritizes existing2026 recovery.
def run(v):
 y,a=v;p=O/'logs'/f'{y}_{a}.log';p.parent.mkdir(exist_ok=True)
 with p.open('a')as f:
  cmd=[sys.executable,str(O/'compare_runner.py'),y,a];f.write('COMMAND '+repr(cmd)+'\n');f.flush();r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 print('DONE'if r.returncode==0 else'BLOCKED',y,a,flush=True);return dict(year=y,asset=a,returncode=r.returncode,log=str(p.relative_to(O)))
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:results=list(pool.map(run,[(str(y),a)for y in [2026,2020,2021,2022,2023,2024,2025]for a in ['BTC','ETH']]))
# Retry actual disk-capacity failures serially after concurrent downloads have finished.
for i,v in enumerate(results):
 if v['returncode']:
  failure=O/'runs'/v['year']/v['asset']/'failure.json'
  if failure.exists()and'INSUFFICIENT_DISK_FOR_RAW_ARCHIVE'in failure.read_text():results[i]=dict(run((v['year'],v['asset'])),serial_disk_retry=True)
(O/'dispatch_results.json').write_text(json.dumps(results,indent=2));print('ALL_REQUESTED_INTERVALS_ATTEMPTED',flush=True)
