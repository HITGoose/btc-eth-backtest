from pathlib import Path
import json,subprocess,sys
O=Path(__file__).resolve().parent;results=[]
for year in range(2020,2027):
 for asset in ['BTC','ETH']:
  f=O/'runs'/str(year)/asset
  if(f/'status.json').exists():continue
  p=f/'failure.json'
  if not p.exists():continue
  err=json.loads(p.read_text())['error']
  if not('INSUFFICIENT_DISK_FOR_RAW_ARCHIVE'in err or('ScenarioCache'in err and'sources'in err)):continue
  log=O/'logs'/f'{year}_{asset}_transport_recovery.log'
  with log.open('a')as h:
   cmd=[sys.executable,str(O/'recover_transport.py'),str(year),asset];h.write('COMMAND '+repr(cmd)+'\n');h.flush();r=subprocess.run(cmd,stdout=h,stderr=subprocess.STDOUT)
  results.append(dict(year=year,asset=asset,returncode=r.returncode,log=str(log.relative_to(O))));print('RECOVERY_RESULT',year,asset,r.returncode,flush=True)
(O/'transport_recovery_results.json').write_text(json.dumps(results,indent=2))
