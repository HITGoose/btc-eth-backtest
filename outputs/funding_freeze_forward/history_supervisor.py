from pathlib import Path
import subprocess,sys,json,concurrent.futures
O=Path(__file__).resolve().parent

def one(x):
 p,a=x
 with(O/f'history_{p}_{a}.log').open('a')as f:q=subprocess.run([sys.executable,'-u',str(O/'history.py'),p,a],stdout=f,stderr=subprocess.STDOUT)
 return dict(period=p,asset=a,returncode=q.returncode)
def main():
 records=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
  for r in pool.map(one,[(p,a)for p in ['2020','2021','2022','2023']for a in ['BTC','ETH']]):
   records.append(r);(O/'history_execution.json').write_text(json.dumps(records,indent=2));print(r,flush=True)
if __name__=='__main__':main()
