from pathlib import Path
import sys,json,gzip,pickle,hashlib,ast,traceback
import worker as w
s=w.s;E=w.E;sig=w.sig;np=w.np;O=w.O;R=w.R
OLD=R/'outputs/rebound_annual_zero';RCFG=json.loads((OLD/'recent_config.json').read_text());START=RCFG['start_ms']//1000;NINE=RCFG['enable_rebound_ms']//1000;CUT=RCFG['raw_execution_end_ms']//1000;END=RCFG['bar_execution_end_ms']//1000
# Reuse only the pre-existing, explicitly assumed price-path classes. Do not
# import its funded/V2 entry module or execute any of its financial functions.
path=R/'outputs/nov15_15m_simulation/run.py';tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.ClassDef)and n.name in ['Native','Cache']];ns=dict(np=np,END=END);exec(compile(ast.Module(body=nodes,type_ignores=[]),'<frozen OHLC/OLHC assumption classes>','exec'),ns);BarNative=ns['Native'];BarCache=ns['Cache']
def fp():return hashlib.sha256(w.fp().encode()+Path(__file__).read_bytes()+(O/'FREEZE.json').read_bytes()+(OLD/'recent_config.json').read_bytes()).hexdigest()
def segment(folder,ctx,start,end,books,maps,market):
 folder.mkdir(parents=True,exist_ok=True);cp=folder/'checkpoint.pkl.gz';resume=start;prefix={k:np.array([])for k in books}
 if cp.exists():
  with gzip.open(cp,'rb')as f:q=pickle.load(f)
  assert(q['fp'],q['datafp'],q['start'],q['end'])==(fp(),ctx['datafp'],start,end);books=q['books'];prefix=q['marks'];resume=q['next']
  for x in books.values():x.leg=ctx['leg'];E.cash_check(x)
 if resume==end:return books,prefix
 markets={k:market(x)for k,x in books.items()};gens={k:E.generator(x)(ctx['asset'],leg=ctx['leg'],signals=maps[k],market=markets[k],start=resume*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)for k,x in books.items()};marks=prefix
 for t in range(resume,end,60):
  for k,g in gens.items():E.activate(books[k]);assert next(g)==t
  if(t+60)%86400==0 or t+60==end:
   marks={k:np.r_[prefix[k],np.array(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
   for x in books.values():E.cash_check(x);x.leg=None
   with gzip.open(cp.with_suffix('.tmp'),'wb',compresslevel=1)as f:pickle.dump(dict(fp=fp(),datafp=ctx['datafp'],start=start,end=end,next=t+60,books=books,marks=marks),f,protocol=5)
   cp.with_suffix('.tmp').replace(cp)
   for x in books.values():x.leg=ctx['leg']
   print('DAY',ctx['asset'],folder.name,s.r.local_s(t+60),flush=True)
 for k,g in gens.items():
  E.activate(books[k])
  try:next(g);raise RuntimeError('overshot')
  except StopIteration as st:assert not st.value['approximated_minutes']
 return books,marks
def output(folder,ctx,cfg,x,marks,mark,label):
 folder.mkdir(parents=True,exist_ok=True);E.cash_check(x);state=s.b.p.state(x)
 if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
 if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
 q=dict(asset=ctx['asset'],period='NOV',key=cfg['key'],configuration=cfg,window=[s.r.local_s(START),s.r.local_s(ctx['end'])],starting_equity=500.,cash=x.cash,ending_equity=x.equity(mark),fee=x.fee,funding=0,V2=False,profile='CONTROL',trades=x.journal,events=x.events,cash_events=x.cash_events,sizing_audit=x.sizing_audit,place_attempts=x.place_attempts,stats=dict(x.stats),state_at_end=state,mark_price=mark,status='COMPLETE_RAW_TRADE_SIMULATION'if label=='RAW'else'COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS',raw_execution_end_ms=CUT*1000,bar_execution_end_ms=END*1000,pre9_equity=marks[(NINE-START)//60-1],unreset_account_path_since_Nov1=True)
 s.dump(folder/(cfg['key']+'_result.json'),q);np.savez_compressed(folder/(cfg['key']+'_equity.npz'),marks=marks)
def run(asset):
 frozen=json.loads((O/'FREEZE.json').read_text());assert frozen['code_fingerprint']==w.fp();folder=O/'recent'/asset;folder.mkdir(parents=True,exist_ok=True)
 if(folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fp']==fp();return
 data=OLD/'recent_data';cfgs=w.configurations('final',frozen);names=list(dict.fromkeys(['A']+[c['source']for c in cfgs]));q=sig.make(asset,data,START,CUT,names);core=q['maps']['A'];maps={c['key']:sig.mix(core,q['maps'][c['source']])if c['hybrid']else q['maps'][c['source']]for c in cfgs};books={c['key']:E.book(asset,c['fee'],q['leg'],core,c['hybrid'])for c in cfgs};ref,olddata,oldstart,oldend,first,sources=s.z.inputs('NOV',asset)
 d=s.b.d;d.DATA=data;d.START=START;d.END=CUT;d.FIRST1=first;d.BASE='https://data.binance.vision/data/futures/um';native=s.b.p.Canonical(asset);cache=s.b.e.RawCache(asset,native,folder);ctx=dict(asset=asset,leg=q['leg'],end=CUT,datafp=s.o.digest(dict(config=RCFG,configs=cfgs,maps=maps,code=fp())))
 s.dump(folder/'signals_RAW.json',dict(A=core,candidates=q['maps'],accepted=maps));
 for name,di in q['diagnostics'].items():s.z.csv_dump(folder/(name+'_conditions_RAW.csv'),di)
 books,prefix=segment(folder/'pre9',ctx,START,NINE,books,maps,lambda x:E.Market(native,cache,x,True));s.dump(folder/'pre9_states.json',{k:dict(state=s.b.p.state(x),replacement=x.replacement,origin=x.order_info,profile=x.profile)for k,x in books.items()})
 books,tail=segment(folder/'RAW',ctx,NINE,CUT,books,maps,lambda x:E.Market(native,cache,x,True));full={k:np.r_[prefix[k],tail[k]]for k in books}
 for cfg in cfgs:
  x=books[cfg['key']];mark=E.Market(native,cache,x,True)[CUT-60][3];output(folder/'RAW/results',ctx,cfg,x,full[cfg['key']],mark,'RAW')
 if END>CUT:
  q2=sig.make(asset,data,START,END,names);core2=q2['maps']['A'];maps2={c['key']:sig.mix(core2,q2['maps'][c['source']])if c['hybrid']else q2['maps'][c['source']]for c in cfgs}
  for key in maps:assert {t:v for t,v in maps2[key].items()if t<CUT*1000}==maps[key]
  s.dump(folder/'signals_BAR.json',dict(A=core2,candidates=q2['maps'],accepted=maps2))
  for name,di in q2['diagnostics'].items():s.z.csv_dump(folder/(name+'_conditions_BAR.csv'),di)
  for order in ['OHLC','OLHC']:
   clones={k:s.o.clone(x,q2['leg'])for k,x in books.items()}
   for x in clones.values():x.core=core2
   n=BarNative(q2['raw'],order);n.end=END;c=BarCache(n);ctx2=dict(asset=asset,leg=q2['leg'],end=END,datafp=s.o.digest(dict(base=ctx['datafp'],maps=maps2,order=order)))
   clones,ext=segment(folder/order,ctx2,CUT,END,clones,maps2,lambda x:E.Market(n,c,x,True))
   for cfg in cfgs:
    key=cfg['key'];output(folder/order/'results',ctx2,cfg,clones[key],np.r_[full[key],ext[key]],n[END-60][3],order)
 s.dump(folder/'status.json',dict(completed=True,fp=fp(),raw_end_ms=CUT*1000,bar_end_ms=END*1000))
if __name__=='__main__':
 asset=sys.argv[1]
 try:run(asset)
 except Exception as e:s.dump(O/'recent'/asset/'failure.json',dict(error=repr(e),traceback=traceback.format_exc(),fp=fp()));raise
