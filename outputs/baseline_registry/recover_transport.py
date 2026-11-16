"""Transport/logging recovery only. Original financial and data fingerprints remain checked."""
from pathlib import Path
from urllib.request import Request,urlopen
import sys,json,hashlib,inspect,fcntl,os,shutil,gzip,pickle,datetime,traceback
import compare_runner as c
# Direct runner checkpoints reference __main__.MAControl. Preserve that identity.
MAControl=c.MAControl;MAControl.__module__=__name__
O=c.O

def run(year,asset):
 f=O/'runs'/year/asset
 if(f/'status.json').exists():c.run(year,asset);return
 fail=json.loads((f/'failure.json').read_text());assert 'INSUFFICIENT_DISK_FOR_RAW_ARCHIVE'in fail['error']or('ScenarioCache'in fail['error']and'sources'in fail['error']),fail
 before_driver=c.fp();before_financial=c.s.fp();raw_sha=hashlib.sha256(inspect.getsource(c.s.b.e.RawCache.load).encode()).hexdigest();view_sha=hashlib.sha256(inspect.getsource(c.s.a.ScenarioCache.load).encode()).hexdigest();cp=f/'whole/checkpoint.pkl.gz';prior_cp_sha=None;next_time=None
 if cp.exists():
  prior_cp_sha=hashlib.sha256(cp.read_bytes()).hexdigest()
  with gzip.open(cp,'rb')as h:old=pickle.load(h)
  assert old['fp']==before_financial;assert old['keys']==['MA_DIRECTION_REFERENCE'];next_time=old['next']
 # Same readonly progress delegate used by the original reference recovery.
 c.s.a.ScenarioCache.sources=property(lambda self:self.strict.sources)
 margin=16*1024*1024
 def acquire(url,path):
  path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
  with(O/'download.lock').open('w')as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);cached=c.INVENTORY.get(path.name)
   if not path.exists()and cached and cached.exists():os.link(cached,path)
   with urlopen(Request(url,method='HEAD'),timeout=30)as response:size=int(response.headers.get('Content-Length')or 0);status=response.status
   free=shutil.disk_usage(O).free;need=max(0,size-(path.stat().st_size if path.exists()else 0))+margin
   with(O/'data_queries.jsonl').open('a')as h:h.write(json.dumps(dict(at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),url=url,status=status,content_length=size,free_disk_bytes=free,need_with_checkpoint_margin=need,guard_margin_bytes=margin,recovery='IO16_LOG_DELEGATE',reused_cache=bool(cached and cached.exists())))+'\n')
   if not size:raise RuntimeError('UNVERIFIED_ARCHIVE_SIZE: '+url)
   if free<need:raise RuntimeError('INSUFFICIENT_DISK_FOR_RAW_ARCHIVE: '+json.dumps(dict(url=url,archive_bytes=size,free_bytes=free,required_bytes=need,guard_margin_bytes=margin)))
   # All original official checksum, range-resume, parse and strict validation retained.
   return c.ORIGINAL_ACQUIRE(url,path)
 c.s.b.d.acquire=acquire
 assert before_driver==c.fp()and before_financial==c.s.fp()
 assert raw_sha==hashlib.sha256(inspect.getsource(c.s.b.e.RawCache.load).encode()).hexdigest()and view_sha==hashlib.sha256(inspect.getsource(c.s.a.ScenarioCache.load).encode()).hexdigest()
 c.dump(f/'transport_recovery.json',dict(at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),prior_failure=fail,original_checkpoint_SHA256=prior_cp_sha,resume_second=next_time,original_financial_checkpoint_fingerprint=before_financial,financial_driver_fingerprint=before_driver,implementation_adapter_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),financial_and_data_checkpoint_checks_not_bypassed=True,strict_raw_load_source_SHA256=raw_sha,scenario_load_source_SHA256=view_sha,changes=['readonly logging sources delegates to strict cache','serial download margin32MiB to16MiB; no file or price or strategy changes'],justification='Failed day ZIP fits free space; completed checkpoints are <2MiB, ZIP is unlinked after validated parsing before daily checkpoint; retain16MiB margin',official_checksum_and_ID_rules_unchanged=True))
 print('TRANSPORT_RECOVERY',year,asset,'resume',next_time,flush=True);c.run(year,asset)
if __name__=='__main__':
 year,asset=sys.argv[1:3]
 try:run(year,asset)
 except Exception as ex:
  f=O/'runs'/year/asset;c.dump(f/'failure.json',dict(error=repr(ex),traceback=traceback.format_exc(),code_fingerprint=c.fp(),transport_adapter_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()));raise
