from pathlib import Path
import importlib.util,sys,json,subprocess
from concurrent.futures import ThreadPoolExecutor
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent/'baseline'
def run(year,asset):
 sp=importlib.util.spec_from_file_location('locked_v2_baseline',ROOT/'outputs/adaptive_risk_exit_v2/worker.py');v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v);v.OUT=OUT;v.original_worker.OUT=OUT;v.run(year,asset)
 folder=OUT/str(year)/asset;original=ROOT/f'outputs/adaptive_risk_exit_v2/{year}/{asset}'
 for name in ('CONTROL','DYNAMIC'):
  a=json.loads((folder/f'{name}_result.json').read_text());b=json.loads((original/f'{name}_result.json').read_text())
  assert a['trades']==b['trades'],(year,asset,name,'trade mismatch')
  assert abs(a['ending_equity']-b['ending_equity'])<1e-7
 (folder/'regression.json').write_text(json.dumps(dict(passed=True,exact_trades_equal=True,equity_tolerance=1e-7,reference=str(original))))
 print('REGRESSION_PASS',year,asset,flush=True)
def child(job):
 y,a=job;f=OUT/str(y)/a;f.mkdir(parents=True,exist_ok=True)
 with (f/'run.log').open('w') as log:r=subprocess.run([sys.executable,__file__,str(y),a],stdout=log,stderr=subprocess.STDOUT)
 print(y,a,r.returncode,flush=True);return r.returncode
if __name__=='__main__':
 if len(sys.argv)>1:run(int(sys.argv[1]),sys.argv[2])
 else:
  assert json.loads((OUT.parent/'validation32/test_results.json').read_text())['failed']==0
  with ThreadPoolExecutor(max_workers=4) as p:codes=list(p.map(child,[(y,a)for y in (2024,2025)for a in ('BTC','ETH')]))
  (OUT/'status.json').write_text(json.dumps(dict(passed=not any(codes),codes=codes)))
  sys.exit(1 if any(codes) else 0)
