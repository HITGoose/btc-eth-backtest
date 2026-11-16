from pathlib import Path
import sys,json,hashlib,os,importlib.util
sp=importlib.util.spec_from_file_location('failed_breakout_hooks',Path(__file__).resolve().parent/'engine.py');custom=importlib.util.module_from_spec(sp);sys.modules[sp.name]=custom;sp.loader.exec_module(custom)
parent=custom.parent;E=custom.E;sig=custom.sig;s=custom.s;np=custom.np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;P=R/'outputs/a_exit_regime_sizing';OLD=R/'outputs/adaptive_density_floors';FEES={'ZERO':0.,'MAKER_002_SIDE':.0002}
def dump(p,x):s.dump(p,x)
def fp():return hashlib.sha256(b''.join((O/n).read_bytes()for n in ['runner.py','engine.py','EXPERIMENT.md'])+(parent.BASE/'engine.py').read_bytes()+(R/'work/fit_squeeze_ladder_bot.py').read_bytes()).hexdigest()
def run(period,asset):
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True);finger=fp()
 if(folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fingerprint']==finger;return
 for name,sha in json.loads((OLD/'CONFIG.json').read_text())['original_sources_unchanged'].items():assert sig.digest_file(R/name)==sha
 _,data,start,end,first,sources=s.z.inputs(period,asset);checks=json.loads((OLD/'runs'/period/asset/'signal_check.json').read_text());assert all(sig.digest_file(Path(v['path']))==v['sha256']for v in checks['data']);q=sig.make(asset,data,start,end,['A']);core=q['maps']['A'];ref=P/'runs'/period/asset;oldcore=json.loads((ref/'signals.json').read_text())['A'];assert core=={int(k):v for k,v in oldcore.items()};c=q['raw'][:,4];lines=np.stack([sig.r.model.sma(c,n)for n in [20,60,120]]+[sig.r.model.ema(c,n)for n in [20,60,120]]);lo=lines.min(axis=0);hi=lines.max(axis=0);assert np.allclose(100*(hi-lo)/c,q['leg'].width,equal_nan=True);dump(folder/'signals.json',dict(A_BASE=core,A_FAIL_EXIT=core,identical=True));native=parent.Native(asset,data,first,end);cache=parent.Cache(native);refs=[]
 for label,fee in FEES.items():
  original=ref/f'{label}_A_BASE_result.json';z=json.loads(original.read_text());assert z['configuration']['exit_policy']=='fixed'and z['fee']==fee and z['window']==[start*1000,end*1000]and z['experiment_fingerprint']==json.loads((P/'CONFIG.json').read_text())['financial_fingerprint']
  for suffix in ['result.json','equity.npz']:
   src=ref/f'{label}_A_BASE_{suffix}';dest=folder/src.name
   if not dest.exists():os.link(src,dest)
   assert sig.digest_file(src)==sig.digest_file(dest);refs.append(dict(source=str(src.relative_to(R)),SHA256=sig.digest_file(src)))
  key=label+'_A_FAIL_EXIT';path=folder/(key+'_result.json')
  if path.exists():assert json.loads(path.read_text())['fingerprint']==finger;continue
  x=custom.book(asset,fee,q['leg'],core,c,lo,hi);market=E.Market(native,cache,x,True);E.activate(x);g=E.generator(x)(asset,leg=q['leg'],signals=core,market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False);print('START',period,asset,key,flush=True)
  for t in range(start,end,60):
   x.check_closed(t);market.optimized=not bool(x.fail_request and t>=x.fail_request['ready_s']);assert next(g)==t
  try:next(g);raise RuntimeError('overshot')
  except StopIteration as st:out=st.value
  v=np.asarray(out['marks']);E.cash_check(x);mark=float(native[end-60][3]);assert abs(v[-1]-x.equity(mark))<1e-7;state=s.b.p.state(x)
  if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
  if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
  result=dict(asset=asset,period=period,key=key,fingerprint=finger,configuration=dict(group='A_FAIL_EXIT',exit_policy='fixed',fee=fee,funding=0,slip=.0002,V2=False,pause_transition=True,leverage=3),starting_equity=500.,ending_equity=x.equity(mark),cash=x.cash,fee=fee,V2=False,trades=x.journal,events=x.events,sizing_audit=x.sizing_audit,cash_events=x.cash_events,stats=dict(x.stats),exit_checks=x.exit_checks,fail_request_at_end=x.fail_request,fail_state_at_end=dict(checked=getattr(x.position,'fail_checked',None),due_s=getattr(x.position,'fail_check_due_s',None))if x.position else None,state_at_end=state,mark_price=mark,status='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS',source='BINANCE_USDT_PERPETUAL',window=[start*1000,end*1000]);np.savez_compressed(folder/(key+'_equity.npz'),marks=v);dump(path,result);print('COMPLETE',period,asset,key,x.equity(mark),len(x.journal),'early exits',sum(t['reason']=='failed_breakout_exit'for t in x.journal),flush=True)
 dump(folder/'baseline_reuse.json',dict(sources=refs,signals_equal=True,data_SHA_verified=True));dump(folder/'status.json',dict(complete=True,fingerprint=finger))
if __name__=='__main__':run(*sys.argv[1:3])
