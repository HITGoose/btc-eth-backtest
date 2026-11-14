"""Load exactly the sealed parent without ambiguous legacy module imports."""
from pathlib import Path
import importlib.util,sys,json,hashlib
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent;PARENT=ROOT/'outputs/eth_core_priority'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
z=module('sensitivity_parent_strategy',PARENT/'strategy.py');sys.modules['strategy']=z
pe=module('priority_engine',PARENT/'priority_engine.py')
w=module('sensitivity_parent_worker',PARENT/'worker.py')
e=z.e;r=z.r;p=z.p;d=z.d
BASE_COMMIT='17366bb41b11ca82e3084f2f042c09e00b160234'
EXPECTED_SHA='053164460ed94f8b586ffd2e2d01e85612e752031f06b7d51776f27c7f6aa9db'
DAY='2025-08-29';ASSET='ETH';SYMBOL='ETHUSDT';IDS=(6299136398,6299136399,6299136400)
SCENARIOS=['S_ALL']+['S_'+format(i,'03b')for i in range(8)]
ARCHIVE=ROOT/'outputs/eth_density_experiment/runs/2025/ETH/temporary/ETHUSDT-trades-2025-08-29.zip'
PARENT_FP='fda92bd02091def33bcb6eefa9466e0f22e1447397bbb5975ca6159bace396bc'
def verify_parent():
 cfg=json.loads((PARENT/'frozen_config.json').read_text())
 manifest=json.loads((OUT/'parent_source_manifest.json').read_text())
 for item in manifest['tree']:
  raw=(ROOT/item['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['sha'],item['path']
 for name,sha in cfg['code_SHA256'].items():assert hashlib.sha256((PARENT/name).read_bytes()).hexdigest()==sha,name
 assert w.fingerprint()==PARENT_FP
 return cfg
verify_parent()
dump=z.dump;csv_dump=z.csv_dump
