from pathlib import Path
import subprocess,sys,json,concurrent.futures,time
import shared as s
O=s.OUT;PERIODS=['NOV','2024','2026','2025','2020','2021','2022','2023']
def task(period,asset):
 with (O/f'funded_{period}_{asset}.log').open('a')as f:p=subprocess.run([sys.executable,'-u',str(O/'funded_replay.py'),period,asset,'funded'],stdout=f,stderr=subprocess.STDOUT)
 return dict(period=period,asset=asset,returncode=p.returncode)
def main():
 pending=[(p,a)for p in PERIODS for a in ('ETH','BTC')];active={};results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
  while pending or active:
   for item in pending[:]:
    p,a=item;datafile=O/'funding_data'/p/a/'result.json';fail=O/'funding_data'/p/a/'failure.json'
    if datafile.exists()and json.loads(datafile.read_text())['status']!='COMPLETE':
     d=json.loads(datafile.read_text());results.append(dict(period=p,asset=a,status='UNVERIFIED',reason='OFFICIAL_MARK_PRICE_MISSING',missing_events=len(d['invalid_records']),valid_events=len(d['events'])));pending.remove(item)
    elif fail.exists()and not datafile.exists():results.append(dict(period=p,asset=a,status='UNVERIFIED',reason=json.loads(fail.read_text())['error']));pending.remove(item)
   for item in pending[:]:
    if len(active)>=2:break
    p,a=item;status=O/'runs'/p/a/'baseline/status.json';failure=O/'runs'/p/a/'baseline/failure.json';data=O/'funding_data'/p/a/'result.json'
    if status.exists()and json.loads(status.read_text()).get('completed')and data.exists():active[pool.submit(task,p,a)]=item;pending.remove(item)
   for future in list(active):
    if future.done():r=future.result();results.append(r);del active[future];print(json.dumps(r),flush=True)
   s.dump(O/'funded_execution_status.json',dict(results=results,pending=pending,active=list(active.values())))
   if pending or active:time.sleep(3)
if __name__=='__main__':main()
