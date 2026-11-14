from pathlib import Path
from datetime import datetime
import sys,json,hashlib,shutil,argparse
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_dynamic_compare'));import dynamic as x
OUT=Path(__file__).resolve().parent;d=x.d;r=x.r

def repair(year,asset,day):
 folder=OUT/str(year)/asset;data=OUT/'spot_inputs'/str(year)/'data';base='https://data.binance.vision/data/spot';candles={};sources=[]
 for interval in ('1m','15m'):
  path=folder/f'daily_{interval}_{day}.zip';meta=d.acquire(f'{base}/daily/klines/{asset}USDT/{interval}/{asset}USDT-{interval}-{day}.zip',path);a=d.read_zip(path,list(range(6)));a[:,0]/=1e6 if a[0,0]>1e14 else 1000
  assert len(a)==(1440 if interval=='1m' else 96);candles[interval]=a;sources.append(meta)
 path=folder/f'raw_{day}.zip';meta=d.acquire(f'{base}/daily/trades/{asset}USDT/{asset}USDT-trades-{day}.zip',path);raw=d.read_zip(path,[0,1,4]);raw[:,2]/=1e6 if raw[0,2]>1e14 else 1000;sources.append(meta)
 assert np.all(np.diff(raw[:,0])==1)
 for interval,step in [('1m',60),('15m',900)]:
  a=candles[interval];index=((raw[:,2]//step*step-a[0,0])/step).astype(int);assert index.min()==0 and index.max()==len(a)-1
  assert np.all((raw[:,1]>=a[index,3]-1e-8)&(raw[:,1]<=a[index,2]+1e-8)), 'Official daily candles also conflict; no replacement'
 minute=data/f'{asset}_1m.npy';bar=data/f'{asset}_15m.csv'
 for f in (minute,bar):
  backup=f.with_name(f.name+f'.before_{day}');assert not backup.exists();shutil.copy2(f,backup)
 first=int(datetime(year,1,1,tzinfo=r.TZ).timestamp())-86400
 a=np.load(minute);i=((candles['1m'][:,0]-first)//60).astype(int);changed1=int(np.any(a[i]!=candles['1m'][:,1:],axis=1).sum());a[i]=candles['1m'][:,1:];np.save(minute,a)
 a=np.loadtxt(bar,delimiter=',',skiprows=1);i=np.searchsorted(a[:,0],candles['15m'][:,0]*1000);assert np.array_equal(a[i,0],candles['15m'][:,0]*1000);changed15=int(np.any(a[i,1:]!=candles['15m'][:,1:],axis=1).sum());a[i,1:]=candles['15m'][:,1:];np.savetxt(bar,a,delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
 proof=dict(year=year,asset=asset,day=day,sources=sources,whole_raw_day_rows=len(raw),changed_1m=changed1,changed_15m=changed15,price_replacement=False,strategy_change=False,official_daily_candles_agree_with_all_raw_trades=True)
 d.dump(folder/f'{day}_repair.json',proof);print(json.dumps(proof))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('year',type=int);p.add_argument('asset');p.add_argument('day');a=p.parse_args();repair(a.year,a.asset,a.day)
