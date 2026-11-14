from pathlib import Path
import sys,json,hashlib,shutil
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import worker as w
d=w.d;r=w.r;out=w.OUT;folder=out/'2020/BTC';data=out/'2020/data';day='2020-10-27';base='https://data.binance.vision/data/spot';sources=[];candles={}
for interval in ('1m','15m'):
 path=folder/f'daily_{interval}_{day}.zip';url=f'{base}/daily/klines/BTCUSDT/{interval}/BTCUSDT-{interval}-{day}.zip'
 meta=d.acquire(url,path);a=d.read_zip(path,list(range(6)));a[:,0]/=1e6 if a[0,0]>1e14 else 1000;sources.append(meta);candles[interval]=a
 assert len(a)==(1440 if interval=='1m' else 96) and np.all(np.diff(a[:,0])==(60 if interval=='1m' else 900))
path=folder/f'raw_trades_{day}.zip';meta=d.acquire(f'{base}/daily/trades/BTCUSDT/BTCUSDT-trades-{day}.zip',path);raw=d.read_zip(path,[0,1,4]);raw[:,2]/=1e6 if raw[0,2]>1e14 else 1000;sources.append(meta)
assert np.all(np.diff(raw[:,0])==1) and np.all(np.diff(raw[:,2])>=0)
index=((raw[:,2]//60*60-candles['1m'][0,0])/60).astype(int)
assert index.min()==0 and index.max()==1439
bad=(raw[:,1]<candles['1m'][index,3]-1e-8)|(raw[:,1]>candles['1m'][index,2]+1e-8)
assert not bad.any(),f'Daily candles still conflict with {bad.sum()} raw trades'
index15=((raw[:,2]//900*900-candles['15m'][0,0])/900).astype(int)
assert np.all((raw[:,1]>=candles['15m'][index15,3]-1e-8)&(raw[:,1]<=candles['15m'][index15,2]+1e-8))
minute_path=data/'BTC_1m.npy';bar_path=data/'BTC_15m.csv'
for p in (minute_path,bar_path):
 backup=p.with_suffix(p.suffix+'.before_daily_fix');assert not backup.exists();shutil.copy2(p,backup)
first=int(__import__('datetime').datetime(2019,12,31,tzinfo=r.TZ).timestamp())
rows=np.load(minute_path);indexes=((candles['1m'][:,0]-first)//60).astype(int);diff1=int(np.any(rows[indexes]!=candles['1m'][:,1:],axis=1).sum());rows[indexes]=candles['1m'][:,1:];np.save(minute_path,rows)
rows=np.loadtxt(bar_path,delimiter=',',skiprows=1);indexes=np.searchsorted(rows[:,0],candles['15m'][:,0]*1000);assert np.array_equal(rows[indexes,0],candles['15m'][:,0]*1000);diff15=int(np.any(rows[indexes,1:]!=candles['15m'][:,1:],axis=1).sum());rows[indexes,1:]=candles['15m'][:,1:];np.savetxt(bar_path,rows,delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
proof=dict(day=day,source_market='BINANCE_SPOT_ONLY',sources=sources,whole_raw_day_rows=len(raw),raw_trade_ids_contiguous=True,all_actual_prices_inside_official_daily_1m_and_15m=True,replaced_whole_day=True,changed_1m_candles=diff1,changed_15m_candles=diff15,backup_files=['BTC_1m.npy.before_daily_fix','BTC_15m.csv.before_daily_fix'],strategy_changed=False)
d.dump(data/'BTC_daily_repair.json',proof);d.dump(folder/'daily_repair.json',proof);print(json.dumps(proof))
