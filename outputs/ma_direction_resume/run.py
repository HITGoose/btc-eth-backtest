"""Colab-only 2026 recomputation. Reuse years 2020-2025; retain original freeze."""
from pathlib import Path
import sys,os,json,hashlib,shutil,subprocess,argparse,urllib.request,datetime,fcntl,concurrent.futures,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'ma_direction_retests'))
import common as c
sys.path.insert(0,str(HERE))
import revision
def prepare(source):
 source=Path(source);assert source.is_dir(),'Original MA Drive results missing'
 snapshot=json.loads((HERE/'official_preflight.json').read_text());pins={a:{}for a in ['BTC','ETH']}
 for asset in pins:
  old=json.loads((c.ROOT/f'outputs/baseline_registry/runs/2026/{asset}/raw_sources.json').read_text())
  pins[asset].update({day:dict(sha256=entry['sha256'])for day,entry in old.items()if day<'2026-10-29'})
 for row in snapshot['rows']:
  assert row.get('zip_status')==200 and row.get('checksum_status')==200 and not row.get('error')
  pins[row['asset']][row['day']]=dict(sha256=row['current_sha256'],url=row['url'])
 q=dict(mode='AUDITED_TAIL_REVISION_WITH_COMPATIBLE_STATE_MIGRATION',baseline='MA_DIRECTION_REFERENCE',V2=False,pins=pins,official_preflight_sha256=c.digest(HERE/'official_preflight.json'))
 manifest=c.OUT/'data_revision.json'
 if manifest.exists():assert json.loads(manifest.read_text())==q,'Data snapshot differs; do not overwrite'
 else:c.dump(manifest,q)
 revision.install(c)
 import migration
 oldfp=migration.old_fingerprint(c)
 preflight_data();migration.reuse_completed(c)
 for p in source.glob('freeze_*.json'):
  old=json.loads(p.read_text());assert old['fingerprint']==oldfp and old['V2']is False and old['fee']==0 and old['training_years']==[2020,2021,2022]
  q=dict(old,fingerprint=c.fingerprint());dest=c.OUT/p.name
  if dest.exists():assert json.loads(dest.read_text())==q
  else:c.dump(dest,q)
  c.dump(c.OUT/'freeze_migration'/p.name,dict(original_sha256=c.digest(p),old_fingerprint=oldfp,new_fingerprint=c.fingerprint(),parameters_unchanged=True))
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
 with(c.OUT/'REPORT.md').open('a')as f:f.write('\n2026使用完整尾段官方SHA清单；兼容旧断点经代码、输入、配置、已用数据和完整账户/权益核验后迁移，兼容已完成账户复用。原MA已完成账户与训练冻结复用。不得与旧2026结果混称同数据复现。归因数值方向比较及期末未平身份已作只读修正。\n')
 c.backup(c.OUT)

def execute(stage,keys,workers,years=(2026,)):
 from catalog import canonical
 tasks=[]
 for year in years:
  for asset in ['BTC','ETH']:
   ks=list(dict.fromkeys(canonical(k,asset)for k in keys))
   if keys!=['REF']:ks=[k for k in ks if k!='REF']
   if any(not c.existing(k,year,asset)for k in ks):tasks.append((year,asset,ks))
 print('2026 STAGE',stage,'new asset tasks',len(tasks),flush=True)
 def task(t):
  year,a,ks=t;log=c.OUT/'runner_logs'/f'{stage}_{year}_{a}.txt';log.parent.mkdir(exist_ok=True)
  previous=Path(os.environ['BTC_REVISION_PREVIOUS'])/'tasks'/str(year)/a/('-'.join(ks))/'whole/progress.json'
  if previous.exists():print('FOUND_PREVIOUS_CHECKPOINT_VERIFY_FIRST',a,'-'.join(ks),previous.read_text(),flush=True)
  with log.open('a')as f:p=subprocess.run([sys.executable,'-u',str(HERE/'worker.py'),str(year),a,*ks],stdout=f,stderr=subprocess.STDOUT)
  execution=c.OUT/'tasks'/str(year)/a/('-'.join(ks))/'execution.log'
  if execution.exists():
   lines=[line for line in execution.read_text().splitlines()if 'AUDITED_RESUME'in line or line.startswith('RESUME ')or line.startswith('RUN_OR_RESUME')]
   for line in lines[-3:]:print(line,flush=True)
  return str(year)+' '+a,p.returncode,log
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
    for year,a,ks in pending.values():
     p=c.OUT/'tasks'/str(year)/a/('-'.join(ks))/'whole/progress.json'
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
  import freeze
  execute('BASELINE',['REF'],workers)
  for stage in range(1,12):
   keys=[k for k,z in SPECS.items()if z['stage']==stage]
   if stage==1:
    execute('1_TRAIN',['FAIL_EXIT','VOL_SIZE'],workers,[2020,2021,2022]);freeze.save('fixed_low',freeze.fixed())
    execute('1_EVAL',['FAIL_EXIT','VOL_SIZE'],workers,[2023,2024,2025,2026]);execute(1,['FIXED_LOW'],workers,range(2020,2027))
   elif stage in (7,8):
    family='B'if stage==7 else'C';execute(str(stage)+'_TRAIN',keys,workers,[2020,2021,2022]);f=freeze.save('adaptive_'+family,freeze.adaptive(family));execute(str(stage)+'_EVAL',[f[family+'_winner']],workers,[2023,2024,2025,2026])
   elif stage==9:
    b=json.loads((c.OUT/'freeze_adaptive_B.json').read_text());d=json.loads((c.OUT/'freeze_adaptive_C.json').read_text());scores=[next(r for r in b['B_scores']if r['key']==b['B_winner']),next(r for r in d['C_scores']if r['key']==d['C_winner'])];choice=sorted(scores,key=lambda r:(-r['score'],r['worst_drawdown'],r['total_fills'],r['preset_index']))[0];freeze.save('adaptive_D',dict(D_source=choice['key'],selected_between_frozen_families=True));execute(stage,keys,workers,range(2020,2027))
   else:execute(stage,keys,workers,range(2020,2027))
  print('FINISHED. Check incomplete.csv; failed accounts are not zero.',flush=True)
if __name__=='__main__':main()
