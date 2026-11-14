from pathlib import Path
from datetime import datetime
from dataclasses import asdict
import argparse,json,traceback
import numpy as np
import engine as e
OUT=e.OUT;d=e.d;p=e.p;r=e.r

def run(year,asset):
 folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'status.json').exists() and json.loads((folder/'status.json').read_text()).get('completed'):return
 d.BASE='https://data.binance.vision/data/futures/um'
 d.START=int(datetime(year,1,1,tzinfo=r.TZ).timestamp());d.END=int(datetime(year+1,1,1,tzinfo=r.TZ).timestamp())
 d.FIRST1=d.START-86400;d.FIRST15=d.START-80*86400;d.DATA=e.ROOT/f'outputs/other_years_050/{year}/data'
 sources=json.loads((d.DATA.parent/f'{asset}_candle_sources.json').read_text());assert all('/data/futures/um/' in s['url'] and s['official_checksum_match'] for s in sources)
 assert np.load(d.DATA/f'{asset}_1m.npy',mmap_mode='r').shape==((d.END-d.FIRST1)//60,5)
 leg,signals,ctx,base,policy,pair=p.prepare(asset,d.DATA/f'{asset}_15m.csv',d.START,d.END)
 native=p.Canonical(asset);cache=e.RawCache(asset,native,folder)
 books={name:e.new_book(asset,name,leg) for name in ('CONTROL','DYNAMIC')}
 markets={name:e.Market(native,cache,book,True) for name,book in books.items()}
 gens={name:e.generator(book)(asset,leg=leg,signals=signals['ER'],market=markets[name],start=d.START*1000,end=d.END*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False) for name,book in books.items()}
 config=dict(source='BINANCE_USDT_PERPETUAL_ONLY',year=year,window=[r.local_s(d.START),r.local_s(d.END)],fee=0.,leverage=3.,each_initial_cash=500.,slippage=.0002,ER=pair,policy=asdict(policy),entry='unchanged old SMA/EMA20,60,120 + original ER BASELINE, no dual-cross',versions=['CONTROL','DYNAMIC'],execution='official raw trades, every active minute, full latest raw quote for polls and marks; discrepancies logged not rejected',minute_HL_pruning=False,raw_IDs_monotonic_required=True,ID_jumps_logged=True,archive_market_completeness_independently_verified=False,no_price_rewrite=True,no_OHLC_fallback=True,dynamic='unchanged1pct initial25pct then first closed15m six-line/MACD weakening25pct; original trailing stop for remainder',original_work_files_unchanged=True,original_submit_boundary_preserved=True,limit_fill='full-size touch proxy, no queue/depth simulation',funding='omitted')
 d.dump(folder/'config.json',config);d.dump(folder/'signals.json',signals['ER']);print('START',year,asset,'RAW_PERPETUAL',len(signals['ER']),'signal candidates',flush=True)
 for t in range(d.START,d.END,60):
  for g in gens.values():assert next(g)==t
  if t%86400==0:d.dump(folder/'progress.json',dict(time=r.local_s(t),books={n:dict(cash=b.cash,opens=b.stats['long']+b.stats['short']) for n,b in books.items()},raw_days=len(cache.sources)))
 for name,g in gens.items():
  try:next(g);raise RuntimeError('Overshot calendar end')
  except StopIteration as stop:q=stop.value
  assert not q['approximated_minutes'];b=books[name];mark=markets[name][d.END-60][3]
  realized=sum(v['net'] for v in b.journal)+(getattr(b.position,'partial_net',0.) if b.position else 0.)
  assert abs(b.cash-500-realized)<1e-7
  if name=='DYNAMIC':
   for row in b.journal:assert abs(sum(v['quantity'] for v in row['partial_fills'])+row['final_exit_quantity']-row['quantity'])<1e-8
  result=dict(year=year,asset=asset,profile=name,source='BINANCE_USDT_PERPETUAL_ONLY',period=config['window'],starting_equity=500.,ending_equity=b.equity(mark),return_pct=100*(b.equity(mark)/500-1),opens=q['opens'],trades=b.journal,events=b.events,stats=dict(b.stats),state_at_end=p.state(b),actual_raw_last_mark=mark,no_OHLC_fallback=True,raw_day_count=len(cache.sources),disagreement_days=len(cache.disagreements))
  d.dump(folder/f'{name}_result.json',result);np.save(folder/f'{name}_equity.npy',q['marks']);print(year,asset,name,'COMPLETE',result['return_pct'],flush=True)
 d.dump(folder/'status.json',dict(completed=True,versions=['CONTROL','DYNAMIC'],source='BINANCE_USDT_PERPETUAL_ONLY'))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int);a.add_argument('asset',choices=['BTC','ETH']);q=a.parse_args()
 try:run(q.year,q.asset)
 except Exception as error:
  folder=OUT/str(q.year)/q.asset;folder.mkdir(parents=True,exist_ok=True);d.dump(folder/'failure.json',dict(completed=False,error=repr(error),traceback=traceback.format_exc()));raise
