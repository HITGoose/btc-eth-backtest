from pathlib import Path
from datetime import datetime,timedelta
import sys,json,calendar,traceback,argparse
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/user_ma_squeeze050'))
import run as e
OUT=Path(__file__).resolve().parent
e.PROFILES=('M30','H4')

def series(asset):
 rows=np.loadtxt(e.d.DATA/f'{asset}_15m.csv',delimiter=',',skiprows=1);rows[:,0]/=1000
 result={}
 for key,size in [('M30',2),('H4',16)]:
  n=len(rows)//size;b=rows[:n*size].reshape(n,size,6)
  c=b[:,-1,4];v=np.stack([e.r.model.sma(c,k) for k in e.u.PERIODS])
  result[key]=((b[:,-1,0]+900).astype(np.int64)*1000,e.u.directions(v))
 return result

def prepare(year,asset):
 start=int(datetime(year,1,1,tzinfo=e.r.TZ).timestamp());end=int(datetime(year+1,1,1,tzinfo=e.r.TZ).timestamp())
 # UTC midnight grids also align to Beijing midnight and four-hour bars.
 first=start-80*86400;first1=start-86400
 folder=OUT/str(year);data=folder/'data';data.mkdir(parents=True,exist_ok=True)
 e.d.START=start;e.d.END=end;e.d.FIRST15=first;e.d.FIRST1=first1;e.d.DATA=data
 e.ANNUAL=folder;e.d.TEMP=folder/'temporary';e.d.TEMP.mkdir(exist_ok=True)
 sources=[]
 for interval,step,begin in [('15m',900,first),('1m',60,first1)]:
  pieces=[];cur=datetime.fromtimestamp(begin,e.r.UTC).replace(day=1,hour=0,minute=0,second=0)
  while int(cur.timestamp())<end:
   month=cur.strftime('%Y-%m');symbol=asset+'USDT';file=data/f'{asset}_{interval}_{month}.zip'
   url=f'{e.d.BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip'
   meta=e.d.acquire(url,file);raw=e.d.read_zip(file,list(range(6)));scale=1e6 if raw[0,0]>1e14 else 1000;meta['timestamp_divisor']=scale;raw[:,0]/=scale
   raw=raw[(raw[:,0]>=begin)&(raw[:,0]<end)];pieces.append(raw);sources.append(meta)
   file.unlink()
   cur=cur.replace(year=cur.year+1,month=1) if cur.month==12 else cur.replace(month=cur.month+1)
  rows=np.concatenate(pieces);rows=rows[np.argsort(rows[:,0])]
  if not np.array_equal(rows[:,0],np.arange(begin,end,step)):raise RuntimeError('Incomplete '+asset+' '+interval+' history; no gap filling or invented prelisting prices')
  assert np.isfinite(rows).all() and (rows[:,3]>0).all()
  assert (rows[:,3]<=np.minimum(rows[:,1],rows[:,4])).all() and (rows[:,2]>=np.maximum(rows[:,1],rows[:,4])).all()
  if interval=='15m':np.savetxt(data/f'{asset}_15m.csv',np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
  else:np.save(data/f'{asset}_1m.npy',rows[:,1:])
 e.d.dump(folder/f'{asset}_candle_sources.json',sources)
 e.annual_series=series
 return folder

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--year",type=int);parser.add_argument("--asset",choices=["BTC","ETH"]);args=parser.parse_args()
 status=[]
 # Full2020 requires2019 preheat archives; absence does not prove prelisting.
 # Attempt official files and record absence; do not substitute spot or fake bars.
 for year in ([args.year] if args.year else range(2020,2026)):
  for asset in ([args.asset] if args.asset else ['BTC','ETH']):
   existing=OUT/str(year)/f'{asset}_status.json'
   if existing.exists() and json.loads(existing.read_text()).get('completed'):continue
   print('START',year,asset,flush=True)
   try:
    folder=prepare(year,asset);e.replay(asset,'annual')
    for k in e.PROFILES:
     q=json.loads((folder/f'{asset}_{k}_result.json').read_text());status.append(dict(year=year,asset=asset,profile=k,return_pct=q['return_pct'],completed=True))
   except Exception as error:
    item=dict(year=year,asset=asset,completed=False,error=repr(error),traceback=traceback.format_exc());status.append(item)
    folder=OUT/str(year);folder.mkdir(exist_ok=True);e.d.dump(folder/f'{asset}_failure.json',item)
    print('FAILED',year,asset,repr(error),flush=True)
   e.d.dump(OUT/f'progress_{year}_{asset}.json',status)
 print('BATCH_COMPLETE',flush=True)
if __name__=='__main__':main()
