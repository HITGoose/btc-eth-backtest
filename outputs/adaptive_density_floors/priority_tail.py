from pathlib import Path
import subprocess,time
O=Path(__file__).resolve().parent;PY='/workspace/.venv-btc-eth-original/bin/python'
while not(O/'runs/2026/ETH/status.json').exists():time.sleep(5)
for y,a in [('2026','BTC'),('2025','ETH')]:
 with(O/f'{y}_{a}_priority.log').open('a')as f:
  r=subprocess.run([PY,str(O/'experiment.py'),y,a],stdout=f,stderr=subprocess.STDOUT)
 print('FINISHED',y,a,r.returncode,flush=True);subprocess.run([PY,str(O/'report.py')])
