from pathlib import Path
import sys,json,hashlib,os
import features
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;P=R/'outputs/a_exit_regime_sizing';OLD=R/'outputs/adaptive_density_floors';sys.path.insert(0,str(OLD));import experiment as parent
E=parent.E;sig=parent.sig;s=parent.s;np=parent.np;FEES={'ZERO':0.,'MAKER_002_SIDE':.0002}
def dump(p,x):s.dump(p,x)
def code_fp():return hashlib.sha256(b''.join((O/n).read_bytes()for n in ['runner.py','features.py','EXPERIMENT.md'])+(parent.BASE/'engine.py').read_bytes()+(parent.BASE/'signals.py').read_bytes()).hexdigest()
def run(period,asset,stage):
 assert stage in ['train','final']
 if stage=='train':assert period in ['2020','2021','2022'];frozen=None;cfgs=[('ZERO','A_VOL')]
 else:
  frozen=json.loads((O/'FREEZE.json').read_text());assert frozen['code_fingerprint']==code_fp();assert frozen['L_fixed']>=1.5 and frozen['L_fixed']<=3;cfgs=[(fee,g)for fee in FEES for g in ['A_VOL','A_FIXED_LOW']]
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True);done=folder/f'status_{stage}.json'
 if done.exists():assert json.loads(done.read_text())['fingerprint']==code_fp();return
 for name,sha in json.loads((OLD/'CONFIG.json').read_text())['original_sources_unchanged'].items():assert sig.digest_file(R/name)==sha
 _,data,start,end,first,sources=s.z.inputs(period,asset);check=json.loads((OLD/'runs'/period/asset/'signal_check.json').read_text());assert all(sig.digest_file(Path(v['path']))==v['sha256']for v in check['data']);q=sig.make(asset,data,start,end,['A']);core=q['maps']['A'];ref=P/'runs'/period/asset;assert core=={int(k):v for k,v in json.loads((ref/'signals.json').read_text())['A'].items()};z=features.compute(q['raw']);weights={};diag=[]
 for t,side in core.items():
  i=(t-q['leg'].first)//900000-1;assert q['leg'].first+(i+1)*900000==t;weights[t]=float(z['m'][i]);diag.append(dict(signal_close_ms=t,side=side,bar_close_ms=t,close=float(q['raw'][i,4]),ATR96=float(z['ATR'][i]),v=float(z['v'][i]),v_ref=float(z['v_ref'][i])if np.isfinite(z['v_ref'][i])else None,history_valid_count=int(z['history_valid_count'][i]),m=weights[t],target_L=float(z['L'][i]),fallback=not bool(z['valid'][i]),fallback_reason=str(z['fallback_reason'][i])))
 dump(folder/'signals.json',dict(A=core,all_groups_identical=True));s.z.csv_dump(folder/'volatility_signals.csv',diag);dump(folder/'input.json',dict(data=str(data),start=start,end=end,minute_first=first,source_data_SHA=check['data'],code_fingerprint=code_fp()));native=parent.Native(asset,data,first,end);cache=parent.Cache(native);data_fp=s.o.digest(dict(core=core,weights=weights,inputs=check['data']));refs=[]
 if stage=='final':
  for label,fee in FEES.items():
   a=json.loads((ref/f'{label}_A_BASE_result.json').read_text());assert a['configuration']['exit_policy']=='fixed'and a['fee']==fee and a['window']==[start*1000,end*1000]and a['experiment_fingerprint']==json.loads((P/'CONFIG.json').read_text())['financial_fingerprint']
   for suffix in ['result.json','equity.npz']:
    src=ref/f'{label}_A_BASE_{suffix}';dest=folder/src.name
    if not dest.exists():os.link(src,dest)
    assert sig.digest_file(src)==sig.digest_file(dest);refs.append(dict(source=str(src.relative_to(R)),SHA256=sig.digest_file(src)))
  dump(folder/'baseline_reuse.json',dict(sources=refs,signals_equal=True,data_SHA_verified=True))
 for label,group in cfgs:
  fee=FEES[label];key=label+'_'+group;path=folder/(key+'_result.json');fixed=float(frozen['L_fixed'])if group=='A_FIXED_LOW'else None;wm=weights if group=='A_VOL'else{t:fixed/3 for t in core};configuration=dict(group=group,fee=fee,exit_policy='fixed',fixed_L=fixed,funding=0,slip=.0002,V2=False,freeze_SHA256=sig.digest_file(O/'FREEZE.json')if group=='A_FIXED_LOW'else None);config_fp=s.o.digest(dict(code=code_fp(),data=data_fp,configuration=configuration))
  if path.exists():assert json.loads(path.read_text())['configuration_fingerprint']==config_fp;continue
  x=E.book(asset,fee,q['leg'],core,False);x.exit_policy='fixed';market=E.Market(native,cache,x,True);E.activate(x);g=E.generator(x)(asset,leg=q['leg'],signals=core,market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False,size_multipliers=wm);print('START',stage,period,asset,key,'L_fixed',fixed,flush=True)
  for t in range(start,end,60):assert next(g)==t
  try:next(g);raise RuntimeError('overshot')
  except StopIteration as st:out=st.value
  v=np.asarray(out['marks']);E.cash_check(x);mark=float(native[end-60][3]);assert abs(v[-1]-x.equity(mark))<1e-7;state=s.b.p.state(x)
  if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
  if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
  info={r['signal_close_ms']:r for r in diag}
  for a in x.sizing_audit:
   weight=float(wm[a['signal_close_ms']]);a.update(multiplier=weight,target_leverage=3*weight,leverage=3*weight,target_notional=max(a['realized_balance'],0.)*3*weight,fallback=info[a['signal_close_ms']]['fallback']if group=='A_VOL'else False,fallback_reason=info[a['signal_close_ms']]['fallback_reason']if group=='A_VOL'else'FIXED')
  assert sum(a['accepted']for a in x.sizing_audit)==x.stats['submitted']
  result=dict(asset=asset,period=period,key=key,code_fingerprint=code_fp(),configuration_fingerprint=config_fp,configuration=configuration,stage=stage,starting_equity=500.,ending_equity=x.equity(mark),cash=x.cash,fee=fee,V2=False,trades=x.journal,events=x.events,sizing_audit=x.sizing_audit,cash_events=x.cash_events,stats=dict(x.stats),state_at_end=state,mark_price=mark,status='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS',source='BINANCE_USDT_PERPETUAL',window=[start*1000,end*1000],fallback_full_signal_count=sum(d['fallback']for d in diag),fallback_submitted_count=sum(a['accepted']and a['fallback']for a in x.sizing_audit));np.savez_compressed(folder/(key+'_equity.npz'),marks=v);dump(path,result);print('COMPLETE',stage,period,asset,key,x.equity(mark),len(x.journal),flush=True)
 dump(done,dict(complete=True,fingerprint=code_fp()))
if __name__=='__main__':run(*sys.argv[1:4])
