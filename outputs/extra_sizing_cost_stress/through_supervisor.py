from pathlib import Path
import sys,subprocess,concurrent.futures,time,json
import shared as s
O=s.OUT;PERIODS=['NOV','2020','2021','2022','2024','2023','2026','2025']
def task(period,asset):
 with(O/f'through_{period}_{asset}.log').open('a')as f:p=subprocess.run([sys.executable,'-u',str(O/'through_replay.py'),period,asset,'through'],stdout=f,stderr=subprocess.STDOUT)
 return dict(period=period,asset=asset,returncode=p.returncode)
def main():
 pending=[(p,a)for p in PERIODS for a in ['ETH','BTC']];active={};done=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
  while pending or active:
   for item in pending[:]:
    if len(active)>=2:break
    period,asset=item;base=O/'runs'/period/asset/'baseline/status.json'
    if not base.exists():continue
    # Avoid three simultaneous 2025 ETH full-day nine-view allocations.
    if period=='2025'and asset=='ETH'and not(O/'funded/runs/2025/ETH/funded/status.json').exists():continue
    active[pool.submit(task,period,asset)]=item;pending.remove(item)
   for f in list(active):
    if f.done():r=f.result();done.append(r);del active[f];print(json.dumps(r),flush=True)
   s.dump(O/'through_execution_status.json',dict(pending=pending,active=list(active.values()),results=done))
   if pending or active:time.sleep(3)
if __name__=='__main__':main()
