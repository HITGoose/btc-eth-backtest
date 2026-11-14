from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import importlib.util,sys,inspect,json,time
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent;DATA=OUT/'data';DATA.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('nov_v2',ROOT/'outputs/adaptive_risk_exit_v2/worker.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
e=v.e;d=e.d
TZ=timezone(timedelta(hours=8));START=int(datetime(2026,11,1,tzinfo=TZ).timestamp());END=int(datetime(2026,11,13,tzinfo=timezone.utc).timestamp());FIRST=START-86400

def acquire_retry(url,path):
 for attempt in range(4):
  try:return d.acquire(url,path)
  except Exception:
   if attempt==3:raise
   time.sleep(2+attempt)

def prepare():
 jobs=[(a,k,day) for a in ('BTC','ETH') for k in ('15m','1m') for day in ['2026-10-30','2026-10-31']+[f'2026-11-{i:02}' for i in range(1,13)]]
 def job(q):
  a,k,day=q;symbol=a+'USDT';p=DATA/f'{symbol}-{k}-{day}.zip';meta=acquire_retry(f'https://data.binance.vision/data/futures/um/daily/klines/{symbol}/{k}/{p.name}',p);rows=d.read_zip(p,list(range(6)));rows[:,0]/=1e6 if rows[0,0]>1e14 else 1000;p.unlink();return a,k,rows,meta
 groups={(a,k):[] for a in ('BTC','ETH') for k in ('15m','1m')};sources=[]
 with ThreadPoolExecutor(max_workers=8) as pool:
  for a,k,rows,meta in pool.map(job,jobs):groups[a,k].append(rows);sources.append(meta)
 for a in ('BTC','ETH'):
  for k in ('15m','1m'):
   r=np.concatenate(groups[a,k]);r=r[np.argsort(r[:,0])];r=r[(r[:,0]>=FIRST)&(r[:,0]<END)]
   assert np.array_equal(r[:,0],np.arange(FIRST,END,60 if k=='1m' else 900))
   if k=='1m':np.save(DATA/f'{a}_1m.npy',r[:,1:])
   else:
    old=np.loadtxt(ROOT/f'outputs/attribution_2026/data/{a}_15m.csv',delimiter=',',skiprows=1);old=old[old[:,0]<FIRST*1000];r[:,0]*=1000;r=np.concatenate((old,r));np.savetxt(DATA/f'{a}_15m.csv',r,delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
 (OUT/'candle_sources.json').write_text(json.dumps(sources))

def run(asset):
 ow=v.original_worker;source=inspect.getsource(ow.run)
 source=source.replace('d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp())',f'd.START={START};d.END={END}')
 source=source.replace("d.DATA=e.ROOT/f'outputs/other_years_050/{year}/data'",f'd.DATA=Path({str(DATA)!r})')
 source=source.replace("sources=json.loads((d.DATA.parent/f'{asset}_candle_sources.json').read_text());assert all('/data/futures/um/' in s['url'] and s['official_checksum_match'] for s in sources)","sources=json.loads((d.DATA.parent/'candle_sources.json').read_text());assert all('/data/futures/um/' in s['url'] and s['official_checksum_match'] for s in sources)")
 ns=dict(ow.__dict__);ns['OUT']=OUT;exec(compile(source,'<Nov same full raw engine>','exec'),ns);ow.run=ns['run'];ow.OUT=OUT;v.OUT=OUT;v.run(2026,asset)
if __name__=='__main__':
 if len(sys.argv)>1:run(sys.argv[1])
 else:
  import subprocess
  prepare()
  def child(a):
   with (OUT/f'{a}.log').open('w') as f:return subprocess.run([sys.executable,__file__,a],stdout=f,stderr=subprocess.STDOUT).returncode
  codes=list(ThreadPoolExecutor(max_workers=2).map(child,('BTC','ETH')));print(codes);assert not any(codes)
