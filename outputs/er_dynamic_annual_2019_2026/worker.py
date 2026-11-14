from pathlib import Path
from datetime import datetime
import sys,inspect,argparse,traceback,json
from urllib.request import urlopen
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_dynamic_compare'))
import dynamic as x
OUT=Path(__file__).resolve().parent;d=x.d;r=x.r;p=x.p

def main(year,asset):
 folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'status.json').exists() and json.loads((folder/'status.json').read_text()).get('completed'):return
 try:
  if year==2019:
   month='2018-11';url=f'{d.BASE}/monthly/klines/{asset}USDT/15m/{asset}USDT-15m-{month}.zip.CHECKSUM'
   print('PREFLIGHT',url,flush=True)
   with urlopen(url,timeout=30) as response:content=response.read()
   raise RuntimeError('2019 acquisition needs separate complete data preparation; checksum probe alone is not a replay')
  d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp())
  d.FIRST15=d.START-80*86400;d.FIRST1=d.START-86400;d.DATA=ROOT/f'outputs/other_years_050/{year}/data'
  for suffix in ('15m.csv','1m.npy'):assert (d.DATA/f'{asset}_{suffix}').exists(),f'Missing native {asset} {suffix}'
  expected=(d.END-d.FIRST1)//60;assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape==(expected,5)
  if year==2024:
   # Actual official-data preflight; same known inconsistent day, no strategy assumptions.
   p.OUT=folder;d.TEMP=folder/'temporary';d.TEMP.mkdir(exist_ok=True)
   native=p.Canonical(asset);cache=p.DayCache(asset,native)
   cache.load(int(datetime(2024,10,28,tzinfo=r.UTC).timestamp()))
   raise RuntimeError('If2024 preflight passes, full replay must be scheduled separately')
  x.OUT=OUT
  source=inspect.getsource(x.run)
  source=source.replace(' if year==2020:',' if False:')
  source=source.replace(" profiles=['DYNAMIC'] if year==2020 else ['DYNAMIC','EARLY_2'];books={}"," profiles=['DYNAMIC'];books={}")
  source=source.replace('full_year=False','full_year=True')
  namespace=dict(x.__dict__);exec(compile(source,'<unchanged dynamic rule, annual runtime window only>','exec'),namespace)
  print('START',year,asset,'DYNAMIC',flush=True);namespace['run'](year,asset)
 except Exception as error:
  item=dict(year=year,asset=asset,completed=False,error=repr(error),traceback=traceback.format_exc(),stage='data_preflight' if year in (2019,2024) else 'historical_replay')
  d.dump(folder/'failure.json',item);d.dump(folder/'status.json',item);print('FAILED',year,asset,repr(error),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int);a.add_argument('asset',choices=['BTC','ETH']);q=a.parse_args();main(q.year,q.asset)
