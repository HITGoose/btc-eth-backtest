from pathlib import Path
import argparse,json,gzip,pickle,copy,hashlib,traceback,sys
from datetime import datetime
import shared as s
import funding_engine as E
b=s.b;r=s.r;z=s.z;np=s.np;OUT=s.OUT/'funded'

def fund_fp():
 return hashlib.sha256(s.fp().encode()+b''.join((s.OUT/n).read_bytes()for n in ['funding_engine.py','funded_replay.py'])).hexdigest()
def configurations(asset,stage):
 rows=[]
 cfgs={'C2':(.0005,.0002),'C3':(.0005,.0005),'C4':(.00075,.001)}
 for cost,(fee,slip)in cfgs.items():
  for group in(s.GROUPS if asset=='ETH'else ['B']):rows.append(dict(key=cost+'_'+group+'_F_TOUCH',cost=cost,group=group,fill='F_TOUCH',fee=fee,slip=slip,funding=True))
 for group in(['B','I100','I50','I25']if asset=='ETH'else ['B']):rows.append(dict(key='C2_'+group+'_F_THROUGH',cost='C2',group=group,fill='F_THROUGH',fee=.0005,slip=.0002,funding=True))
 return rows

def raw_cache(asset,native,folder):
 cache=b.e.RawCache(asset,native,folder)
 for name,attr in [('raw_sources.json','sources'),('candle_tick_disagreements.json','disagreements')]:
  p=folder/name
  if p.exists():setattr(cache,attr,json.loads(p.read_text()))
 return cache

def segment(folder,ctx,start,end,books,maps,scenes,cache,views,final=False):
 folder.mkdir(parents=True,exist_ok=True);cp=folder/'checkpoint.pkl.gz';resume=start;prefix={k:np.array([])for k in books}
 fingerprint=fund_fp();datafp=ctx['fingerprint']
 if cp.exists():
  with gzip.open(cp,'rb')as f:q=pickle.load(f)
  assert(q['fp'],q['datafp'],q['start'],q['end'],q['keys'])==(fingerprint,datafp,start,end,list(books)),'incompatible checkpoint'
  books=q['books'];prefix=q['marks'];resume=q['next']
  for x in books.values():x.leg=ctx['leg'];E.cash_check(x)
  print('RESUME',folder,r.local_s(resume),flush=True)
 if resume==end:return books,prefix
 markets={};gens={}
 for key,x in books.items():
  cv=s.a.ScenarioCache(cache,views,scenes[key])if views else cache
  markets[key]=E.Market(ctx['native'],cv,x,True)
  gens[key]=b.pe.generator(x)(ctx['asset'],leg=ctx['leg'],signals=maps[key],market=markets[key],start=resume*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
 for t in range(resume,end,60):
  for key,g in gens.items():s.activate(books[key]);assert next(g)==t
  if(t+60)%86400==0 or t+60==end:
   marks={k:np.r_[prefix[k],np.asarray(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
   for x in books.values():E.cash_check(x);x.leg=None
   try:
    with gzip.open(cp.with_suffix('.tmp'),'wb',compresslevel=1)as f:pickle.dump(dict(fp=fingerprint,datafp=datafp,start=start,end=end,keys=list(books),next=t+60,books=books,marks=marks),f,protocol=5)
    cp.with_suffix('.tmp').replace(cp)
   finally:
    for x in books.values():x.leg=ctx['leg']
   s.dump(folder/'progress.json',dict(next_time=r.local_s(t+60),cash={k:x.cash for k,x in books.items()},raw_days=len(cache.sources)));print('DAY',ctx['period'],ctx['asset'],folder.name,r.local_s(t+60),flush=True)
 marks={k:np.r_[prefix[k],np.asarray(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
 if final:
  for key,g in gens.items():
   s.activate(books[key])
   try:next(g);raise RuntimeError('overshot')
   except StopIteration as stop:assert not stop.value['approximated_minutes']
 else:
  for g in gens.values():g.close()
 return books,marks

def oldpath(period,asset,cost,group,scene):
 cost={'C0':'ZERO','C1':'ASSUMED_005_SIDE'}[cost];group='B'if asset=='BTC'else s.GROUPS[group][0]
 if period=='2025'and asset=='ETH':return s.OLD/'results'/scene/(cost+'_'+group+'_result.json'),s.OLD/'results'/scene/(cost+'_'+group+'_equity.npy')
 folders=list((b.PARENT/'runs'/period/asset).glob('*/'+cost+'_'+group+'_result.json'))
 assert len(folders)==1,folders
 return folders[0],folders[0].with_name(cost+'_'+group+'_equity.npy')

def output(ctx,folder,scene,cfg,x,marks,mark,stage):
 E.cash_check(x);pos=x.position;part=getattr(pos,'partial_net',0.)if pos else 0.;fee=x.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.
 state=b.p.state(x)
 if pos:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
 if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
 q=dict(asset=ctx['asset'],period=ctx['period'],window=[r.local_s(ctx['start']),r.local_s(ctx['end'])],key=cfg['key'],configuration=cfg,scenario=scene,status='COMPLETED_WITH_DATA_ANOMALY'if ctx['period']=='2025'else 'COMPLETE',fee=x.fee,cash=x.cash,starting_equity=500.,ending_equity=x.equity(mark),trades=x.journal,events=x.events,cash_events=x.cash_events,stats=dict(x.stats),place_attempts=x.place_attempts,sizing_audit=x.sizing_audit,slippage_cost_USDT=x.slippage_cost,funding_total_USDT=x.funding_total,funding='INCLUDED_OFFICIAL',funding_events=x.funding_events,funding_data_SHA256=ctx['funding_SHA256'],source='BINANCE_USDT_PERPETUAL_ONLY',state_at_end=state,actual_raw_last_mark=mark,open_contribution=x.equity(mark)-x.cash+part-fee+(getattr(pos,'funding_pnl',0.)if pos else 0.),replacement_at_end=x.replacement,no_OHLC_fallback=True)
 if pos:q['open_partial_state']={k:getattr(pos,k,None)for k in ('initial_quantity','partial_net','partial_fills','partial_queue','partial_stage','funding_pnl')}
 if stage=='baseline':
  op,ep=oldpath(ctx['period'],ctx['asset'],cfg['cost'],cfg['group'],scene);old=json.loads(op.read_text());assert len(old['trades'])==len(x.journal)
  for actual,expected in zip(x.journal,old['trades']):
   for key,val in expected.items():assert actual.get(key)==val,('trade',cfg['key'],key,actual.get(key),val)
  for key in ('cash','ending_equity'):assert abs(q[key]-old[key])<1e-7,(cfg['key'],key)
  assert np.array_equal(marks,np.load(ep)),('minute regression',cfg['key'])
  q['baseline_exact_trade_cash_equity_minutes']=True
 folder.mkdir(parents=True,exist_ok=True);s.dump(folder/(cfg['key']+'_result.json'),q);np.savez_compressed(folder/(cfg['key']+'_equity.npz'),marks=marks)
 print('COMPLETE',ctx['period'],ctx['asset'],scene,cfg['key'],q['ending_equity'],flush=True)

def run(period,asset,stage):
 folder=OUT/'runs'/period/asset/stage;folder.mkdir(parents=True,exist_ok=True)
 fp=fund_fp();done=folder/'status.json'
 if done.exists():assert json.loads(done.read_text())['fp']==fp;return
 assert json.loads((s.OUT/'runs'/period/asset/'baseline/status.json').read_text())['completed']
 funding_sha=E.configure_feed(period,asset)
 cfgs=configurations(asset,stage)
 info=z.prepare(period,asset);btc=info if asset=='BTC'else z.prepare(period,'BTC');d=b.d;d.BASE='https://data.binance.vision/data/futures/um';d.DATA=info['data'];d.START=info['start'];d.END=info['end'];d.FIRST1=info['first']
 native=b.p.Canonical(asset);ctx=dict(info,asset=asset,period=period,native=native,funding_SHA256=funding_sha)
 hashes={name:hashlib.file_digest((info['data']/name).open('rb'),'sha256').hexdigest()for name in [asset+'_15m.csv',asset+'_1m.npy']}
 ctx['fingerprint']=s.o.digest(dict(funding_data_SHA256=funding_sha,hashes=hashes,core=info['core'],wide=info['wide'],BTC=btc['core'],configs=cfgs,period=period,asset=asset))
 s.dump(folder/'input_provenance.json',dict(source='BINANCE_USDT_PERPETUAL_ONLY',native_SHA256=hashes,candle_sources=info['sources'],data_fingerprint=ctx['fingerprint'],runtime_fingerprint=fp))
 maps={};books={}
 for cfg in cfgs:
  key=cfg['key'];parent,ratio=s.GROUPS[cfg['group']];maps[key]=info['core']if asset=='BTC'else z.classify(info['core'],info['wide'],btc['core'],parent)[0]
  books[key]=E.book(asset,cfg['fee'],cfg['slip'],info['leg'],info['core'],asset=='ETH'and z.GROUPS[parent]['priority'],ratio,cfg['fill'])
 cache=raw_cache(asset,native,folder);views=s.a.Views()if period=='2025'and asset=='ETH'else None
 start,end=info['start'],info['end'];print('START',period,asset,stage,len(books),flush=True)
 if views:
  fork=views.manifest['fork_second'];merge=views.manifest['merge_second']
  common,prefix=segment(folder/'prefix',ctx,start,fork,books,maps,{k:'S_ALL'for k in books},cache,views)
  forks={};scenes={};fmaps={}
  for scene in b.SCENARIOS:
   for key,x in common.items():
    ident=scene+'|'+key;forks[ident]=s.o.clone(x,info['leg']);scenes[ident]=scene;fmaps[ident]=maps[key]
  forks,window=segment(folder/'fork',ctx,fork,merge,forks,fmaps,scenes,cache,views)
  pools={};membership={};evidence=[]
  for ident,x in forks.items():
   scene,key=ident.split('|',1);state=s.o.encoded(s.o.full_state(x));quote=views.latest(scene,merge-.000001);blob=state+s.o.encoded(quote);h=hashlib.sha256(blob).hexdigest();pool=key+'|'+h
   if pool in pools:assert blob==pools[pool][1]
   else:pools[pool]=(x,blob)
   membership[ident]=pool;evidence.append(dict(id=ident,pool=pool,full_state_SHA256=h,own_prefix_SHA256=hashlib.sha256(np.r_[prefix[key],window[ident]].tobytes()).hexdigest()))
  s.dump(folder/'pooling.json',dict(full_state_with_original_history_and_latest_quote=True,members=evidence,pools=len(pools),scenarios=b.SCENARIOS))
  sb={pool:x[0]for pool,x in pools.items()};sm={pool:maps[pool.split('|',1)[0]]for pool in sb}
  sb,suffix=segment(folder/'suffix',ctx,merge,end,sb,sm,{k:'S_ALL'for k in sb},cache,views,True)
  for ident,pool in membership.items():
   scene,key=ident.split('|',1);cfg=next(v for v in cfgs if v['key']==key);marks=np.r_[prefix[key],window[ident],suffix[pool]];market=E.Market(native,s.a.ScenarioCache(cache,views,scene),sb[pool],True);mark=market[end-60][3]
   output(ctx,folder/'results'/scene,scene,cfg,sb[pool],marks,mark,stage)
 else:
  books,marks=segment(folder/'whole',ctx,start,end,books,maps,{k:'STRICT'for k in books},cache,None,True)
  for cfg in cfgs:
   x=books[cfg['key']];mark=E.Market(native,cache,x,True)[end-60][3];output(ctx,folder/'results/STRICT','STRICT',cfg,x,marks[cfg['key']],mark,stage)
 s.dump(done,dict(completed=True,fp=fp,datafp=ctx['fingerprint'],configs=cfgs,status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'else 'COMPLETE'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('period');p.add_argument('asset');p.add_argument('stage',choices=['funded']);v=p.parse_args()
 try:run(v.period,v.asset,v.stage)
 except Exception as e:
  folder=OUT/'runs'/v.period/v.asset/v.stage;folder.mkdir(parents=True,exist_ok=True);s.dump(folder/'failure.json',dict(error=repr(e),traceback=traceback.format_exc(),fp=fund_fp()));raise
