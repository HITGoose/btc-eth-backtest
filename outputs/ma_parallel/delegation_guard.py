"""Worker-start delegation gate. No strategy modules or account state are modified."""
from pathlib import Path
import os,sys,json,time,hashlib,shutil

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def copy_account(source,target,expected_fp,manifest_sha,year,asset,key):
 status=source/'status.json'
 if not status.is_file():return False
 assert sha(source.parents[3]/'data_revision.json')==manifest_sha,'Parallel data manifest mismatch'
 st=json.loads(status.read_text())
 assert st.get('complete')and st['fingerprint']==expected_fp,'Parallel fingerprint mismatch'
 assert sha(source/'result.json')==st['result_SHA256']and sha(source/'equity.npz')==st['equity_SHA256'],'Parallel file SHA mismatch'
 q=json.loads((source/'result.json').read_text());cfg=json.loads((source/'config.json').read_text())
 assert q['asset']==asset and q['period']==str(year)and q['V2']is False and q['baseline']=='MA_DIRECTION_REFERENCE'
 assert q['retest_fingerprint']==expected_fp and cfg['fingerprint']==expected_fp
 assert not any(e.get('event')in ['adaptive_v2_request','partial_exit','partial_exit_requested']for e in q['events'])
 if(target/'status.json').is_file():
  old=json.loads((target/'status.json').read_text());assert old['result_SHA256']==st['result_SHA256']and old['equity_SHA256']==st['equity_SHA256'],'Different existing result; preserve both'
  return True
 target.mkdir(parents=True,exist_ok=True)
 for name in ['result.json','equity.npz','config.json','signals.json']:
  p=source/name;tmp=target/(name+'.parallel_copying');shutil.copy2(p,tmp);tmp.replace(target/name)
 receipt=dict(parallel_source=str(source),fingerprint=expected_fp,data_manifest_sha256=manifest_sha,financial_replay_in_main=False)
 (target/'parallel_receipt.json').write_text(json.dumps(receipt,indent=2))
 st=dict(st,source='VERIFIED_PARALLEL_STAGE');tmp=target/'status.json.parallel_copying';tmp.write_text(json.dumps(st,indent=2));tmp.replace(target/'status.json')
 return True

def maybe_delegate():
 if len(sys.argv)<4 or not sys.argv[0].endswith('/outputs/ma_direction_resume/worker.py')or'--hours'in sys.argv:return
 year=int(sys.argv[1]);asset=sys.argv[2];keys=sys.argv[3:]
 stage=10 if keys and set(keys)<=set(['BTC_CONFIRM','CORE_PRIORITY','BOTH100','BOTH50','BOTH25'])else 11 if keys==['REBOUND']else None
 if not stage:return
 main=Path(os.environ['BTC_OUTPUT_ROOT']);plan=main/f'delegate_stage{stage}.json'
 if not plan.exists():return
 q=json.loads(plan.read_text());assert q['stage']==stage and q['baseline']=='MA_DIRECTION_REFERENCE'and q['V2']is False
 assert sha(main/'data_revision.json')==q['data_manifest_sha256'],'Main data manifest differs from parallel plan'
 source=Path(q['parallel_drive_results']);deadline=time.monotonic()+24*3600;last=''
 while time.monotonic()<deadline:
  try:
   ok=True
   for key in keys:ok=copy_account(source/'runs'/key/str(year)/asset,main/'imported'/key/str(year)/asset,q['fingerprint'],q['data_manifest_sha256'],year,asset,key)and ok
   if ok:
    print('DELEGATED_COMPLETE',stage,year,asset,keys,'NO_DUPLICATE_REPLAY',flush=True);sys.stdout.flush();os._exit(0)
   state=source/'parallel_state.json'
   if state.exists()and json.loads(state.read_text()).get('status')=='FAILED':raise RuntimeError('Parallel stage failed; inspect its notebook')
  except (OSError,ValueError,KeyError,AssertionError)as error:last=str(error)
  task=main/'tasks'/str(year)/asset/('-'.join(keys))/'whole';task.mkdir(parents=True,exist_ok=True)
  tmp=task/'progress.json.parallel_copying';tmp.write_text(json.dumps(dict(next_time=f'WAITING_PARALLEL_STAGE_{stage}',year=year,asset=asset,reason=last)));tmp.replace(task/'progress.json')
  print('DELEGATED_WAIT',stage,year,asset,last,flush=True);time.sleep(30)
 raise RuntimeError('Parallel wait exceeded 24h; no duplicate financial calculation started')
