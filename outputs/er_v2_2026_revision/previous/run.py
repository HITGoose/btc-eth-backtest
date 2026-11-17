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
 if not manifest.exists():
  archives={}
  for asset in ['BTC','ETH']:
   name=f'{asset}USDT-trades-2026-10-29.zip';url=f'https://data.binance.vision/data/futures/um/daily/trades/{asset}USDT/{name}'
   with urllib.request.urlopen(url+'.CHECKSUM',timeout=60)as r:raw=r.read()
   text=raw.decode();h=text.split()[0].lower();assert len(h)==64 and name in text
   with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=60)as r:headers=dict(r.headers);assert int(r.headers.get('Content-Length',0))>0
   archives[asset]=dict(url=url,sha256=h,old_sha256=revision.OLD[asset],checksum_response=text,headers=headers)
  c.dump(manifest,dict(mode='SEPARATE_2026_OFFICIAL_REVISION',acquired_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),archives=archives,freeze_sha256=FREEZE_SHA,old_2026_results_or_checkpoints_reused=False))
 else:
  q=json.loads(manifest.read_text());assert q['freeze_sha256']==FREEZE_SHA
 # Preserve the exact two new archives on Drive; never overwrite old versions.
 q=json.loads(manifest.read_text())
 if os.environ.get('BTC_DRIVE_DATA'):
  for asset,entry in q['archives'].items():
   url=entry['url'];name=url.rsplit('/',1)[1];print('Verify/download and preserve',name,flush=True);local=c.D.DATA/'archives/daily/trades'/f'{asset}USDT'/name
   if local.exists()and c.digest(local)!=entry['sha256']:local.rename(local.with_name(name+'.preserved.'+c.digest(local)[:12]))
   meta=c.D.acquire(url,local);assert meta['sha256']==entry['sha256'],'Official archive changed again; keep UNVERIFIED'
   dest=Path(os.environ['BTC_DRIVE_DATA'])/'revision_archives'/entry['sha256']/name;dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():assert c.digest(dest)==entry['sha256']
   else:
    temp=dest.with_suffix('.zip.copying');shutil.copy2(local,temp);assert c.digest(temp)==entry['sha256'];temp.replace(dest)
 revision.install(c);c.backup(c.OUT)

def report():
 # Read-only reason correction: numeric directions and end-open identity first.
 src=(c.HERE/'report.py').read_text()
 src=src.replace("signals.get(ident[1])!=ident[0]", "signals.get(ident[1])!={'LONG':1,'SHORT':-1}[ident[0]]")
 old="if kind=='DISAPPEARED':\n      if signals"
 new="if kind=='DISAPPEARED':\n      pos=(q.get('state_at_end')or{}).get('position');order=(pos or{}).get('order',{});end_identity=(('LONG'if order.get('side')==1 else'SHORT'),order.get('signal_close_ms'))\n      if pos and end_identity==ident:reason='REFERENCE_CLOSED_VARIANT_STILL_OPEN'\n      elif signals"
 assert old in src;src=src.replace(old,new)
 module={};exec(compile(src,str(c.HERE/'report.py'),'exec'),module);module['refresh']()
 for name in ['annual.csv','trade_matching.csv','REPORT.md']:assert(c.OUT/name).is_file()
 with(c.OUT/'REPORT.md').open('a')as f:f.write('\n2026使用单独官方日档修订快照，全部2026账户重新回放；原2020—2025与训练冻结复用。不得与旧2026结果混称同数据复现。归因数值方向比较及期末未平身份已作只读修正。\n')
 c.backup(c.OUT)

def execute(stage,keys,workers):
 from catalog import canonical
 tasks=[]
 for asset in ['BTC','ETH']:
  ks=list(dict.fromkeys(canonical(k,asset)for k in keys));ks=[k for k in ks if not c.existing(k,2026,asset)]
  if ks:tasks.append((asset,ks))
 print('2026 STAGE',stage,'new asset tasks',len(tasks),flush=True)
 def task(t):
  a,ks=t;log=c.OUT/'runner_logs'/f'{stage}_{a}.txt';log.parent.mkdir(exist_ok=True)
  with log.open('a')as f:p=subprocess.run([sys.executable,'-u',str(HERE/'worker.py'),'2026',a,*ks],stdout=f,stderr=subprocess.STDOUT)
  return a,p.returncode,log
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
  pending={pool.submit(task,t):t for t in tasks}
  while pending:
   done,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    pending.pop(future);a,code,log=future.result();print(stage,a,'OK'if not code else'FAILED',log,flush=True)
   if not done:
    for a,ks in pending.values():
     p=c.OUT/'tasks/2026'/a/('-'.join(ks))/'whole/progress.json'
     print(stage,a,p.read_text()if p.exists()else'preparing official data',flush=True)
 report()
 import csv
 with(c.OUT/'annual.csv').open(encoding='utf-8-sig')as f:
  for row in csv.DictReader(f):
   if row.get('year')=='2026'and row.get('asset')=='COMBINED'and row.get('completed')=='True':print(row['group'],row['return_pct'],row['minute_max_drawdown_pct'],row['difference_vs_reference'],flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--prepare-only',action='store_true');p.add_argument('--short',action='store_true');p.add_argument('--report-only',action='store_true');args=p.parse_args()
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
