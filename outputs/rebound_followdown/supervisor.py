from pathlib import Path
import subprocess,sys,json,datetime
from counts import WINDOWS
O=Path(__file__).resolve().parent
rows=[]
for y,_,_ in WINDOWS:
 for a in ['BTC','ETH']:
  with (O/f'{y}_{a}.log').open('w')as out:
   rc=subprocess.run([sys.executable,str(O/'run.py'),y,a],stdout=out,stderr=subprocess.STDOUT).returncode
  rows.append(dict(period=y,asset=a,returncode=rc,finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()));(O/'execution.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
