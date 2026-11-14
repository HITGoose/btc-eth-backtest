"""Salvage independent threshold cohorts without relaxing any data guard.

Selects accounts only. All statements in the frozen financial run body remain
unchanged. Loads its own copy of the original August checkpoint. A bad cohort
cannot suppress another independent cohort's verifiable result.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import importlib.util,sys,inspect,json,shutil,subprocess,os,hashlib
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
sp=importlib.util.spec_from_file_location('density_worker_isolation',OUT/'worker.py');w=importlib.util.module_from_spec(sp);sys.modules[sp.name]=w;sp.loader.exec_module(w)
# The original checkpoint was made by worker.py executed as __main__.
Control=w.Control;Dynamic=w.Dynamic

def run(threshold):
 selected={'.25':['A','B'],'.30':['C','D'],'.35':['E','F']}[threshold]
 root=OUT/'isolation'/threshold[1:];folder=root/'runs/2025/ETH';folder.mkdir(parents=True,exist_ok=True)
 if not(folder/'checkpoint.pkl.gz').exists():shutil.copy2(OUT/'runs/2025/ETH/checkpoint.pkl.gz',folder/'checkpoint.pkl.gz')
 tmp=folder/'temporary';tmp.mkdir(exist_ok=True);bad=OUT/'runs/2025/ETH/temporary/ETHUSDT-trades-2025-08-29.zip'
 if bad.exists()and not(tmp/bad.name).exists():os.link(bad,tmp/bad.name)
 source=inspect.getsource(w.run);needle="groups=['A','B']if asset=='BTC'else list(s.GROUPS)";assert source.count(needle)==1;source=source.replace(needle,'groups=SELECTED_GROUPS')
 ns=dict(w.__dict__);ns.update(OUT=root,SELECTED_GROUPS=selected)
 exec(compile(source,'<frozen financial runner, independent cohort selection only>','exec'),ns)
 (folder/'selection.json').write_text(json.dumps(dict(groups=selected,financial_source=str(OUT/'worker.py'),wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),derived_function_sha256=hashlib.sha256(source.encode()).hexdigest(),data_validation='UNCHANGED: duplicate/unordered IDs still reject archive',checkpoint_source=str(OUT/'runs/2025/ETH/checkpoint.pkl.gz')),indent=2))
 try:ns['run']('2025','ETH')
 except Exception as error:
  import traceback
  (folder/'failure.json').write_text(json.dumps(dict(error=repr(error),traceback=traceback.format_exc()),indent=2));raise

def child(t):
 folder=OUT/'isolation'/t[1:];folder.mkdir(parents=True,exist_ok=True)
 with(folder/'run.log').open('w')as log:r=subprocess.run([sys.executable,__file__,t],stdout=log,stderr=subprocess.STDOUT)
 print(t,r.returncode,flush=True);return dict(threshold=t,code=r.returncode)
if __name__=='__main__':
 if len(sys.argv)>1:run(sys.argv[1])
 else:
  with ThreadPoolExecutor(max_workers=2)as pool:result=list(pool.map(child,('.25','.30','.35')))
  (OUT/'isolation_status.json').write_text(json.dumps(result,indent=2))
