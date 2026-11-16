from pathlib import Path
import sys,json,hashlib,os
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;P=R/'outputs/adaptive_density_floors';sys.path.insert(0,str(P));import experiment as parent
s=parent.s;sig=parent.sig;E=parent.E;np=parent.np
GROUPS={'A_BASE':'fixed','A_EXIT_UNCAPPED':'uncapped','A_EXIT_TRAIL8':'trail_from_8pct','A_REGIME_SIZE':'fixed'}
FEES={'ZERO':0.,'ASSUMED_005_SIDE':.0005,'MAKER_002_SIDE':.0002}
def dump(p,x):s.dump(p,x)
def fp():return hashlib.sha256(Path(__file__).read_bytes()+(O/'EXPERIMENT.md').read_bytes()+(parent.BASE/'engine.py').read_bytes()+(parent.BASE/'signals.py').read_bytes()+(R/'work/fit_squeeze_ladder_bot.py').read_bytes()).hexdigest()
def weights(q,core):
 raw=q['raw'];n=len(raw)//4*4;hour=3600000;closes=raw[3:n:4,4];first=q['leg'].first+hour;reg=sig.r.regime.hourly_regimes(closes,first,thresholds=sig.PAIR);out={};rows=[]
 for t,side in core.items():
  h=t//hour*hour;assert h<=t;value=reg.get(h,(None,None,None))[2];direction=1 if value is not None and value>=.10 else -1 if value is not None and value<=-.10 else 0;weight=1.3 if direction==side else .7;out[t]=weight;rows.append(dict(signal_close_ms=t,side=side,last_closed_hour_ms=h,slow_ER=value,slow_direction=direction,weight=weight,base_leverage=3,effective_requested_leverage=3*weight))
 return out,rows

def exposure(q,marks,native,start,end):
 qty=np.zeros(len(marks));n_secs=end-start;weighted=0.;hold=0.;tfinal=end*1000000
 items=[(t['opened_us'],t['closed_us'],t['quantity'],t['notional'])for t in q['trades']]
 state=q['state_at_end']
 if state['position']:
  p=state['position'];items.append((state['position_opened_us'],tfinal,p['order']['qty'],p['order']['qty']*p['order']['price']))
 for a,b,size,notional in items:
  seconds=(min(b,tfinal)-max(a,start*1000000))/1e6;assert seconds>=0;hold+=seconds;weighted+=notional*seconds
  lo=max(0,int(a//60000000-start//60));hi=min(len(qty),int(b//60000000-start//60));qty[lo:hi]=size
 prices=native.rows[(start-native.first)//60:(end-native.first)//60,3];gross=qty*prices;lev=np.divide(gross,marks,out=np.full(len(marks),np.nan),where=marks>0);valid=np.isfinite(lev);assert valid.all()or np.all(gross[~valid]==0)
 return dict(duration_weighted_entry_notional_USDT=weighted/n_secs,holding_time_fraction=hold/n_secs,minute_end_avg_gross_notional_USDT=float(np.mean(gross)),minute_end_avg_gross_equity_leverage=float(np.nanmean(lev)),minute_end_avg_leverage_when_held=float(np.mean(lev[qty>0]))if(qty>0).any()else 0.,max_minute_end_gross_equity_leverage=float(np.nanmax(lev)))

def run(period,asset):
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True);finger=fp()
 if(folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fingerprint']==finger;return
 for name,sha in json.loads((P/'CONFIG.json').read_text())['original_sources_unchanged'].items():assert sig.digest_file(R/name)==sha
 assert sig.r.model.LADDER_CAP==5 and sig.POLICY.range_squeeze_pct==.25 and sig.POLICY.range_entry_bandwidth_pct==.50
 _,data,start,end,first,sources=s.z.inputs(period,asset);old=P/'runs'/period/asset;check=json.loads((old/'signal_check.json').read_text());assert all(sig.digest_file(Path(v['path']))==v['sha256']for v in check['data']);q=sig.make(asset,data,start,end,['A']);core=q['maps']['A'];prior=json.loads((old/'signals.json').read_text())['accepted']['A'];assert core=={int(t):v for t,v in prior.items()};wm,wr=weights(q,core);dump(folder/'signals.json',dict(A=core,all_groups_identical_signals=True,Settings=vars(sig.SETTINGS),overlay=vars(sig.POLICY)));s.z.csv_dump(folder/'regime_weights.csv',wr);native=parent.Native(asset,data,first,end);cache=parent.Cache(native)
 for label,fee in FEES.items():
  for group,policy in GROUPS.items():
   key=label+'_'+group;dest=folder/(key+'_result.json');eq=folder/(key+'_equity.npz')
   if dest.exists():assert json.loads(dest.read_text())['experiment_fingerprint']==finger;continue
   print('START',period,asset,key,flush=True)
   if group=='A_EXIT_UNCAPPED'and label in ['ZERO','ASSUMED_005_SIDE']:
    original=old/f'{label}_A_result.json';oe=old/f'{label}_A_equity.npz';z=json.loads(original.read_text());assert z['fingerprint']==parent.fingerprint()and z['fee']==fee and z['configuration']['V2']is False and z['window']==[start*1000,end*1000];marks=np.load(oe)['marks'];z.update(experiment_fingerprint=finger,key=key,original_configuration=z['configuration'],configuration=dict(group=group,exit_policy=policy,fee=fee,funding=0,slip=.0002,V2=False),reused_from=dict(path=str(original.relative_to(R)),SHA256=sig.digest_file(original)),exposure=exposure(z,marks,native,start,end),actual_replayed_this_round=False)
    if not eq.exists():os.link(oe,eq)
    dump(dest,z);print('REUSED',period,asset,key,z['ending_equity'],flush=True);continue
   x=E.book(asset,fee,q['leg'],core,False);x.exit_policy=policy;assert x.profile=='CONTROL';market=E.Market(native,cache,x,True);E.activate(x);g=E.generator(x)(asset,leg=q['leg'],signals=core,market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False,size_multipliers=wm if group=='A_REGIME_SIZE'else None)
   for t in range(start,end,60):assert next(g)==t
   try:next(g);raise RuntimeError('overshot')
   except StopIteration as st:out=st.value
   marks=np.asarray(out['marks']);E.cash_check(x);mark=float(native[end-60][3]);assert abs(marks[-1]-x.equity(mark))<1e-7;state=s.b.p.state(x)
   if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   for v in x.sizing_audit:
    weight=wm[v['signal_close_ms']]if group=='A_REGIME_SIZE'else 1.;v.update(requested_weight=weight,leverage=3*weight,target_notional=max(v['realized_balance'],0.)*3*weight)
   z=dict(asset=asset,period=period,key=key,fingerprint=finger,experiment_fingerprint=finger,configuration=dict(group=group,exit_policy=policy,fee=fee,funding=0,slip=.0002,V2=False,pause_transition=True),starting_equity=500.,ending_equity=x.equity(mark),cash=x.cash,fee=fee,V2=False,trades=x.journal,events=x.events,sizing_audit=x.sizing_audit,cash_events=x.cash_events,state_at_end=state,mark_price=mark,status='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS',source='BINANCE_USDT_PERPETUAL',window=[start*1000,end*1000],actual_replayed_this_round=True);z['exposure']=exposure(z,marks,native,start,end);np.savez_compressed(eq,marks=marks);dump(dest,z);print('COMPLETE',period,asset,key,z['ending_equity'],len(x.journal),flush=True)
 dump(folder/'status.json',dict(complete=True,fingerprint=finger))
if __name__=='__main__':run(*sys.argv[1:3])
