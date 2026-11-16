"""Preserve frozen Jan-Oct native prefix; official daily data extends 2026."""
import common as c
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
np=c.np

def prepare(year,asset):
 year=int(year)
 data,m=c.D.native(year,asset)
 if year!=2026:return data,m
 end=c.END2026;out=c.D.DATA/'native_extended_20261115'/asset;out.mkdir(parents=True,exist_ok=True);receipt=out/'provenance.json'
 if receipt.exists():
  z=json.loads(receipt.read_text());assert z['prefix_hashes']==m['hashes']and z['end']==end
  for name,h in z['hashes'].items():assert c.digest(out/name)==h
  return out,dict(m,end=end,hashes=z['hashes'],original_end=m['end'])
 for interval,step in [('15m',900),('1m',60)]:
  first=m['end'];symbol=asset+'USDT';day=datetime.fromtimestamp(first,timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0);chunks=[];sources=[]
  while day.timestamp()<end:
   stamp=day.strftime('%Y-%m-%d');url=f'https://data.binance.vision/data/futures/um/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{stamp}.zip';path=c.D.DATA/'archives'/url.split('/data/futures/um/')[1]
   meta=c.D.acquire(url,path);r=c.s.b.d.read_zip(path,list(range(6)));r[:,0]/=1e6 if r[0,0]>1e14 else 1000;chunks.append(r[(r[:,0]>=first)&(r[:,0]<end)]);sources.append(meta);day+=timedelta(days=1)
  r=np.concatenate(chunks);assert np.array_equal(r[:,0],np.arange(first,end,step)), '2026 extended coverage gap'
  if interval=='15m':
   old=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1);new=np.column_stack((r[:,0]*1000,r[:,1:]));allrows=np.r_[old,new];assert np.array_equal(allrows[:len(old)],old)
   np.savetxt(out/f'{asset}_15m.csv',allrows,delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
  else:
   old=np.load(data/f'{asset}_1m.npy');allrows=np.r_[old,r[:,1:6]];assert np.array_equal(allrows[:len(old)],old);np.save(out/f'{asset}_1m.npy',allrows)
  c.dump(out/f'{interval}_sources.json',sources)
 hashes={n:c.digest(out/n)for n in [f'{asset}_15m.csv',f'{asset}_1m.npy']};c.dump(receipt,dict(prefix_hashes=m['hashes'],hashes=hashes,end=end,original_end=m['end'],source='BINANCE_UM_OFFICIAL_DAILY',prefix_identical_by_construction=True))
 drive=c.os.environ.get('BTC_DRIVE_DATA')
 if drive:
  import shutil
  dest=Path(drive)/out.relative_to(c.D.DATA);shutil.copytree(out,dest,dirs_exist_ok=True)
 return out,dict(m,end=end,hashes=hashes,original_end=m['end'])
