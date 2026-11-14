"""Reacquire only the same 2026 comparison inputs, with official checksums."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.request import Request,urlopen
import hashlib
import json
import shutil
import time
import zipfile

import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
DATA=OUT/'data';DATA.mkdir(parents=True,exist_ok=True)
TEMP=OUT/'temporary';TEMP.mkdir(exist_ok=True)
BASE='https://data.binance.vision/data/futures/um'
TZ=timezone(timedelta(hours=8))
START=int(datetime(2026,1,1,tzinfo=TZ).timestamp())
END=int(datetime(2026,11,1,tzinfo=TZ).timestamp())
WARM=START-30*86400
FIRST15=WARM-15*86400
FIRST1=int(datetime(2025,12,31,tzinfo=timezone.utc).timestamp())


def dump(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,default=lambda x:x.item())+'\n');tmp.replace(path)


def acquire(url,path):
    expected=urlopen(url+'.CHECKSUM',timeout=30).read().decode().split()[0].lower()
    if len(expected)!=64:raise RuntimeError('Invalid official checksum')
    if not path.exists():
        part=path.with_suffix('.part')
        for attempt in range(4):
            try:
                offset=part.stat().st_size if part.exists() else 0
                request=Request(url,headers={'Range':f'bytes={offset}-'} if offset else {})
                with urlopen(request,timeout=90) as response:
                    resume=offset and response.status==206
                    with part.open('ab' if resume else 'wb') as f:shutil.copyfileobj(response,f,1024*1024)
                part.replace(path);break
            except Exception:
                if attempt==3:raise
                time.sleep(attempt+1)
    actual=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
    if actual!=expected:raise RuntimeError('Official checksum mismatch: '+str(path))
    return dict(url=url,bytes=path.stat().st_size,sha256=actual,official_checksum_match=True)


def read_zip(path,columns):
    with zipfile.ZipFile(path) as z:
        member=next(x for x in z.namelist() if x.endswith('.csv'))
        with z.open(member) as f:first=f.readline().split(b',',1)[0]
        with z.open(member) as f:
            return pd.read_csv(f,header=None,skiprows=0 if first.isdigit() else 1,usecols=columns,
                               dtype=np.float64,float_precision='round_trip').to_numpy()


def months(first):
    return (['2025-11'] if first=='15m' else [])+['2025-12']+[f'2026-{m:02}' for m in range(1,11)]


def prepare():
    jobs=[(a,interval,m) for a in ('BTC','ETH') for interval in ('15m','1m') for m in months(interval)]
    def job(x):
        asset,interval,month=x;symbol=asset+'USDT'
        url=f'{BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip'
        file=DATA/f'{asset}_{interval}_{month}.zip'
        meta=acquire(url,file);return asset,interval,read_zip(file,list(range(6))),dict(asset=asset,interval=interval,month=month,**meta)
    groups={(a,k):[] for a in ('BTC','ETH') for k in ('15m','1m')};sources=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for asset,interval,rows,meta in pool.map(job,jobs):
            groups[asset,interval].append(rows);sources.append(meta)
    metadata={}
    for a in ('BTC','ETH'):
        info={}
        for interval,step,first in (('15m',900,FIRST15),('1m',60,FIRST1)):
            rows=np.concatenate(groups[a,interval]);scale=1e6 if rows[0,0]>1e14 else 1000
            rows[:,0]/=scale;rows=rows[(rows[:,0]>=first)&(rows[:,0]<END)]
            rows=rows[np.argsort(rows[:,0],kind='stable')]
            expected=np.arange(first,END,step,dtype=np.int64)
            if not np.array_equal(rows[:,0],expected):raise RuntimeError('Incomplete or duplicate native '+a+' '+interval)
            if np.any(~np.isfinite(rows)) or np.any(rows[:,3]<=0):raise RuntimeError('Invalid native prices')
            if np.any(rows[:,3]>np.minimum(rows[:,1],rows[:,4])) or np.any(rows[:,2]<np.maximum(rows[:,1],rows[:,4])):
                raise RuntimeError('Invalid OHLC orientation')
            if interval=='15m':
                file=DATA/f'{a}_15m.csv'
                np.savetxt(file,np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,
                           header='timestamp,open,high,low,close,volume',comments='')
                info['price_file']=str(file)
            else:
                np.save(DATA/f'{a}_1m.npy',rows[:,1:6],allow_pickle=False)
                info.update(minute_first=first,minute_end=END,missing_native_minutes=0,
                            min_price=float(rows[:,3].min()),max_price=float(rows[:,2].max()))
        metadata[a]=info
        print(a,'INPUTS_READY',info,flush=True)
    dump(OUT/'candle_sources.json',sources);dump(OUT/'prepared_inputs.json',metadata)
    print('PREPARED',len(sources),'official candle archives',flush=True)


if __name__=='__main__':prepare()
