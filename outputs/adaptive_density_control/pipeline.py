from pathlib import Path
import json,sys,subprocess,time,datetime
O=Path(__file__).resolve().parent
print('WAITING_FOR_TRAINING_ONLY',flush=True)
while True:
 ready=all((O/'runs/train'/y/a/'status.json').exists()for y in ['2020','2021','2022']for a in ['BTC','ETH'])
 if ready:break
 if(O/'training_execution.json').exists():
  rows=json.loads((O/'training_execution.json').read_text())
  if len(rows)==6 and any(r['returncode'] for r in rows):
   # The known initial import-name failure has already been repaired; require
   # the latest attempt log to have concluded before declaring a blocker.
   if(O/'train_supervisor_true.log').exists()and len((O/'train_supervisor_true.log').read_text().splitlines())>=6:
    (O/'pipeline_blocked.json').write_text(json.dumps(dict(reason='Training incomplete; do not select on missing periods',time_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2));raise SystemExit(2)
 time.sleep(2)
r=subprocess.run([sys.executable,str(O/'freeze.py')]);assert r.returncode==0
r=subprocess.run([sys.executable,'-u',str(O/'final_supervisor.py')]);print('FINAL_STAGE_FINISHED',r.returncode,flush=True)

r=subprocess.run([sys.executable,'-u',str(O/'report.py')]);print('REPORT_FINISHED',r.returncode,flush=True)
