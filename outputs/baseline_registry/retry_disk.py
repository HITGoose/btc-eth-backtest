from pathlib import Path
import json,subprocess,sys
O=Path(__file__).resolve().parent;results=json.loads((O/'dispatch_results.json').read_text());out=[]
for item in results:
 p=O/'runs'/item['year']/item['asset']/'failure.json'
 if item['returncode']and p.exists()and'INSUFFICIENT_DISK_FOR_RAW_ARCHIVE'in p.read_text():
  log=O/'logs'/f"{item['year']}_{item['asset']}_serial_retry.log"
  with log.open('a')as f:
   cmd=[sys.executable,str(O/'compare_runner.py'),item['year'],item['asset']];f.write('COMMAND '+repr(cmd)+'\n');f.flush();r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
  out.append(dict(year=item['year'],asset=item['asset'],returncode=r.returncode,log=str(log.relative_to(O))));print('SERIAL_RETRY',item['year'],item['asset'],r.returncode,flush=True)
(O/'serial_retry_results.json').write_text(json.dumps(out,indent=2))
