"""Read-only official Binance candles for the user's Nov13 ETH screenshot."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import hashlib
import json
import sys
import time

import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'outputs/attribution_2026'))
import binance_inputs as d
DATA=OUT/'data';DATA.mkdir(exist_ok=True)
NOW=int(datetime.now(timezone.utc).timestamp())
SOURCE='https://fapi.binance.com/fapi/v1/klines'


def fetch(interval,step,first):
    end=NOW//step*step;cursor=first;rows=[];sources=[]
    while cursor<end:
        params=dict(symbol='ETHUSDT',interval=interval,startTime=cursor*1000,endTime=end*1000-1,limit=1500)
        url=SOURCE+'?'+urlencode(params);file=DATA/f'ETHUSDT_{interval}_{cursor}_{end}.json'
        if file.exists():blob=file.read_bytes()
        else:
            for attempt in range(3):
                try:blob=urlopen(url,timeout=20).read();break
                except Exception:
                    if attempt==2:raise
                    time.sleep(attempt+1)
            file.write_bytes(blob)
        raw=json.loads(blob)
        if not isinstance(raw,list) or not raw:raise RuntimeError('Missing official klines: '+str(raw))
        part=np.array([[int(v[0])//1000,*map(float,v[1:6])] for v in raw],dtype=float)
        part=part[(part[:,0]>=cursor)&(part[:,0]+step<=end)]
        if not len(part):raise RuntimeError('No complete candle returned')
        rows.append(part);sources.append(dict(url=url,response_file=str(file),sha256=hashlib.sha256(blob).hexdigest(),rows=len(part),
            fetched_at_utc=datetime.now(timezone.utc).isoformat(),forming_candles_excluded=True))
        cursor=int(part[-1,0])+step
    data=np.concatenate(rows)
    if not np.array_equal(data[:,0],np.arange(first,end,step)):raise RuntimeError(interval+' incomplete or duplicate grid')
    if not np.isfinite(data).all() or not (data[:,3]>0).all() or not (data[:,5]>=0).all():raise RuntimeError('Invalid fields')
    if not (data[:,3]<=np.minimum(data[:,1],data[:,4])).all() or not (data[:,2]>=np.maximum(data[:,1],data[:,4])).all():raise RuntimeError('Invalid OHLC')
    return data,sources


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={interval:pool.submit(fetch,interval,step,d.END) for interval,step in [('15m',900),('1h',3600)]}
        new={k:v.result() for k,v in jobs.items()}
    old=np.loadtxt(d.DATA/'ETH_15m.csv',delimiter=',',skiprows=1);old[:,0]/=1000
    merged=np.concatenate((old,new['15m'][0]));assert np.array_equal(merged[:,0],np.arange(d.FIRST15,new['15m'][0][-1,0]+900,900))
    file=DATA/'ETH_15m_extended.csv'
    np.savetxt(file,np.column_stack((merged[:,0]*1000,merged[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,
               header='timestamp,open,high,low,close,volume',comments='')
    hour=np.load(ROOT/'outputs/ma_multitimeframe_2026/data/ETH_1h.npy')
    hour=np.concatenate((hour,new['1h'][0]));assert np.array_equal(hour[:,0],np.arange(hour[0,0],hour[-1,0]+3600,3600))
    np.save(DATA/'ETH_1h_extended.npy',hour)
    d.dump(OUT/'sources.json',dict(today_beijing='2026-11-13',symbol='ETHUSDT USD-M perpetual',source=SOURCE,
        now_utc=datetime.fromtimestamp(NOW,timezone.utc).isoformat(),sources=[s for _,ss in new.values() for s in ss],
        last_15m_close_utc=datetime.fromtimestamp(merged[-1,0]+900,timezone.utc).isoformat(),
        last_15m_close=float(merged[-1,4]),price_file=str(file),end_seconds=int(merged[-1,0])+900))
    print('TODAY_INPUTS_READY',json.loads((OUT/'sources.json').read_text()),flush=True)


if __name__=='__main__':main()
