from pathlib import Path
import sys,subprocess,json,datetime,concurrent.futures
O=Path(__file__).resolve().parent
periods=['2020','2021','2022','2023','2024','2026'];rows=[]
def task(pair):
 y,a=pair
 with(O/f'{y}_{a}.log').open('a')as f:rc=subprocess.run([sys.executable,'-u',str(O/'worker.py'),y,a],stdout=f,stderr=subprocess.STDOUT).returncode
 return dict(period=y,asset=a,returncode=rc,finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
 fs=[pool.submit(task,(y,a))for y in periods for a in ['BTC','ETH']]
 for f in concurrent.futures.as_completed(fs):
  row=f.result();rows.append(row);(O/'execution.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
# 2025 serial to leave memory for the authorized S_ALL parsed view.
for asset in ['BTC','ETH']:
 row=task(('2025',asset));rows.append(row);(O/'execution.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
