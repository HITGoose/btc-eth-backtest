"""Scheduling-only continuation: leave already-running account workers intact."""
from pathlib import Path
import os,signal,sys,subprocess,json,time,datetime
import validate_baselines as validation
O=Path(__file__).resolve().parent;PARENT=63804
external={('2026','ETH'):64017}
# Freeze only old dispatch threads, never the two financial workers.
os.kill(PARENT,signal.SIGSTOP)
(O/'scheduler_transition2.json').write_text(json.dumps(dict(old_dispatch_pid=PARENT,unchanged_running_workers=[dict(period=y,asset=a,pid=p)for(y,a),p in external.items()],financial_worker_source_unchanged=True,maximum_non_S_ALL_workers=3,initial_memory_bytes=int(Path('/sys/fs/cgroup/memory.current').read_text()),reason='reuse in-flight workers; improve wall time without duplicate accounts',time_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2))
rows=json.loads((O/'execution.json').read_text());active={k:dict(pid=p,external=True)for k,p in external.items()};pending=[('2025','BTC')];last=[('2025','ETH')];handles=[];parent_killed=False

def running(pid):
 p=Path(f'/proc/{pid}/status')
 if not p.exists():return False
 try:return '\nState:\tZ'not in p.read_text()
 except FileNotFoundError:return False
while active or pending or last:
 for k,v in list(active.items()):
  rc=None
  if v.get('external'):
   if running(v['pid']):continue
  else:
   rc=v['process'].poll()
   if rc is None:continue
  y,a=k
  try:verified=validation.validate(y,a);err=None
  except Exception as e:verified=False;err=repr(e)
  row=dict(period=y,asset=a,returncode=rc,baseline_verified=verified,error=err,finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),external_existing_worker=v.get('external',False));rows.append(row);active.pop(k);(O/'execution.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
 if not parent_killed and not any(v.get('external')for v in active.values()):
  try:os.kill(PARENT,signal.SIGKILL)
  except ProcessLookupError:pass
  parent_killed=True
 while pending and len(active)<3 and int(Path('/sys/fs/cgroup/memory.current').read_text())<4_000_000_000:
  k=pending.pop(0);y,a=k;f=(O/f'{y}_{a}.log').open('a');handles.append(f);p=subprocess.Popen([sys.executable,'-u',str(O/'worker.py'),y,a],stdout=f,stderr=subprocess.STDOUT);active[k]=dict(process=p,pid=p.pid,external=False);print('LAUNCH',y,a,p.pid,flush=True)
 if not active and not pending and last:
  k=last.pop(0);y,a=k;f=(O/f'{y}_{a}.log').open('a');handles.append(f);p=subprocess.Popen([sys.executable,'-u',str(O/'worker.py'),y,a],stdout=f,stderr=subprocess.STDOUT);active[k]=dict(process=p,pid=p.pid,external=False);print('LAUNCH_SERIAL',y,a,p.pid,flush=True)
 if active or pending or last:time.sleep(1)
(O/'dispatch_complete.json').write_text(json.dumps(dict(completed=True,all_14_attempted=len(rows)==14,rows=len(rows)),indent=2));print('ALL_DONE',len(rows),flush=True)
