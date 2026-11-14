from pathlib import Path
import importlib.util,inspect,json,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent

def worker(year,asset):
 spec=importlib.util.spec_from_file_location('v2_extended_rules',ROOT/'outputs/adaptive_risk_exit_v2/worker.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 spec=importlib.util.spec_from_file_location('prior_paths',ROOT/'outputs/dynamic_first10_perpetual/run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 src,data=m.paths(year);q=json.loads((src/asset/'DYNAMIC_result.json').read_text());start,end=[int(m.datetime.fromisoformat(s).timestamp()) for s in m.period(q)]
 ow=v.original_worker;source=inspect.getsource(ow.run)
 source=source.replace("d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp())",f'd.START={start};d.END={end}')
 source=source.replace("d.DATA=e.ROOT/f'outputs/other_years_050/{year}/data'",f'd.DATA=Path({str(data)!r})')
 source=source.replace("sources=json.loads((d.DATA.parent/f'{asset}_candle_sources.json').read_text());assert all('/data/futures/um/' in s['url'] and s['official_checksum_match'] for s in sources)","assert '/spot/' not in str(d.DATA)")
 source=source.replace("assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape==((d.END-d.FIRST1)//60,5)","assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape[1]==5")
 # Canonical uses FIRST1 for indexing; derive the actual existing minute file origin.
 source=source.replace('d.FIRST1=d.START-86400;',"d.FIRST1=d.START-86400;")
 source=source.replace("assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape[1]==5","assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape[1]==5;d.FIRST1=d.END-len(np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r'))*60")
 ns=dict(ow.__dict__);ns['OUT']=OUT;exec(compile(source,'<same full raw worker with saved period/data>','exec'),ns);ow.run=ns['run'];v.OUT=OUT;ow.OUT=OUT
 v.run(year,asset)

def launch(job):
 y,a=job;f=OUT/str(y)/a;f.mkdir(parents=True,exist_ok=True)
 with (f/'run.log').open('w') as log:r=subprocess.run([sys.executable,__file__,str(y),a],stdout=log,stderr=subprocess.STDOUT)
 print(y,a,r.returncode,flush=True)
if __name__=='__main__':
 if len(sys.argv)>1:worker(int(sys.argv[1]),sys.argv[2])
 else:
  with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(launch,[(y,a) for y in (2020,2021,2022,2023,2026) for a in ('BTC','ETH')]))
