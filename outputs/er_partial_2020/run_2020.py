"""Same approved ER partial-exit rules, available 2020 partial-year window."""
from pathlib import Path
from datetime import datetime
import sys,inspect,json,argparse,traceback,shutil
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest')
sys.path.insert(0,str(ROOT/'outputs/er_partial_2026'))
import run as e
d=e.d;OUT=Path(__file__).resolve().parent
START=int(datetime(2020,2,16,tzinfo=e.r.TZ).timestamp())
END=int(datetime(2021,1,1,tzinfo=e.r.TZ).timestamp())
ORIGINAL_CONFIG=e.config
def config():
 q=ORIGINAL_CONFIG();q.update(period='2020-02-16 through 2021-01-01 exclusive UTC+8',
   full_year_2020_verified=False,missing_period='2020-01-01 through 2020-02-16: insufficient2019 preheat')
 return q

def prepare(asset):
 d.START=START;d.END=END;d.FIRST15=START-45*86400;d.FIRST1=START-86400
 d.DATA=OUT/'data';d.DATA.mkdir(exist_ok=True)
 sources=[]
 for interval,step,first in [('15m',900,d.FIRST15),('1m',60,d.FIRST1)]:
  chunks=[];cur=datetime.fromtimestamp(first,e.r.UTC).replace(day=1,hour=0,minute=0,second=0)
  while int(cur.timestamp())<END:
   month=cur.strftime('%Y-%m');symbol=asset+'USDT';path=d.DATA/f'{asset}_{interval}_{month}.zip'
   cached=OUT/path.name
   if cached.exists() and not path.exists():shutil.copy2(cached,path)
   meta=d.acquire(f'{d.BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip',path)
   rows=d.read_zip(path,list(range(6)));scale=1e6 if rows[0,0]>1e14 else 1000
   rows[:,0]/=scale;rows=rows[(rows[:,0]>=first)&(rows[:,0]<END)];chunks.append(rows)
   sources.append(dict(interval=interval,timestamp_divisor=scale,**meta));path.unlink()
   cur=cur.replace(year=cur.year+1,month=1) if cur.month==12 else cur.replace(month=cur.month+1)
  rows=np.concatenate(chunks);rows=rows[np.argsort(rows[:,0])]
  assert np.array_equal(rows[:,0],np.arange(first,END,step)), 'Incomplete native candle grid'
  assert np.isfinite(rows).all() and (rows[:,3]>0).all()
  assert (rows[:,3]<=np.minimum(rows[:,1],rows[:,4])).all() and (rows[:,2]>=np.maximum(rows[:,1],rows[:,4])).all()
  if interval=='15m':np.savetxt(d.DATA/f'{asset}_15m.csv',np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
  else:np.save(d.DATA/f'{asset}_1m.npy',rows[:,1:])
 d.dump(OUT/f'{asset}_candle_sources.json',sources)

def main(asset):
 e.OUT=OUT;e.config=config;prepare(asset)
 # Reuse exactly the approved execution engine; no prior full-year2020
 # baseline exists in this workspace, so compare both new books on same tape.
 source=inspect.getsource(e.run)
 old="    prior=json.loads((ROOT/f'outputs/attribution_2026/{asset}_ER_result.json').read_text())"
 assert source.count(old)==1
 source=source.replace(old,'    prior=None').replace("        if name=='CONTROL':","        if name=='CONTROL' and prior is not None:")
 namespace=dict(e.__dict__);exec(compile(source,'<same fixed partial engine,2020 window>','exec'),namespace)
 namespace['run'](asset)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('asset',choices=['BTC','ETH']);a=parser.parse_args()
 try:main(a.asset)
 except Exception as error:
  d.dump(OUT/f'{a.asset}_failure.json',dict(error=repr(error),traceback=traceback.format_exc(),full_year_verified=False));raise
