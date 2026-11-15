from pathlib import Path
import sys,subprocess,concurrent.futures,json,datetime
O=Path(__file__).resolve().parent
rows=[]
def task(pair):
 y,a=pair
 with(O/f'train_{y}_{a}.log').open('a')as f:p=subprocess.run([sys.executable,'-u',str(O/'worker.py'),y,a,'train'],stdout=f,stderr=subprocess.STDOUT)
 return dict(period=y,asset=a,stage='train',returncode=p.returncode,finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
 fs=[pool.submit(task,(y,a))for y in ['2020','2021','2022']for a in ['BTC','ETH']]
 for f in concurrent.futures.as_completed(fs):
  r=f.result();rows.append(r);(O/'training_execution.json').write_text(json.dumps(rows,indent=2));print(r,flush=True)
