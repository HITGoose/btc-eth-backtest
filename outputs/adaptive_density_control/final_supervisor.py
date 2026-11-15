from pathlib import Path
import sys,json,subprocess,concurrent.futures,datetime
O=Path(__file__).resolve().parent
assert(O/'FREEZE.json').exists(),'No post-training execution before immutable freeze'
rows=[]
def task(t):
 stage,period,asset=t
 with(O/f'{stage}_{period}_{asset}.log').open('a')as f:p=subprocess.run([sys.executable,'-u',str(O/'recent_worker.py'),asset]if period=='NOV'else[sys.executable,'-u',str(O/'worker.py'),period,asset,stage],stdout=f,stderr=subprocess.STDOUT)
 return dict(stage=stage,period=period,asset=asset,returncode=p.returncode,finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
tasks=[('train_final',y,a)for y in ['2020','2021','2022']for a in ['BTC','ETH']]+[('final',y,a)for y in ['2023','2024','2026','NOV']for a in ['BTC','ETH']]
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
 fs=[pool.submit(task,t)for t in tasks]
 for f in concurrent.futures.as_completed(fs):r=f.result();rows.append(r);(O/'final_execution.json').write_text(json.dumps(rows,indent=2));print(r,flush=True)
for asset in ['BTC','ETH']:
 r=task(('final','2025',asset));rows.append(r);(O/'final_execution.json').write_text(json.dumps(rows,indent=2));print(r,flush=True)
