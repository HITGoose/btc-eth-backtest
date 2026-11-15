from pathlib import Path
import sys,json,hashlib,os
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;P=R/'outputs/adaptive_density_floors';sys.path.insert(0,str(P));import experiment as parent
s=parent.s;sig=parent.sig;E=parent.E;np=parent.np
GROUPS=['A_MACRO_60','A_FOMC_60']
def fp():return hashlib.sha256(Path(__file__).read_bytes()+(O/'EXPERIMENT.md').read_bytes()+(O/'calendar.json').read_bytes()+(P/'experiment.py').read_bytes()+(parent.BASE/'engine.py').read_bytes()+(parent.BASE/'signals.py').read_bytes()).hexdigest()
def blocked(t,kind,events):return any(e['release_ms']<=t<=e['release_ms']+3600000 and(kind=='A_MACRO_60'or e['kind']=='FOMC')for e in events)
def dump(path,x):s.dump(path,x)
def run(period,asset):
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True);fingerprint=fp()
 if(folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fingerprint']==fingerprint;return
 for name,sha in json.loads((P/'CONFIG.json').read_text())['original_sources_unchanged'].items():assert sig.digest_file(R/name)==sha
 assert sig.SETTINGS.squeeze_threshold==.25 and sig.POLICY.pause_transition is True
 _,data,start,end,first,sources=s.z.inputs(period,asset);old=P/'runs'/period/asset;oldcheck=json.loads((old/'signal_check.json').read_text());assert all(sig.digest_file(Path(v['path']))==v['sha256']for v in oldcheck['data'])
 # Invoke only original fixed A, never the adaptive/clip wrapper.
 q=sig.make(asset,data,start,end,['A']);core=q['maps']['A'];prior=json.loads((old/'signals.json').read_text())['accepted']['A'];assert core=={int(t):v for t,v in prior.items()};events=json.loads((O/'calendar.json').read_text())['events'];maps={'A':core,**{g:{t:v for t,v in core.items()if not blocked(t,g,events)}for g in GROUPS}}
 dump(folder/'signals.json',dict(accepted=maps,fixed_Settings=vars(sig.SETTINGS),fixed_overlay=vars(sig.POLICY)));s.z.csv_dump(folder/'A_conditions.csv',q['diagnostics']['A']);refs=[]
 for label,fee in [('ZERO',0.),('ASSUMED_005_SIDE',.0005)]:
  for suffix in ['result.json','equity.npz']:
   p=old/f'{label}_A_{suffix}';dest=folder/p.name
   if suffix=='result.json':
    z=json.loads(p.read_text());assert z['fingerprint']==parent.fingerprint()and z['fee']==fee and z['configuration']['V2']is False and z['configuration']['pause_transition']is True and z['window']==[start*1000,end*1000]
   if not dest.exists():os.link(p,dest)
   assert sig.digest_file(p)==sig.digest_file(dest);refs.append(dict(source=str(p.relative_to(R)),copied_as=str(dest.relative_to(R)),SHA256=sig.digest_file(p)))
 dump(folder/'baseline_reuse.json',dict(original_A_signals_equal=True,data_SHA_verified=True,source_results=refs,original_financial_fingerprint=parent.fingerprint(),new_financial_fingerprint=fingerprint))
 native=parent.Native(asset,data,first,end);cache=parent.Cache(native)
 for label,fee in [('ZERO',0.),('ASSUMED_005_SIDE',.0005)]:
  for group in GROUPS:
   key=label+'_'+group;dest=folder/(key+'_result.json')
   if dest.exists():assert json.loads(dest.read_text())['fingerprint']==fingerprint;continue
   x=E.book(asset,fee,q['leg'],core,False);market=E.Market(native,cache,x,True);E.activate(x);g=E.generator(x)(asset,leg=q['leg'],signals=maps[group],market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
   print('START',period,asset,key,'signals',len(maps[group]),flush=True)
   for t in range(start,end,60):assert next(g)==t
   try:next(g);raise RuntimeError('overshot')
   except StopIteration as st:out=st.value
   marks=np.asarray(out['marks']);E.cash_check(x);mark=float(native[end-60][3]);assert abs(marks[-1]-x.equity(mark))<1e-7;state=s.b.p.state(x)
   if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   result=dict(asset=asset,period=period,key=key,fingerprint=fingerprint,configuration=dict(group=group,fee=fee,funding=0,slip=.0002,V2=False,pause_transition=True,historical_threshold=.25,current_range_threshold=.50),starting_equity=500.,ending_equity=x.equity(mark),cash=x.cash,fee=fee,V2=False,trades=x.journal,events=x.events,sizing_audit=x.sizing_audit,cash_events=x.cash_events,state_at_end=state,mark_price=mark,status='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS',not_observed_tick_path=True,source='BINANCE_USDT_PERPETUAL',window=[start*1000,end*1000])
   # Install equity first, then result; reports read only complete coin-years.
   np.savez_compressed(folder/(key+'_equity.npz'),marks=marks);dump(dest,result);print('COMPLETE',period,asset,key,result['ending_equity'],len(x.journal),flush=True)
 dump(folder/'status.json',dict(complete=True,fingerprint=fingerprint))
if __name__=='__main__':run(*sys.argv[1:3])
