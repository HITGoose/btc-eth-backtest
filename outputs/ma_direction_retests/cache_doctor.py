"""Preserve evidence, validate public ZIPs, repair only a local checksum mismatch.
No strategy change and no disabling checksum/ID/date validators.
"""
from pathlib import Path
from urllib.request import urlopen,Request
from datetime import datetime,timezone
import hashlib,json,zipfile,shutil,os,argparse

FROZEN_SNAPSHOTS={
 'BTCUSDT-trades-2026-10-29.zip':'a634b1cc9e3858d732688afc6c8f5d51277a683a27254fc54f4ff70e29bc9d69',
 'ETHUSDT-trades-2026-10-29.zip':'a1380a5185eb2eff57a1975c5d004f92a77652d7f66799dece6103d08e20b1e8',
}
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def expected(url):
 with urlopen(url+'.CHECKSUM',timeout=30)as r:text=r.read().decode()
 value=text.split()[0].lower()
 if len(value)!=64 or any(x not in '0123456789abcdef'for x in value):raise RuntimeError('Invalid official checksum response')
 return value,text

def inspect_archive(url,path,pinned=None):
 p=Path(path);h,raw=expected(url);r=dict(at_UTC=datetime.now(timezone.utc).isoformat(),url=url,checksum_url=url+'.CHECKSUM',official_SHA256=h,official_response=raw,pinned_baseline_SHA256=pinned,path=str(p),exists=p.exists())
 if p.exists():
  r.update(bytes=p.stat().st_size,local_SHA256=sha(p));r['official_match']=r['local_SHA256']==h
  try:
   with zipfile.ZipFile(p)as z:r['first_CRC_error']=z.testzip();r['members']=z.namelist()
   r['ZIP_CRC_OK']=r['first_CRC_error']is None
  except (zipfile.BadZipFile,OSError)as e:r.update(ZIP_CRC_OK=False,ZIP_error=repr(e))
 r['pin_matches_official']=None if pinned is None else h==pinned
 return r

def recover(url,path,pinned=None):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);r=inspect_archive(url,p,pinned);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');record=p.with_name(p.name+'.doctor.'+stamp+'.json')
 def save():record.write_text(json.dumps(r,indent=2))
 if pinned and r['official_SHA256']!=pinned:
  if FROZEN_SNAPSHOTS.get(p.name)==pinned and r.get('local_SHA256')==pinned and r.get('ZIP_CRC_OK') and url.startswith('https://data.binance.vision/data/futures/um/daily/trades/'):
   r.update(status='VALID_PINNED_HISTORICAL_SNAPSHOT',current_official_match=False,historical_snapshot_match=True,price_or_ID_rewritten=False);save();return r
  r['status']='UNVERIFIED_OFFICIAL_CHANGED_FROM_BASELINE';save();raise RuntimeError(r['status']+': '+str(record))
 if r.get('official_match')and r.get('ZIP_CRC_OK'):
  r['status']='VALID_UNCHANGED';save();return r
 with urlopen(Request(url,method='HEAD'),timeout=30)as response:size=int(response.headers.get('Content-Length')or 0)
 if size<=0 or shutil.disk_usage(p.parent).free<size+16*2**20:
  r['status']='BLOCKED_INSUFFICIENT_DISK_OR_SIZE_UNKNOWN';save();raise RuntimeError(r['status']+': '+str(record))
 candidate=p.with_name(p.name+'.repair.'+stamp+'.part')
 try:
  with urlopen(url,timeout=120)as response,candidate.open('xb')as f:shutil.copyfileobj(response,f,1024*1024)
  r['candidate_SHA256']=sha(candidate);h2,_=expected(url)
  if r['candidate_SHA256']!=r['official_SHA256']or h2!=r['official_SHA256']:raise RuntimeError('Source changed or download still mismatches; keep both files UNVERIFIED')
  with zipfile.ZipFile(candidate)as z:
   if z.testzip()is not None:raise RuntimeError('Officially checksummed candidate has CRC failure; do not guess market data')
  if p.exists():
   quarantine=p.with_name(p.name+'.quarantine.'+stamp);p.rename(quarantine);r['preserved_original']=str(quarantine)
  candidate.rename(p);r['status']='LOCAL_CACHE_REPLACED_WITH_VERIFIED_OFFICIAL_BYTES';r['official_data_repaired']=False;save();return r
 except Exception as e:r.update(status='UNVERIFIED_REPAIR_FAILED',error=repr(e),candidate_retained=str(candidate));save();raise

def install_safe_acquire(D):
 d=D.v.s.b.d
 if hasattr(d,'ma_doctor_original'):return
 original=d.acquire_original_colab;d.ma_doctor_original=original
 def checked(url,path):
  try:return original(url,path)
  except RuntimeError as e:
   if 'Official checksum mismatch:'not in str(e):raise
   filename=Path(path).name;asset='BTC'if filename.startswith('BTCUSDT-')else'ETH'if filename.startswith('ETHUSDT-')else None;pinned=None
   if asset and '-trades-'in filename:
    year=int(filename.split('-trades-')[1][:4]);day=Path(path).stem[-10:];base=Path(__file__).resolve().parent/f'reused/REF/{year}/{asset}/raw_sources.json'
    if not base.exists():base=D.ROOT/f'outputs/baseline_registry/runs/{year}/{asset}/raw_sources.json'
    historical=json.loads(base.read_text()).get(day,{})if base.exists()else{}
    pinned=historical.get('sha256')
   result=recover(url,path,pinned)
   if result['status']=='VALID_PINNED_HISTORICAL_SNAPSHOT':
    meta=dict(historical);meta.update(url=url,bytes=Path(path).stat().st_size,sha256=pinned,official_checksum_match=False,historical_official_checksum_match=historical.get('official_checksum_match'),pinned_snapshot_match=True,validation_mode='PINNED_PREVIOUSLY_OFFICIAL_SNAPSHOT',current_official_SHA256=result['official_SHA256'],io_adapter_SHA256=sha(Path(__file__)));return meta
   return original(url,path)
 d.acquire_original_colab=checked
 # Verify the actual per-task hardlink too, not only the shared archive.
 shared=d.acquire
 def linked(url,path):
  meta=shared(url,path);p=Path(path);cache=D.DATA/'archives'/url.split('/data/futures/um/',1)[1]
  if p.exists()and not os.path.samefile(p,cache)and sha(p)!=meta['sha256']:
   stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');p.rename(p.with_name(p.name+'.quarantine.'+stamp));cache=D.DATA/'archives'/url.split('/data/futures/um/',1)[1];os.link(cache,p)
  return meta
 d.acquire=linked

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--data-root',default='/content/btc_eth_market_cache');a.add_argument('--repo-root',default=None);a.add_argument('--repair',action='store_true');a.add_argument('--results-root',default=None);args=a.parse_args()
 import fcntl
 coordinator=None
 if args.repair and args.results_root:
  coordinator=(Path(args.results_root)/'coordinator.lock').open('a')
  try:fcntl.flock(coordinator,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('Backtest still running: wait for it to finish before cache repair')
 for asset in ['BTC','ETH']:
  name=asset+'USDT-trades-2026-10-29.zip';url='https://data.binance.vision/data/futures/um/daily/trades/'+asset+'USDT/'+name;p=Path(args.data_root)/'archives/daily/trades'/f'{asset}USDT'/name;pinned=None
  if args.repo_root:
   for rel in [f'outputs/baseline_registry/reused/ER_V2_REFERENCE/2026/{asset}/raw_sources.json',f'outputs/baseline_registry/runs/2026/{asset}/raw_sources.json']:
    q=Path(args.repo_root)/rel
    if q.exists():pinned=json.loads(q.read_text()).get('2026-10-29',{}).get('sha256');break
  if args.repair and not args.repo_root:raise RuntimeError('Supply the original repository root to pin the baseline; do not repair unpinned historical caches')
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.with_suffix('.lock').open('a')as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   result=recover(url,p,pinned)if args.repair else inspect_archive(url,p,pinned)
   if args.repair and args.results_root and result['status']in ['VALID_UNCHANGED','LOCAL_CACHE_REPLACED_WITH_VERIFIED_OFFICIAL_BYTES','VALID_PINNED_HISTORICAL_SNAPSHOT']:
    for temp in Path(args.results_root).glob('tasks/**/temporary/'+name):
     if sha(temp)!=result['official_SHA256']:
      stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');temp.rename(temp.with_name(temp.name+'.quarantine.'+stamp))
   print(json.dumps(result,ensure_ascii=False,indent=2))
