"""Official UM-only downloads; exact existing native hashes; local CPU storage."""
from pathlib import Path
from datetime import datetime,timezone
import os,json,hashlib,shutil,zipfile,fcntl
import numpy as np
import pandas as pd
import variant_engine as v
ROOT=v.ROOT;HERE=Path(__file__).resolve().parent
DATA=Path(os.environ.get('BTC_DATA_ROOT',ROOT/'colab_data')).resolve()

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def spec(year,asset):return next(x for x in json.loads((HERE/'input_manifest.json').read_text())if x['year']==str(year)and x['asset']==asset)
def acquire(url,path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.with_suffix('.lock').open('w')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if not path.exists():
   from urllib.request import urlopen,Request
   with urlopen(Request(url,method='HEAD'),timeout=30)as response:size=int(response.headers.get('Content-Length')or 0)
   if size<=0 or shutil.disk_usage(path.parent).free<size+16*2**20:raise RuntimeError('INSUFFICIENT_DISK_OR_UNKNOWN_RAW_SIZE: '+url+'; keep original files, add disk or relocate cache')
  return v.s.b.d.acquire_original_colab(url,path)
def setup_acquire():
 d=v.s.b.d
 if hasattr(d,'acquire_original_colab'):return
 d.acquire_original_colab=d.acquire
 def shared(url,path):
  cache=DATA/'archives'/url.split('/data/futures/um/',1)[1];meta=acquire(url,cache)
  path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
  if path.resolve()!=cache.resolve()and not path.exists():os.link(cache,path)
  return meta
 d.acquire=shared

def native(year,asset):
 m=spec(year,asset)
 for name,expected in m['reference_SHA256'].items():assert sha(ROOT/m['reference']/name)==expected,('reference artifact changed',year,asset,name)
 folder=DATA/'native'/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 for interval,first,step in [('15m',m['first15'],900),('1m',m['first1'],60)]:
  name=f'{asset}_{interval}'+('.csv'if interval=='15m'else'.npy');p=folder/name;expected=m['hashes'][name]
  if p.exists():assert sha(p)==expected,('cached native changed',p);continue
  legacy=ROOT/m['legacy_data']/name
  if legacy.exists():shutil.copy2(legacy,p)
  else:
   chunks=[];sources=[];cursor=datetime.fromtimestamp(first,timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
   while cursor.timestamp()<m['end']:
    month=cursor.strftime('%Y-%m');symbol=asset+'USDT';url=f'https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip';cache=DATA/'archives'/url.split('/data/futures/um/')[1]
    meta=acquire(url,cache);rows=v.s.b.d.read_zip(cache,list(range(6)));scale=1e6 if rows[0,0]>1e14 else 1000;rows[:,0]/=scale;chunks.append(rows[(rows[:,0]>=first)&(rows[:,0]<m['end'])]);sources.append(meta)
    cursor=cursor.replace(year=cursor.year+1,month=1)if cursor.month==12 else cursor.replace(month=cursor.month+1)
   rows=np.concatenate(chunks);rows=rows[np.argsort(rows[:,0],kind='stable')];assert np.array_equal(rows[:,0],np.arange(first,m['end'],step)),('native coverage',year,asset,interval)
   if interval=='15m':np.savetxt(p,np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
   else:np.save(p,rows[:,1:6],allow_pickle=False)
   (folder/f'{interval}_sources.json').write_text(json.dumps(sources,indent=2))
  assert sha(p)==expected,('reconstructed native does not match frozen input; STOP',year,asset,interval)
 drive=os.environ.get('BTC_DRIVE_DATA')
 if drive:
  dest=Path(drive)/'native'/str(year)/asset;dest.mkdir(parents=True,exist_ok=True)
  for p in folder.iterdir():
   if p.is_file()and(not(dest/p.name).exists()or(dest/p.name).stat().st_size!=p.stat().st_size):shutil.copy2(p,dest/p.name)
 return folder,m

def anomaly():
 """Rebuild only missing original parsed arrays; compare every frozen byte hash."""
 b=v.s.b;a=v.s.a;manifest=json.loads((b.OUT/'whitelist_manifest.json').read_text());folder=DATA/'anomaly_20250829';folder.mkdir(parents=True,exist_ok=True)
 archive=folder/'ETHUSDT-trades-2025-08-29.zip';meta=acquire('https://data.binance.vision/data/futures/um/daily/trades/ETHUSDT/'+archive.name,archive);assert sha(archive)==b.EXPECTED_SHA
 for name in manifest['parsed_arrays_SHA256']:
  p=folder/(name+'.npy')
  if p.exists():assert sha(p)==manifest['parsed_arrays_SHA256'][name]
 missing=any(not(folder/(n+'.npy')).exists()for n in manifest['parsed_arrays_SHA256'])
 if missing:
  arrays={n:np.lib.format.open_memmap(folder/(n+'.npy'),mode='w+',dtype='float64'if n=='price'else'int64',shape=(manifest['rows'],))for n in ('id','time_ms','price')};offset=0
  with zipfile.ZipFile(archive)as z,z.open('ETHUSDT-trades-2025-08-29.csv')as f:
   for chunk in pd.read_csv(f,usecols=['id','time','price'],dtype={'id':'int64','time':'int64','price':'float64'},float_precision='round_trip',chunksize=250000):
    n=len(chunk)
    for key,col in [('id','id'),('time_ms','time'),('price','price')]:arrays[key][offset:offset+n]=chunk[col].to_numpy()
    offset+=n
  assert offset==manifest['rows']
  for array in arrays.values():array.flush()
  del arrays
 for n,h in manifest['parsed_arrays_SHA256'].items():assert sha(folder/(n+'.npy'))==h,('anomaly array mismatch',n)
 # Adapter reads its own immutable audit/manifest and our cached arrays/archive.
 class CachedViews(a.Views):
  def __init__(self):
   self.manifest=manifest;self.folder=folder;self.views={};a.validate_gate('ETH','2025-08-29',sha(archive),manifest)
   assert sha(b.OUT/'raw_audit/audit.json')==manifest['audit_JSON_SHA256']
   self.ids=np.load(folder/'id.npy',mmap_mode='r');self.time_ms=np.load(folder/'time_ms.npy',mmap_mode='r');self.price=np.load(folder/'price.npy',mmap_mode='r');self.n=len(self.ids);self.sorted=np.argsort(self.time_ms,kind='stable');self.pairs={x['trade_id']:[p['source_line']-2 for p in x['records']]for x in manifest['conflicts']}
 return CachedViews()
setup_acquire()
