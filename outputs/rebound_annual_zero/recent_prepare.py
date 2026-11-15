from pathlib import Path
import urllib.request,urllib.parse,urllib.error,datetime,json,hashlib
import numpy as np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;D=O/'recent_data';D.mkdir(exist_ok=True);S=O/'recent_sources';S.mkdir(exist_ok=True);C=R/'outputs/nov15_continuation/data';sources=[]
def request(url,method='GET'):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,method=method),timeout=30)as f:raw=f.read();status=f.status
 except urllib.error.HTTPError as e:raw=e.read();status=e.code
 name=hashlib.sha256((method+url).encode()).hexdigest()[:16]+'.raw';(S/name).write_bytes(raw);sources.append(dict(url=url,method=method,status=status,SHA256=hashlib.sha256(raw).hexdigest(),stored=str((S/name).relative_to(O)),received_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()));return status,raw
_,raw=request('https://www.binance.com/fapi/v1/time');server=int(json.loads(raw)['serverTime']);end=server//900000*900000;cut=1794614400000
checks=[]
for asset in ['BTC','ETH']:
 status,_=request(f'https://data.binance.vision/data/futures/um/daily/trades/{asset}USDT/{asset}USDT-trades-2026-11-14.zip.CHECKSUM');checks.append(status)
if checks==[200,200]:cut=1794700800000
for asset in ['BTC','ETH']:
 old=np.loadtxt(C/f'{asset}_15m.csv',delimiter=',',skiprows=1);cursor=int(old[-1,0]);new=[]
 while cursor<end:
  url='https://www.binance.com/fapi/v1/klines?'+urllib.parse.urlencode(dict(symbol=asset+'USDT',interval='15m',startTime=cursor,endTime=end-1,limit=1500));status,raw=request(url);assert status==200;v=json.loads(raw);assert v;new.extend(v);cursor=int(v[-1][0])+900000
 arr=np.array([[float(x)for x in r[:6]]for r in new]);assert np.allclose(old[-1],arr[0],rtol=1e-12,atol=1e-7);allrows=np.r_[old,arr[1:]];assert np.array_equal(allrows[:,0],np.arange(old[0,0],end,900000));np.savetxt(D/f'{asset}_15m.csv',allrows,delimiter=',',header='timestamp,open,high,low,close,volume',comments='',fmt='%.17g')
 # Existing official minute cache covers the currently available full-day raw replay.
 minute=np.load(C/f'{asset}_1m.npy',mmap_mode='r');assert 1793376000000+len(minute)*60000>=cut
 # Reuse without rewriting original cache.
 target=D/f'{asset}_1m.npy'
 if not target.exists():target.hardlink_to(C/f'{asset}_1m.npy')
(O/'recent_config.json').write_text(json.dumps(dict(start_ms=1793462400000,enable_rebound_ms=1794153600000,raw_execution_end_ms=cut,bar_execution_end_ms=end,server_time_ms=server,fee=0,funding=0,slip=.0002,source=sources,paths=['OHLC','OLHC'],bar_path_definition='same frozen offsets0/300/600/899seconds, linear1second synthetic prints as prior experiment'),indent=2));print('RECENT_PREPARED',cut,end)
