"""Only 8h real tick test, then resume same completed short checkpoint."""
import subprocess,sys,os,json,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;OUT=Path(os.environ['BTC_OUTPUT_ROOT'])
subprocess.run([sys.executable,str(HERE/'smoke_checks.py')],check=True)
cmd=[sys.executable,str(HERE/'run.py'),'2020','ETH','--hours','8'];subprocess.run(cmd,check=True)
folder=OUT/'smoke/2020/ETH';first=json.loads((folder/'status.json').read_text());shutil.copy2(folder/'status.json',folder/'first_smoke_timing.json')
subprocess.run(cmd+['--resume-probe'],check=True);resumed=json.loads((folder/'status.json').read_text());shutil.copy2(folder/'status.json',folder/'resume_smoke_timing.json')
assert 'RESUME'in(folder/'execution.log').read_text();print('8h real replay and fingerprint-checked checkpoint resume PASS')
print(json.dumps(dict(first_run=first,resume=resumed),indent=2))
print('Cached run CPU/wall ratio:',round(first.get('cpu_seconds',0)/max(first['elapsed_seconds'],.001),2),'; inspect phase times. No GPU logic. Cold downloads can dominate a new Colab session.')
