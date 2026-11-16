from pathlib import Path
import sys,json,hashlib,os
import features,atr_engine
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;P=R/'outputs/a_exit_regime_sizing';OLD=R/'outputs/adaptive_density_floors';sys.path.insert(0,str(OLD));import experiment as parent
E=parent.E;sig=parent.sig;s=parent.s;np=parent.np;Book=atr_engine.build(E);FEES={'ZERO':0.,'MAKER_002_SIDE':.0002}
def dump(p,x):s.dump(p,x)
def fp():return hashlib.sha256(b''.join((O/n).read_bytes()for n in ['runner.py','features.py','atr_engine.py','EXPERIMENT.md'])+(parent.BASE/'engine.py').read_bytes()+(parent.BASE/'signals.py').read_bytes()).hexdigest()
def run(period,asset):
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True);done=folder/'status.json'
 if done.exists():assert json.loads(done.read_text())['fingerprint']==fp();return
 for name,sha in json.loads((OLD/'CONFIG.json').read_text())['original_sources_unchanged'].items():assert sig.digest_file(R/name)==sha
 assert sig.r.model.LADDER_CAP==5 and sig.POLICY.pause_transition is True
 _,data,start,end,first,sources=s.z.inputs(period,asset);check=json.loads((OLD/'runs'/period/asset/'signal_check.json').read_text());assert all(sig.digest_file(Path(v['path']))==v['sha256']for v in check['data']);q=sig.make(asset,data,start,end,['A']);core=q['maps']['A'];ref=P/'runs'/period/asset;assert core=={int(k):v for k,v in json.loads((ref/'signals.json').read_text())['A'].items()};_,atr=features.atr96(q['raw']);atrs={};diag=[]
 for t,side in core.items():
  i=(t-q['leg'].first)//900000-1;assert q['leg'].first+(i+1)*900000==t;atrs[t]=float(atr[i]);price=E.r.model.limit_price(asset,float(q['raw'][i,4]),side,nearest_tick=True);p=features.parameters(atrs[t],price);diag.append(dict(signal_close_ms=t,side=side,bar_close_ms=t,limit_price=price,**p))
 dump(folder/'signals.json',dict(A_BASE=core,A_ATR_STOP=core));s.z.csv_dump(folder/'signal_ATR.csv',diag);dump(folder/'input.json',dict(data=str(data),start=start,end=end,minute_first=first,source_data_SHA=check['data'],original_signal_check_status=check.get('status'),code_fingerprint=fp()));native=parent.Native(asset,data,first,end);cache=parent.Cache(native);refs=[];datafp=s.o.digest(dict(core=core,ATR=diag,inputs=check['data']))
 for label,fee in FEES.items():
  a=json.loads((ref/f'{label}_A_BASE_result.json').read_text());assert a['configuration']['exit_policy']=='fixed'and a['fee']==fee and a['window']==[start*1000,end*1000]and a['experiment_fingerprint']==json.loads((P/'CONFIG.json').read_text())['financial_fingerprint']
  for suffix in ['result.json','equity.npz']:
   src=ref/f'{label}_A_BASE_{suffix}';dest=folder/src.name
   if not dest.exists():os.link(src,dest)
   assert sig.digest_file(src)==sig.digest_file(dest);refs.append(dict(source=str(src.relative_to(R)),SHA256=sig.digest_file(src)))
 dump(folder/'baseline_reuse.json',dict(sources=refs,signals_equal=True,data_SHA_verified=True))
 for label,fee in FEES.items():
  key=label+'_A_ATR_STOP';path=folder/(key+'_result.json');configuration=dict(group='A_ATR_STOP',fee=fee,exit_policy='fixed',funding=0,slip=.0002,V2=False,pause_transition=True,ATR_period=96,ATR_multiplier=2,d_min=.01,d_max=.03,planned_risk_cap=.06,max_L=3.);configfp=s.o.digest(dict(code=fp(),data=datafp,configuration=configuration))
  if path.exists():assert json.loads(path.read_text())['configuration_fingerprint']==configfp;continue
  x=E.book(asset,fee,q['leg'],core,False);x.__class__=Book;x.exit_policy='fixed';x.signal_ATR=atrs;assert isinstance(x,s.z.w.Control)and not isinstance(x,s.z.w.Dynamic);market=E.Market(native,cache,x,True);E.activate(x);g=E.generator(x)(asset,leg=q['leg'],signals=core,market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False);print('START',period,asset,key,flush=True)
  for t in range(start,end,60):assert next(g)==t
  try:next(g);raise RuntimeError('overshot')
  except StopIteration as st:out=st.value
  v=np.asarray(out['marks']);E.cash_check(x);mark=float(native[end-60][3]);assert abs(v[-1]-x.equity(mark))<1e-7;state=s.b.p.state(x)
  if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'],atr_parameters=x.position.order.atr_parameters)
  if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'],atr_parameters=x.order.atr_parameters)
  assert sum(a['accepted']for a in x.sizing_audit)==x.stats['submitted']
  result=dict(asset=asset,period=period,key=key,code_fingerprint=fp(),configuration_fingerprint=configfp,configuration=configuration,starting_equity=500.,ending_equity=x.equity(mark),cash=x.cash,fee=fee,V2=False,trades=x.journal,events=x.events,sizing_audit=x.sizing_audit,cash_events=x.cash_events,stats=dict(x.stats),state_at_end=state,mark_price=mark,status=a['status'],source='BINANCE_USDT_PERPETUAL',window=[start*1000,end*1000],fallback_signal_count=sum(r['fallback']for r in diag),fallback_submitted_count=sum(r['accepted']and r['fallback']for r in x.sizing_audit));np.savez_compressed(folder/(key+'_equity.npz'),marks=v);dump(path,result);print('COMPLETE',period,asset,key,x.equity(mark),len(x.journal),flush=True)
 dump(done,dict(complete=True,fingerprint=fp()))
if __name__=='__main__':run(*sys.argv[1:3])
