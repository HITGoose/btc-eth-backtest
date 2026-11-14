from pathlib import Path
from dataclasses import asdict
import argparse,json,hashlib,gzip,pickle,traceback,sys
from datetime import datetime
import numpy as np
import strategy as z
import priority_engine as pe
r=z.r;p=z.p;d=z.d;e=z.e;OUT=z.OUT

def fingerprint():
 return hashlib.sha256(b''.join((OUT/n).read_bytes()for n in ['strategy.py','priority_engine.py','worker.py'])).hexdigest()
def prior(period,asset,cost,group):
 folder=z.OLD/'runs'/period/asset
 if period=='2025'and asset=='ETH':folder=z.OLD/'isolation'/'25'/'runs'/period/asset
 key=cost+'_'+('B'if asset=='BTC'else group)
 return folder/f'{key}_result.json',folder/f'{key}_equity.npy'
def run(period,asset,groups):
 if asset=='BTC':groups=['B']
 tag=''.join(groups);folder=OUT/'runs'/period/asset/tag;folder.mkdir(parents=True,exist_ok=True);fp=fingerprint()
 if(folder/'status.json').exists()and json.loads((folder/'status.json').read_text()).get('completed'):
  assert json.loads((folder/'status.json').read_text())['code_fingerprint']==fp;return
 info=z.prepare(period,asset);leg=info['leg'];data=info['data'];start=info['start'];end=info['end'];btc=info if asset=='BTC'else z.prepare(period,'BTC')
 maps={};decisions={}
 for group in groups:
  maps[group],decisions[group]=z.classify(info['core'],info['wide'],btc['core'],group)
  if asset=='BTC':assert maps[group]==info['core']
 z.dump(folder/'signals.json',dict(core=info['core'],wide=info['wide'],BTC=btc['core'],accepted=maps))
 z.csv_dump(folder/'signal_classification.csv.gz',[dict(group=g,**row)for g in groups for row in decisions[g]if start*1000<=row['signal_close_ms']<end*1000])
 z.dump(folder/'config.json',dict(base_commit=z.BASE_COMMIT,groups={g:z.GROUPS[g]for g in groups},period=[r.local_s(start),r.local_s(end)],asset=asset,fee_scenarios=z.COSTS,funding='NOT_INCLUDED',single_account_cash=500,leverage=3,poll_seconds=5,poll_phase=2,slippage=.0002,SR_absolute_distance_pct=2.,code_fingerprint=fp,policy=asdict(info['policy']),ER=info['pair'],data=str(data),CORE='independent .25 complete signal at same closed-bar timestamp',EXTRA='complete .30 and not complete .25 at same timestamp/side',BTC_confirmation='same closed-bar complete .25 indicator signal; independent of BTC account',priority='locked CORE request at +10s; stop first, otherwise next strictly later raw print; no same-event re-fill',same_timestamp_order='actual prints before poll; CORE clock after actual prints at +10; original +10 boundary retained for ordinary signals',raw_integrity='strict IDs, original checksum; no OHLC fallback'))
 z.dump(folder/'input_provenance.json',dict(sources=info['sources'],derived_SHA256={f:hashlib.sha256((data/f).read_bytes()).hexdigest()for f in [f'{asset}_15m.csv',f'{asset}_1m.npy']},start=start,end=end,first=info['first'],warmup_first=leg.first,cache_note='native cache plus recorded acquisition checksums; no saved trade path used to execute new orders'))
 d.BASE='https://data.binance.vision/data/futures/um';d.DATA=data;d.START=start;d.END=end;d.FIRST1=info['first']
 native=p.Canonical(asset);cache=e.RawCache(asset,native,folder)
 # Preserve the exact conflicting daily archive for a deterministic retry.
 bad=z.OLD/'runs/2025/ETH/temporary/ETHUSDT-trades-2025-08-29.zip'
 if period=='2025'and asset=='ETH'and bad.exists():
  target=folder/'temporary'/bad.name
  if not target.exists():target.hardlink_to(bad)
 for name,attr in [('raw_sources.json','sources'),('candle_tick_disagreements.json','disagreements')]:
  if(folder/name).exists():setattr(cache,attr,json.loads((folder/name).read_text()))
 saved=None;resume=start;cp=folder/'checkpoint.pkl.gz'
 if cp.exists():
  with gzip.open(cp,'rb')as f:saved=pickle.load(f)
  assert saved['code_fingerprint']==fp and saved['groups']==groups,'fingerprint mismatch: use fresh output cohort'
  resume=saved['next_time'];print('RESUME',r.local_s(resume),flush=True)
 books={};markets={};gens={};prefix={}
 for cost,fee in z.COSTS.items():
  for g in groups:
   key=cost+'_'+g;b=saved['books'][key]if saved else pe.book(asset,fee,leg,info['core'],asset=='ETH'and z.GROUPS[g]['priority']);b.leg=leg
   books[key]=b;prefix[key]=saved['marks'][key]if saved else np.array([],dtype=float);markets[key]=pe.Market(native,cache,b,True)
   gens[key]=pe.generator(b)(asset,leg=leg,signals=maps[g],market=markets[key],start=resume*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
 print('START',period,asset,groups,{g:len(maps[g])for g in groups},flush=True)
 for t in range(resume,end,60):
  for key,generator in gens.items():
   r.model.FEE=books[key].fee;assert next(generator)==t
  if t%86400==0:z.dump(folder/'progress.json',dict(time=r.local_s(t),raw_days=len(cache.sources),books={k:dict(cash=b.cash,opens=b.stats['long']+b.stats['short'])for k,b in books.items()}))
  boundary=datetime.fromtimestamp(t+60,r.TZ)
  if boundary.day==1 and boundary.hour==0 and boundary.minute==0:
   marks={k:np.r_[prefix[k],np.asarray(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
   for b in books.values():b.leg=None
   try:
    with gzip.open(folder/'checkpoint.tmp','wb',compresslevel=1)as f:pickle.dump(dict(code_fingerprint=fp,groups=groups,next_time=t+60,books=books,marks=marks),f,protocol=5)
    (folder/'checkpoint.tmp').replace(cp)
   finally:
    for b in books.values():b.leg=leg
 for key,generator in gens.items():
  b=books[key];r.model.FEE=b.fee
  try:next(generator);raise AssertionError('calendar overshot')
  except StopIteration as stop:result=stop.value
  assert not result['approximated_minutes'];mark=markets[key][end-60][3];pos=b.position
  openpart=getattr(pos,'partial_net',0.)if pos else 0.;openfee=b.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.
  assert abs(b.cash-500-sum(t['net']for t in b.journal)-openpart+openfee)<1e-7,(key,'journal cash mismatch')
  assert abs(b.cash-500-sum(t['delta']for t in b.cash_events))<1e-7,(key,'cash events mismatch')
  state=p.state(b)
  if pos:state['position']['order'].update(signal_close_ms=b.order_info['signal_close_ms'],origin=b.order_info['origin'])
  if b.order:state['pending_order'].update(signal_close_ms=b.order_info['signal_close_ms'],origin=b.order_info['origin'])
  q=dict(asset=asset,period=period,window=[r.local_s(start),r.local_s(end)],key=key,fee=b.fee,ending_equity=b.equity(mark),cash=b.cash,starting_equity=500.,trades=b.journal,events=b.events,place_attempts=b.place_attempts,cash_events=b.cash_events,stats=dict(b.stats),opens=result['opens'],state_at_end=state,actual_raw_last_mark=mark,open_contribution=b.equity(mark)-b.cash+openpart-openfee,no_OHLC_fallback=True,source='BINANCE_USDT_PERPETUAL_ONLY',replacement_at_end=b.replacement)
  if pos:q['open_partial_state']={k:getattr(pos,k,None)for k in ('initial_quantity','partial_net','partial_fills','partial_queue','partial_stage')}
  marks=np.r_[prefix[key],np.asarray(result['marks'])]
  group=key.split('_')[-1];cost=key.rsplit('_',1)[0]
  if group in('B','D'):
   oldpath,eqpath=prior(period,asset,cost,group)
   if oldpath.exists():
    old=json.loads(oldpath.read_text());assert abs(q['ending_equity']-old['ending_equity'])<1e-7,(period,asset,key,'equity regression')
    assert len(q['trades'])==len(old['trades'])
    for actual,expected in zip(q['trades'],old['trades']):
     for field in expected:assert actual[field]==expected[field],(period,asset,key,field,actual[field],expected[field])
    assert np.array_equal(marks,np.load(eqpath)),(period,asset,key,'equity path regression')
    q['prior_exact_trade_and_equity_path_regression']=True
  with gzip.open(folder/f'{key}_shadow_snapshots.pkl.gz','wb')as f:pickle.dump(b.shadow_snapshots,f,protocol=5)
  z.dump(folder/f'{key}_result.json',q);np.save(folder/f'{key}_equity.npy',marks)
  print('COMPLETE',period,asset,key,q['ending_equity'],flush=True)
 z.dump(folder/'status.json',dict(completed=True,code_fingerprint=fp,groups=groups,keys=list(books)))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('period');parser.add_argument('asset',choices=['BTC','ETH']);parser.add_argument('--groups',default='BDGHI');args=parser.parse_args()
 try:run(args.period,args.asset,list(args.groups))
 except Exception as error:
  folder=OUT/'runs'/args.period/args.asset/('B'if args.asset=='BTC'else args.groups);folder.mkdir(parents=True,exist_ok=True);z.dump(folder/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),code_fingerprint=fingerprint()));raise
