"""Autonomous Colab stages, no assistant polling. Resume same frozen code/config."""
import common as c
from catalog import SPECS,canonical,STAGES
import report,freeze
from pathlib import Path
import subprocess,sys,json,concurrent.futures,os
import psutil

def jobs(keys,years):
 out=[]
 for y in years:
  for asset in ['BTC','ETH']:
   wanted=list(dict.fromkeys(canonical(k,asset)for k in keys));wanted=[k for k in wanted if (k!='REF'or keys==['REF'])and not c.existing(k,y,asset)]
   if wanted:out.append((y,asset,wanted))
 return out
def execute(stage,tasks):
 available=psutil.virtual_memory().available/2**30;automatic=max(1,min(4,(os.cpu_count()or 1)//2,int(available//6)));workers=min(automatic,max(1,int(os.environ.get('BTC_WORKERS',automatic))));print('Stage',stage,'new tasks',len(tasks),'CPU workers',workers,flush=True)
 def one(task):
  y,a,ks=task;cmd=[sys.executable,str(c.HERE/'worker.py'),str(y),a,*ks];p=subprocess.run(cmd,capture_output=True,text=True);return dict(year=y,asset=a,keys=ks,returncode=p.returncode,output=(p.stdout+p.stderr)[-3500:])
 outcomes=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
  pending={pool.submit(one,t):t for t in tasks}
  while pending:
   done,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    pending.pop(f);q=f.result();outcomes.append(q);print(stage,len(outcomes),'/',len(tasks),q['year'],q['asset'],'OK'if not q['returncode']else'ERROR',q['output'].strip(),flush=True)
   if not done:
    dates=[]
    for y,a,ks in pending.values():
     p=c.OUT/'tasks'/str(y)/a/('-'.join(ks))/'whole/progress.json'
     if p.exists():
      try:dates.append(f'{y} {a} '+json.loads(p.read_text())['next_time'])
      except (ValueError,OSError):pass
    print('RUNNING',stage, '; '.join(dates[-4:])or'preparing/downloading official data',flush=True)
 c.dump(c.OUT/'stage_logs'/f'{stage}.json',outcomes);c.backup(c.OUT/'stage_logs');return outcomes

def main():
 print('Frozen MA_DIRECTION_REFERENCE, NO V2, ZERO; through BJT Nov15 inclusive.',flush=True)
 execute('BASELINE_2026',jobs(['REF'],[2026]))
 for stage in range(1,12):
  try:
   keys=[k for k,z in SPECS.items()if z['stage']==stage]
   if stage==1:
    execute('1_TRAIN',jobs(['FAIL_EXIT','VOL_SIZE'],[2020,2021,2022]));freeze.save('fixed_low',freeze.fixed());execute('1_EVAL',jobs(['FAIL_EXIT','VOL_SIZE'],[2023,2024,2025,2026]));execute(stage,jobs(['FIXED_LOW'],range(2020,2027)))
   elif stage in (7,8):
    family='B'if stage==7 else'C';execute(str(stage)+'_TRAIN',jobs(keys,[2020,2021,2022]));f=freeze.save('adaptive_'+family,freeze.adaptive(family));execute(str(stage)+'_EVAL',jobs([f[family+'_winner']],[2023,2024,2025,2026]))
   elif stage==9:
    b=json.loads((c.OUT/'freeze_adaptive_B.json').read_text());d=json.loads((c.OUT/'freeze_adaptive_C.json').read_text());rows=[next(r for r in b['B_scores']if r['key']==b['B_winner']),next(r for r in d['C_scores']if r['key']==d['C_winner'])];choice=sorted(rows,key=lambda r:(-r['score'],r['worst_drawdown'],r['total_fills'],r['preset_index']))[0];freeze.save('adaptive_D',dict(D_source=choice['key'],selected_between_frozen_families=True));execute(stage,jobs(keys,range(2020,2027)))
   else:execute(stage,jobs(keys,range(2020,2027)))
  except Exception as error:
   c.dump(c.OUT/'stage_logs'/f'{stage}_blocked.json',dict(error=repr(error),stage=stage,rule='continue independent stages; no invented freeze or zero result'));print('STAGE_BLOCKED',stage,repr(error),flush=True)
  report.refresh(stage)
 report.refresh();export();print('FINISHED available stages; see incomplete.csv and stage_logs for blockers.',flush=True)
def export():
 import zipfile
 p=c.OUT/'ma_retests_results_for_review.zip'
 with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED)as z:
  for f in c.OUT.rglob('*'):
   if f.is_file()and f!=p and f.name!='checkpoint.pkl.gz'and'temporary'not in f.parts and f.suffix not in ['.zip','.part','.tmp']:z.write(f,f.relative_to(c.OUT))
 import hashlib
 with zipfile.ZipFile(p)as check:
  bad=check.testzip()
  if bad:raise RuntimeError('Export CRC failed: '+bad)
 receipt=dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),zip_crc='PASS')
 c.dump(c.OUT/'export_receipt.json',receipt);print('ZIP VERIFIED',receipt,flush=True)
 c.backup(c.OUT)
 if os.environ.get('BTC_DRIVE_RESULTS'):
  import shutil
  dest=c.Path(os.environ['BTC_DRIVE_RESULTS'])/p.name;temp=dest.with_suffix('.zip.copying');shutil.copy2(p,temp);temp.replace(dest)
if __name__=='__main__':
 import fcntl
 with(c.OUT/'coordinator.lock').open('a')as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('A coordinator is already running in this output root; do not start duplicate tasks')
  main()
