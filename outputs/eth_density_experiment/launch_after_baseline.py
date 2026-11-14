from pathlib import Path
import time,json,subprocess,sys
OUT=Path(__file__).resolve().parent
while not (OUT/'baseline/status.json').exists():time.sleep(15)
assert json.loads((OUT/'baseline/status.json').read_text())['passed'],'Baseline mismatch: experiments blocked'
assert json.loads((OUT/'financial_tests.json').read_text())['passed']
raise SystemExit(subprocess.call([sys.executable,'-u',str(OUT/'supervisor.py')]))
