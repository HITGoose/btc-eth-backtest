"""Colab-only 2026 recomputation. Reuse years 2020-2025; retain original freeze."""
from pathlib import Path
import sys,os,json,hashlib,shutil,subprocess,argparse,urllib.request,datetime,fcntl,concurrent.futures,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'er_v2_retests'))
import common as c
sys.path.insert(0,str(HERE))
import revision
FREEZE_SHA={'fixed_low':'8c38ea1504cf91b105c187f178b7087f4cfb7c32b48eab40f532885ec547440d','adaptive_B':'5a9ed44204ef0afb5b41396ff956d0f72b3983df1263bc823447f31ca961855f','adaptive_C':'5b9556645a6e5a5438d391140c50839e1c62ae7493d81b2cb1a80d358b133e17','adaptive_D':'0ce34ae687565bb0ea5d4e1b9c3b9c4991c55a9e60454c2d4adb8295dbd0887c'}
def prepare(source):
 source=Path(source);assert source.is_dir(), 'Original Drive result directory missing'
 for name,h in FREEZE_SHA.items():
  p=source/f'freeze_{name}.json';assert c.digest(p)==h,('Original freeze changed',p)
  dest=c.OUT/p.name
  if dest.exists():assert dest.read_bytes()==p.read_bytes()
  else:shutil.copy2(p,dest)
 for base in ['runs','imported']:
  for st in (source/base).glob('*/*/*/status.json'):
   key,year,asset=st.parent.relative_to(source/base).parts
   if int(year)==2026:continue
   assert 2020<=int(year)<=2025
   q=json.loads(st.read_text())
   if not q.get('complete'):continue
   for name,field in [('result.json','result_SHA256'),('equity.npz','equity_SHA256')]:assert c.digest(st.parent/name)==q[field]
   dst=c.OUT/'imported'/key/year/asset;dst.mkdir(parents=True,exist_ok=True)
   for p in st.parent.iterdir():
    if p.is_file()and p.suffix in ['.json','.npz']:
     t=dst/p.name
     if t.exists():assert c.digest(t)==c.digest(p)
     else:shutil.copy2(p,t)
 manifest=c.OUT/'data_revision.json'
 snapshot=json.loads((HERE/'official_preflight.json').read_text());pins={a:{}for a in ['BTC','ETH']}
 for asset in pins:
  old=json.loads((c.ROOT/f'outputs/baseline_registry/reused/ER_V2_REFERENCE/2026/{asset}/raw_sources.json').read_text())
  pins[asset].update({day:dict(sha256=entry['sha256'],basis='ORIGINAL_PIN_BEFORE_TAIL')for day,entry in old.items()if day<'2026-10-29'})
 for row in snapshot['rows']:
  assert row.get('zip_status')==200 and row.get('checksum_status')==200 and not row.get('error')
  pins[row['asset']][row['day']]=dict(sha256=row['current_sha256'],url=row['url'],basis='OFFICIAL_TAIL_CHECKSUM_SNAPSHOT')
 q=dict(mode='AUDITED_TAIL_REVISION_WITH_COMPATIBLE_STATE_MIGRATION',official_preflight_sha256=c.digest(HERE/'official_preflight.json'),pins=pins,freeze_sha256=FREEZE_SHA,old_2026_reused_only_after_full_compatibility_audit=True)
 if manifest.exists():assert json.loads(manifest.read_text())==q,'Different snapshot: preserve directory, do not overwrite'
 else:c.dump(manifest,q)
 revision.install(c)
 import migration
 migration.old_fingerprint(c) # proves original source/manifest available before expensive downloads
 preflight_data()
 migration.reuse_completed(c)
 c.backup(c.OUT)

def preflight_data():
 from inputs import prepare as native_prepare
 from datetime import datetime,timezone
 q=json.loads((c.OUT/'data_revision.json').read_text());original=c.s.b.d.acquire
 for asset in ['BTC','ETH']:
  data,m=native_prepare(2026,asset);d=c.s.b.d;d.DATA=data;d.BASE='https://data.binance.vision/data/futures/um';d.START=m['start'];d.END=m['end'];d.FIRST1=m['first1'];native=c.s.b.p.Canonical(asset)
  folder=c.OUT/'data_preflight'/asset;folder.mkdir(parents=True,exist_ok=True);cache=c.w.raw_cache(asset,native,folder)
  def acquire(url,path):
   meta=original(url,path)
   if '/daily/trades/'in url:
    day=path.stem[-10:];assert meta['sha256']==q['pins'][asset][day]['sha256'],('Official archive changed since preflight',asset,day)
   return meta
  c.s.b.d.acquire=acquire
  try:
   for day,entry in q['pins'][asset].items():
    if day<'2026-10-29':continue
    path=c.D.DATA/'archives/daily/trades'/f'{asset}USDT'/f'{asset}USDT-trades-{day}.zip'
    stored=c.D.DATA/'revision_archives'/entry['sha256']/path.name
    if not path.exists()and stored.exists():
     assert c.digest(stored)==entry['sha256'];path.parent.mkdir(parents=True,exist_ok=True);os.link(stored,path)
    marker=folder/f'{day}.validated.json'
    if marker.exists()and path.exists()and c.digest(path)==entry['sha256']:
     assert json.loads(marker.read_text())['manifest_sha256']==c.digest(c.OUT/'data_revision.json');print('PREFLIGHT_ALREADY_VALID',asset,day,flush=True);continue
    if path.exists()and c.digest(path)!=entry['sha256']:path.rename(path.with_name(path.name+'.preserved.'+c.digest(path)[:12]))
    print('PREFLIGHT_DOWNLOAD_AND_PARSE',asset,day,flush=True)
    minute=int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp());cache.load(minute)
    assert cache.sources[day]['sha256']==entry['sha256']
    c.dump(marker,dict(manifest_sha256=c.digest(c.OUT/'data_revision.json'),archive_sha256=entry['sha256'],parsed_source=cache.sources[day]))
    if os.environ.get('BTC_DRIVE_DATA'):
     dest=Path(os.environ['BTC_DRIVE_DATA'])/'revision_archives'/entry['sha256']/path.name;dest.parent.mkdir(parents=True,exist_ok=True)
     if not dest.exists():
      tmp=dest.with_suffix('.zip.copying');shutil.copy2(path,tmp);assert c.digest(tmp)==entry['sha256'];tmp.replace(dest)
     else:assert c.digest(dest)==entry['sha256']
    c.backup(folder)
  finally:c.s.b.d.acquire=original
  c.dump(folder/'COMPLETE.json',dict(manifest_sha256=c.digest(c.OUT/'data_revision.json'),all_tail_archives_parsed=True))
 print('DATA_PREFLIGHT_ALL_36_ARCHIVES_PASS',flush=True)

def report():
 # Read-only reason correction: numeric directions and end-open identity first.
 src=(c.HERE/'report.py').read_text()
 src=src.replace("signals.get(ident[1])!=ident[0]", "signals.get(ident[1])!={'LONG':1,'SHORT':-1}[ident[0]]")
 old="if kind=='DISAPPEARED':\n      if signals"
 new="if kind=='DISAPPEARED':\n      pos=(q.get('state_at_end')or{}).get('position');order=(pos or{}).get('order',{});end_identity=(('LONG'if order.get('side')==1 else'SHORT'),order.get('signal_close_ms'))\n      if pos and end_identity==ident:reason='REFERENCE_CLOSED_VARIANT_STILL_OPEN'\n      elif signals"
 assert old in src;src=src.replace(old,new)
 module={};exec(compile(src,str(c.HERE/'report.py'),'exec'),module);module['refresh']()
 for name in ['annual.csv','trade_matching.csv','REPORT.md']:assert(c.OUT/name).is_file()
 with(c.OUT/'REPORT.md').open('a')as f:f.write('\n2026使用完整尾段官方SHA清单；兼容旧断点经代码、输入、配置、已用数据和完整账户/权益核验后迁移，兼容已完成账户复用。原2020—2025与训练冻结复用。不得与旧2026结果混称同数据复现。归因数值方向比较及期末未平身份已作只读修正。\n')
 c.backup(c.OUT)

def execute(stage,keys,workers):
 from catalog import canonical
 tasks=[]
 for asset in ['BTC','ETH']:
  ks=list(dict.fromkeys(canonical(k,asset)for k in keys))
  if any(not c.existing(k,2026,asset)for k in ks):tasks.append((asset,ks))
 print('2026 STAGE',stage,'new asset tasks',len(tasks),flush=True)
 def task(t):
  a,ks=t;log=c.OUT/'runner_logs'/f'{stage}_{a}.txt';log.parent.mkdir(exist_ok=True)
  previous=Path(os.environ['BTC_REVISION_PREVIOUS'])/'tasks/2026'/a/('-'.join(ks))/'whole/progress.json'
  if previous.exists():print('FOUND_PREVIOUS_CHECKPOINT_VERIFY_FIRST',a,'-'.join(ks),previous.read_text(),flush=True)
  with log.open('a')as f:p=subprocess.run([sys.executable,'-u',str(HERE/'worker.py'),'2026',a,*ks],stdout=f,stderr=subprocess.STDOUT)
  execution=c.OUT/'tasks/2026'/a/('-'.join(ks))/'execution.log'
  if execution.exists():
   lines=[line for line in execution.read_text().splitlines()if 'AUDITED_RESUME'in line or line.startswith('RESUME ')or line.startswith('RUN_OR_RESUME')]
   for line in lines[-3:]:print(line,flush=True)
  return a,p.returncode,log
 failures=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
  pending={pool.submit(task,t):t for t in tasks}
  while pending:
   done,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    pending.pop(future);a,code,log=future.result();print(stage,a,'OK'if not code else'FAILED',log,flush=True)
    if code:
     failures.append((a,str(log)));print(log.read_text()[-2500:],flush=True)
   if not done:
    for a,ks in pending.values():
     p=c.OUT/'tasks/2026'/a/('-'.join(ks))/'whole/progress.json'
     print(stage,a,p.read_text()if p.exists()else'preparing official data',flush=True)
 report()
 import csv
 with(c.OUT/'annual.csv').open(encoding='utf-8-sig')as f:
  for row in csv.DictReader(f):
   if row.get('year')=='2026'and row.get('asset')=='COMBINED'and row.get('completed')=='True':print(row['group'],row['return_pct'],row['minute_max_drawdown_pct'],row['difference_vs_reference'],flush=True)
 if failures:raise RuntimeError('Stage failed; stopped before later stages. Check the displayed error: '+str(failures))

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--prepare-only',action='store_true');p.add_argument('--short',action='store_true');p.add_argument('--report-only',action='store_true');p.add_argument('--previous',required=True);args=p.parse_args();os.environ['BTC_REVISION_PREVIOUS']=args.previous
 with(c.OUT/'revision_coordinator.lock').open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if args.report_only:
   revision.install(c);report();return
  prepare(args.source)
  if args.prepare_only:print('PREPARED. No financial replay started.');return
  if args.short:
   env=os.environ.copy();env['BTC_OUTPUT_ROOT']=str(c.OUT/'short_validation');env.pop('BTC_DRIVE_RESULTS',None);dest=Path(env['BTC_OUTPUT_ROOT']);dest.mkdir(exist_ok=True)
   for p in c.OUT.glob('freeze_*.json'):shutil.copy2(p,dest/p.name)
   shutil.copy2(c.OUT/'data_revision.json',dest/'data_revision.json')
   subprocess.run([sys.executable,'-u',str(HERE/'worker.py'),'2026','ETH','REF','CANCEL','--hours','8'],env=env,check=True);print('8h short only PASS');return
  import psutil
  workers=max(1,min(2,int(psutil.virtual_memory().available/2**30//6),(os.cpu_count()or 1)//2))
  from catalog import SPECS
  freezes={}
  for p in c.OUT.glob('freeze_*.json'):freezes.update(json.loads(p.read_text()))
  execute('BASELINE',['REF'],workers)
  for stage in range(1,12):
   keys=[k for k,z in SPECS.items()if z['stage']==stage]
   if stage==7:keys=[freezes['B_winner']]
   if stage==8:keys=[freezes['C_winner']]
   execute(stage,keys,workers)
  print('FINISHED. Check incomplete.csv; failed accounts are not zero.',flush=True)
if __name__=='__main__':main()
