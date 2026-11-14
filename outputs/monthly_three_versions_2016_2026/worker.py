from pathlib import Path
from datetime import datetime
import sys,inspect,argparse,traceback,json
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_dynamic_spot_fallback'))
import worker as f
x=f.x;d=x.d;p=x.p;r=x.r;OUT=Path(__file__).resolve().parent
original_reachable=x.generator.__globals__['reachable']
x.generator.__globals__['reachable']=lambda b,*args: False if b.profile=='CONTROL' else original_reachable(b,*args)

def main(year,asset):
 folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 status=folder/'status.json'
 if status.exists() and json.loads(status.read_text()).get('completed') and (folder/'CONTROL_result.json').exists():return
 try:
  if year<=2018:
   f.OUT=OUT/'spot_inputs';f.OUT.mkdir(exist_ok=True)
   prepared=f.OUT/str(year)/'data'
   if year==2018 and (prepared/f'{asset}_1m.npy').exists() and (prepared/f'{asset}_15m.csv').exists() and (f.OUT/str(year)/f'{asset}_candle_sources.json').exists():
    d.BASE='https://data.binance.vision/data/spot';d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp());d.FIRST15=d.START-45*86400;d.FIRST1=d.START-86400;d.DATA=prepared
   elif year==2018:
    from normalize_early import normalize
    preparation=inspect.getsource(f.prepare)
    old="  if len(missing) or len(extra) or len(np.unique(rows[:,0]))!=len(rows):"
    new="  if len(extra) or len(np.unique(rows[:,0]))!=len(rows):\n   rows=normalize(rows,expected,step,asset,year,OUT,d,r);missing=np.setdiff1d(expected,rows[:,0]);extra=np.setdiff1d(rows[:,0],expected)\n"+old
    assert old in preparation;preparation=preparation.replace(old,new)
    ns=dict(f.__dict__);ns['normalize']=normalize;exec(compile(preparation,'<same spot acquisition, verified irregular-bar reconstruction>','exec'),ns);ns['prepare'](year,asset)
   else:f.prepare(year,asset)
   market='BINANCE_SPOT'
  else:
   spot=year in (2019,2020,2024,2025);market='BINANCE_SPOT' if spot else 'BINANCE_USDT_PERPETUAL'
   d.BASE='https://data.binance.vision/data/spot' if spot else 'https://data.binance.vision/data/futures/um'
   d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp())
   d.FIRST15=d.START-(45 if spot else 80)*86400;d.FIRST1=d.START-86400
   d.DATA=ROOT/f'outputs/er_dynamic_spot_fallback/{year}/data' if spot else ROOT/f'outputs/other_years_050/{year}/data'
  profiles=['CONTROL','DYNAMIC'] if year<=2018 else ['CONTROL']
  assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape[0]==(d.END-d.FIRST1)//60
  source=inspect.getsource(x.run).replace(' if year==2020:',' if False:')
  source=source.replace(" profiles=['DYNAMIC'] if year==2020 else ['DYNAMIC','EARLY_2'];books={}"," profiles=SELECTED_PROFILES;books={}")
  source=source.replace("  if name=='EARLY_2':b=v.book(asset,name)","  if name=='CONTROL':b=p.new_book(asset,name)\n  elif name=='EARLY_2':b=v.book(asset,name)")
  source=source.replace("  for row in b.journal:assert abs(sum(x['quantity'] for x in row['partial_fills'])+row['final_exit_quantity']-row['quantity'])<1e-8", "  if name!='CONTROL':\n   for row in b.journal:assert abs(sum(x['quantity'] for x in row['partial_fills'])+row['final_exit_quantity']-row['quantity'])<1e-8")
  source=source.replace('full_year=False','full_year=True');x.OUT=OUT
  ns=dict(x.__dict__);ns['SELECTED_PROFILES']=profiles;exec(compile(source,'<same rules, missing comparison books only>','exec'),ns)
  print('START',year,asset,market,profiles,flush=True);ns['run'](year,asset)
  for name in profiles:
   path=folder/f'{name}_result.json';q=json.loads(path.read_text());q['source_market']=market;d.dump(path,q)
 except Exception as error:
  q=dict(year=year,asset=asset,completed=False,error=repr(error),traceback=traceback.format_exc());d.dump(folder/'failure.json',q);d.dump(status,q);print('FAILED',year,asset,repr(error),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int);a.add_argument('asset',choices=['BTC','ETH']);q=a.parse_args();main(q.year,q.asset)
