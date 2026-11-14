from pathlib import Path
from datetime import datetime
import sys,json,inspect,argparse,traceback,hashlib
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_dynamic_compare'))
import dynamic as x
OUT=Path(__file__).resolve().parent;d=x.d;r=x.r;p=x.p

def prepare(year,asset):
 d.BASE='https://data.binance.vision/data/spot'
 d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp())
 d.FIRST15=d.START-45*86400;d.FIRST1=d.START-86400
 data=OUT/str(year)/'data';data.mkdir(parents=True,exist_ok=True);d.DATA=data
 if (data/f'{asset}_daily_repair.json').exists():
  print('REUSE_VERIFIED_DAILY_REPAIR',year,asset,flush=True);return
 sources=[]
 for interval,step,first in [('15m',900,d.FIRST15),('1m',60,d.FIRST1)]:
  chunks=[];cur=datetime.fromtimestamp(first,r.UTC).replace(day=1,hour=0,minute=0,second=0)
  while int(cur.timestamp())<d.END:
   month=cur.strftime('%Y-%m');symbol=asset+'USDT';path=data/f'{asset}_{interval}_{month}.zip'
   meta=d.acquire(f'{d.BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip',path)
   rows=d.read_zip(path,list(range(6)));scale=1e6 if rows[0,0]>1e14 else 1000;rows[:,0]/=scale
   rows=rows[(rows[:,0]>=first)&(rows[:,0]<d.END)];chunks.append(rows);sources.append(dict(interval=interval,scale=scale,**meta));path.unlink()
   cur=cur.replace(year=cur.year+1,month=1) if cur.month==12 else cur.replace(month=cur.month+1)
  rows=np.concatenate(chunks);rows=rows[np.argsort(rows[:,0])];expected=np.arange(first,d.END,step);missing=np.setdiff1d(expected,rows[:,0]);extra=np.setdiff1d(rows[:,0],expected)
  if len(missing) or len(extra) or len(np.unique(rows[:,0]))!=len(rows):
   d.dump(OUT/str(year)/f'{asset}_{interval}_gaps.json',dict(missing_count=len(missing),first_missing=[r.local_s(int(t)) for t in missing[:30]],extra_count=len(extra)))
   from restore_gaps import restore
   if len(extra) or len(np.unique(rows[:,0]))!=len(rows):raise RuntimeError('Duplicate or off-grid native timestamps')
   rows=restore(rows,expected,step,asset,year,OUT,d,r)
   assert np.array_equal(rows[:,0],expected), 'Gap recovery incomplete'
  assert np.isfinite(rows).all() and (rows[:,3]>0).all()
  assert (rows[:,3]<=np.minimum(rows[:,1],rows[:,4])).all() and (rows[:,2]>=np.maximum(rows[:,1],rows[:,4])).all()
  if interval=='15m':np.savetxt(data/f'{asset}_15m.csv',np.column_stack((rows[:,0]*1000,rows[:,1:])),delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
  else:np.save(data/f'{asset}_1m.npy',rows[:,1:])
  d.dump(OUT/str(year)/f'{asset}_candle_sources.json',sources)
 print('SPOT_INPUTS_READY',year,asset,flush=True)

def main(year,asset):
 folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 status=folder/'status.json'
 if status.exists() and json.loads(status.read_text()).get('completed'):return
 try:
  prepare(year,asset);x.OUT=OUT
  source=inspect.getsource(x.run).replace(' if year==2020:',' if False:').replace(" profiles=['DYNAMIC'] if year==2020 else ['DYNAMIC','EARLY_2'];books={}"," profiles=['DYNAMIC'];books={}").replace('full_year=False','full_year=True')
  ns=dict(x.__dict__);exec(compile(source,'<same dynamic rule, homogeneous spot price input>','exec'),ns)
  ns['run'](year,asset)
  result_path=folder/'DYNAMIC_result.json';q=json.loads(result_path.read_text());q.update(source_market='BINANCE_SPOT_ONLY',financial_model='synthetic3x long/short, not actual spot or perpetual trading',borrow_interest='omitted',fees=0,derived_bar_proofs=[p.name for p in (OUT/str(year)).glob(f'{asset}_*gap_proofs.json')])
  d.dump(result_path,q)
 except Exception as error:
  q=dict(year=year,asset=asset,completed=False,source_market='BINANCE_SPOT_ONLY',error=repr(error),traceback=traceback.format_exc());d.dump(folder/'failure.json',q);d.dump(status,q);print('FAILED',year,asset,repr(error),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int);a.add_argument('asset',choices=['BTC','ETH']);z=a.parse_args();main(z.year,z.asset)
