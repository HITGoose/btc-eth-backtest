from pathlib import Path
import sys,json,hashlib,pickle,gzip,datetime,traceback
import signals as sig
import importlib.util
sp=importlib.util.spec_from_file_location('adaptive_control_engine',Path(__file__).resolve().parent/'engine.py');E=importlib.util.module_from_spec(sp);sys.modules[sp.name]=E;sp.loader.exec_module(E)
s=sig.s;np=s.np;R=sig.R;O=sig.O
TRAIN=['2020','2021','2022']
def fp():return hashlib.sha256(b''.join((O/n).read_bytes()for n in ['signals.py','engine.py','worker.py','EXPERIMENT.md'])+s.fp().encode()).hexdigest()
def configurations(stage,freeze=None):
 if stage=='train':return[dict(key='ZERO_'+n,source=n,group=n,fee=0.,hybrid=False)for n in sig.SPECS]
 b,c,d=freeze['B'],freeze['C'],freeze['D_source'];out=[]
 if stage=='train_final':out=[dict(key='ZERO_D',source=d,group='D',fee=0.,hybrid=True)]
 for fee,label in [(0.,'ZERO'),(.0005,'ASSUMED_005_SIDE')]:
  if stage=='train_final'and fee==0:continue
  for group,source in [('A','A'),('B',b),('C',c),('D',d)]:out.append(dict(key=label+'_'+group,source=source,group=group,fee=fee,hybrid=group=='D'))
 return out

def run(period,asset,stage):
 if stage!='train':
  freeze=json.loads((O/'FREEZE.json').read_text());assert freeze['code_fingerprint']==fp();assert period not in TRAIN or stage=='train_final'
 else:assert period in TRAIN;freeze=None
 folder=O/'runs'/stage/period/asset;folder.mkdir(parents=True,exist_ok=True);done=folder/'status.json'
 if done.exists():assert json.loads(done.read_text())['fp']==fp();return
 ref,data,start,end,first,sources=s.z.inputs(period,asset);info=dict(ref=ref,data=data,start=start,end=end,first=first,sources=sources);cfgs=configurations(stage,freeze);names=list(dict.fromkeys(['A']+[c['source']for c in cfgs]));q=sig.make(asset,info['data'],start,end,names);leg=q['leg'];core=q['maps']['A'];maps={c['key']:sig.mix(core,q['maps'][c['source']])if c['hybrid']else q['maps'][c['source']]for c in cfgs}
 s.dump(folder/'signals.json',dict(base=core,candidates=q['maps'],accepted=maps));s.dump(folder/'config.json',dict(period=period,asset=asset,stage=stage,configs=cfgs,Settings=vars(sig.SETTINGS),policy=vars(sig.POLICY),ER=sig.PAIR,V2=False,rebound=False,initial_cash=500,ordinary_leverage=3,EXTRA_D_leverage=1,funding=0,exit_slippage=.0002,thresholds=q['thresholds'],warmup_first_ms=leg.first,financial_start_ms=start*1000,end_ms=end*1000,code_fingerprint=fp()))
 for name,diag in q['diagnostics'].items():s.z.csv_dump(folder/(name+'_signal_conditions.csv'),diag)
 d=s.b.d;d.DATA=info['data'];d.START=start;d.END=end;d.FIRST1=info['first'];d.BASE='https://data.binance.vision/data/futures/um';native=s.b.p.Canonical(asset);strict=s.b.e.RawCache(asset,native,folder)
 if(folder/'raw_sources.json').exists():strict.sources=json.loads((folder/'raw_sources.json').read_text())
 cache=strict
 if period=='2025'and asset=='ETH':
  views=s.a.Views();cache=s.a.ScenarioCache(strict,views,'S_ALL');s.dump(folder/'S_ALL.json',views.get('S_ALL')['metadata'])
 books={c['key']:E.book(asset,c['fee'],leg,core,c['hybrid'])for c in cfgs};resume=start;prefix={k:np.array([])for k in books};cp=folder/'checkpoint.pkl.gz';datafp=s.o.digest(dict(maps=maps,configs=cfgs,hashes={n:sig.digest_file(info['data']/n)for n in [asset+'_15m.csv',asset+'_1m.npy']}))
 if cp.exists():
  with gzip.open(cp,'rb')as f:v=pickle.load(f)
  assert v['fp']==fp()and v['datafp']==datafp and v['end']==end and v['start']==start;books=v['books'];prefix=v['marks'];resume=v['next']
  for x in books.values():x.leg=leg;E.cash_check(x)
 markets={k:E.Market(native,cache,x,True)for k,x in books.items()};gens={k:E.generator(x)(asset,leg=leg,signals=maps[k],market=markets[k],start=resume*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)for k,x in books.items()}
 marks={k:prefix[k]for k in books}
 print('START',stage,period,asset,'accounts',len(cfgs),{k:len(v)for k,v in maps.items()},flush=True)
 for t in range(resume,end,60):
  for k,g in gens.items():E.activate(books[k]);assert next(g)==t
  if(t+60)%86400==0 or t+60==end:
   marks={k:np.r_[prefix[k],np.array(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
   for x in books.values():E.cash_check(x);x.leg=None
   with gzip.open(cp.with_suffix('.tmp'),'wb',compresslevel=1)as f:pickle.dump(dict(fp=fp(),datafp=datafp,start=start,end=end,next=t+60,books=books,marks=marks),f,protocol=5)
   cp.with_suffix('.tmp').replace(cp)
   for x in books.values():x.leg=leg
   print('DAY',stage,period,asset,s.r.local_s(t+60),flush=True)
 for k,g in gens.items():
  E.activate(books[k])
  try:next(g);raise RuntimeError('overshot')
  except StopIteration as st:assert not st.value['approximated_minutes']
  x=books[k];E.cash_check(x);v=marks[k];mark=markets[k][end-60][3];p=x.position;entryfee=x.fee*p.order.price*p.order.qty if p else 0.;state=s.b.p.state(x)
  if p:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
  if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
  result=dict(asset=asset,period=period,stage=stage,key=k,configuration=next(c for c in cfgs if c['key']==k),window=[s.r.local_s(start),s.r.local_s(end)],starting_equity=500,ending_equity=x.equity(mark),cash=x.cash,fee=x.fee,funding=0,V2=False,profile='CONTROL',exit_slippage=.0002,trades=x.journal,events=x.events,cash_events=x.cash_events,place_attempts=x.place_attempts,sizing_audit=x.sizing_audit,stats=dict(x.stats),state_at_end=state,open_entry_fee=entryfee,mark_price=mark,replacement=x.replacement,status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'and asset=='ETH'else'COMPLETE',source='BINANCE_USDT_PERPETUAL')
  (folder/'results').mkdir(exist_ok=True);s.dump(folder/'results'/f'{k}_result.json',result);np.savez_compressed(folder/'results'/f'{k}_equity.npz',marks=v);print('COMPLETE',stage,period,asset,k,x.equity(mark),flush=True)
 s.dump(done,dict(completed=True,fp=fp(),datafp=datafp,keys=list(books),status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'and asset=='ETH'else'COMPLETE'))
if __name__=='__main__':
 period,asset,stage=sys.argv[1:4]
 try:run(period,asset,stage)
 except Exception as e:s.dump(O/'runs'/stage/period/asset/'failure.json',dict(error=repr(e),traceback=traceback.format_exc(),fp=fp()));raise
