"""Fixed per-period baseline gate and complete cost schedule, independent of PnL."""
from pathlib import Path
import subprocess,sys,json,concurrent.futures,time,threading
O=Path(__file__).resolve().parent
PERIODS=['NOV','2024','2020','2021','2022','2023','2026','2025'];LOCK=threading.Lock();ROWS=[]
def task(period,asset,stage):
 log=O/f'{period}_{asset}_{stage}.log'
 with log.open('a')as f:
  f.write('\n# RUN '+str(time.time())+'\n');f.flush();runner='sizing_only_replay.py'if period in ('2024','2025','2026')and asset=='ETH'and stage=='experiment'else'replay.py'
  p=subprocess.run([sys.executable,'-u',str(O/runner),period,asset,stage],stdout=f,stderr=subprocess.STDOUT)
 row=dict(period=period,asset=asset,stage=stage,returncode=p.returncode,log=str(log.relative_to(O)))
 with LOCK:
  ROWS.append(row);tmp=O/'execution_status.tmp';tmp.write_text(json.dumps(ROWS,indent=2));tmp.replace(O/'execution_status.json');print(json.dumps(row),flush=True)
 return row
def period_run(period):
 # Own asset baseline required before its small-size/cost run. No PnL-based skips.
 for asset in ('ETH','BTC'):task(period,asset,'baseline')
 for asset in ('ETH','BTC'):
  if asset=='BTC'and period in ('2024','2025','2026'):continue # unchanged C0/C1 proof plus actual funded C2—C4 handle all required BTC cases
  task(period,asset,'experiment')
def main():
 with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:list(pool.map(period_run,PERIODS))
if __name__=='__main__':main()
