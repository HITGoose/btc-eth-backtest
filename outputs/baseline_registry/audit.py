from pathlib import Path
import json,csv,hashlib,subprocess,datetime,os
import numpy as np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;G=Path('/workspace/offline-abcd-publish')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def write(p,rr):
 keys=list(dict.fromkeys(k for r in rr for k in r))
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rr)
def metrics(v,seed,q):
 peaks=np.maximum.accumulate(np.r_[seed,v])[1:];tr=q['trades'];n=len(tr)
 closed=sum(t['net']for t in tr);end=float(q['ending_equity']);cash=float(q['cash']if'cash'in q else q['state_at_end']['cash']);unreal=end-cash;partial=cash-seed-closed
 assert abs(end-seed-closed-unreal-partial)<1e-7 and abs(v[-1]-end)<1e-7
 if 'cash_events'in q:assert abs(cash-seed-sum(t['delta']for t in q['cash_events']))<1e-7
 return dict(ending_equity_USDT=end,return_pct=100*(end/seed-1),minute_max_drawdown_pct=float(np.max((peaks-v)/peaks)*100),closed_trades=n,win_rate_pct=100*sum(t['net']>0 for t in tr)/n if n else None,closed_net_USDT=closed,end_unrealized_USDT=unreal,open_partial_realized_net_USDT=partial,end_open_contribution_USDT=unreal+partial,open_entry_fee_USDT=0.,net_pnl_USDT=end-seed)
rows=[];evidence=[];codes=[];checks=[];old=[]
codepaths=['outputs/rebound_annual_zero/worker.py','outputs/rebound_followdown/signals.py','outputs/extra_sizing_cost_stress/replay.py','outputs/extra_sizing_cost_stress/cost_engine.py','outputs/eth_core_priority/priority_engine.py','outputs/eth_density_experiment/worker.py','outputs/adaptive_risk_exit_v2/worker.py','outputs/attribution_2026/paired_replay.py','outputs/retry_nov9_nov12/replay_comparison.py']
for name in codepaths:
 p=R/name;git=subprocess.run(['git','show','133f95967b5789b216406b30117d3703643c7d7a:'+name],cwd=G,capture_output=True);assert git.returncode==0 and git.stdout==p.read_bytes(),name;codes.append(dict(path=name,SHA256=sha(p),matches_commit_133f959=True))
for year in range(2020,2027):
 y=str(year);acc={}
 for a in ['BTC','ETH']:
  f=R/'outputs/rebound_annual_zero/runs'/y/a;p=f/'results/CONTROL_result.json';ep=p.with_name('CONTROL_equity.npz');q=json.loads(p.read_text());cfg=json.loads((f/'config.json').read_text());assert q['fee']==0 and cfg['funding']==0 and cfg['exit_slippage']==.0002 and cfg['initial_equity']==500 and not cfg['core_priority'];v=np.load(ep)['marks'];stat=json.loads((f/'status.json').read_text());assert stat['completed'];comparison=json.loads((f/'baseline_comparison.json').read_text());assert comparison['passed'];d=json.loads((f/'signals.json').read_text());assert all(t['origin']=='CORE'for t in q['trades'])
  # This identically reused CONTROL already includes V2 partial exits.
  part_events=[e for e in q['events']if e['event']=='partial_exit'];assert part_events
  for name,h in cfg['data_SHA256'].items():
   source=R/('outputs/er_partial_2020/data'if year==2020 else'outputs/attribution_2026/data'if year==2026 else f'outputs/other_years_050/{y}/data')/name;assert sha(source)==h
  ev=dict(version='ER_V2_REFERENCE',period=y,asset=a,result=str(p.relative_to(R)),result_SHA256=sha(p),equity=str(ep.relative_to(R)),equity_SHA256=sha(ep),config_SHA256=sha(f/'config.json'),source_code_commit='133f95967b5789b216406b30117d3703643c7d7a',action='REUSED_EXISTING_ACCOUNT',V2_partial_exit_events=len(part_events),original_status=q['status'],baseline_comparison=comparison,data_SHA256=cfg['data_SHA256']);published=O/'reused/ER_V2_REFERENCE'/y/a;published.mkdir(parents=True,exist_ok=True)
  for src,name in [(p,'result.json'),(ep,'equity.npz')]:
   dst=published/name
   if not dst.exists():os.link(src,dst)
   assert sha(src)==sha(dst)
  ev.update(published_result=str((published/'result.json').relative_to(R)),published_equity=str((published/'equity.npz').relative_to(R)));evidence.append(ev)
  r=dict(version='ER_V2_REFERENCE',period=y,asset=a,status=q['status'],action='REUSED_EXISTING_ACCOUNT',start_Beijing=cfg['start_Beijing'],end_Beijing=cfg['end_Beijing'],**metrics(v,500,q));rows.append(r);acc[a,'ER']=(q,v,r);checks.append(dict(version=r['version'],period=y,asset=a,ledger_closed=True))
  mf=O/'runs'/y/a;mp=mf/'results/MA_DIRECTION_REFERENCE_result.json'
  if (mf/'status.json').exists():
   m=json.loads(mp.read_text());mv=np.load(mp.with_name('MA_DIRECTION_REFERENCE_equity.npz'))['marks'];r=dict(version='MA_DIRECTION_REFERENCE',period=y,asset=a,status=json.loads((mf/'status.json').read_text())['status'],action='SUPPLEMENTARY_RAW_REPLAY',start_Beijing=cfg['start_Beijing'],end_Beijing=cfg['end_Beijing'],**metrics(mv,500,m));rows.append(r);acc[a,'MA']=(m,mv,r);checks.append(dict(version=r['version'],period=y,asset=a,ledger_closed=True));evidence.append(dict(version=r['version'],period=y,asset=a,result=str(mp.relative_to(R)),result_SHA256=sha(mp),equity=str(mp.with_name('MA_DIRECTION_REFERENCE_equity.npz').relative_to(R)),equity_SHA256=sha(mp.with_name('MA_DIRECTION_REFERENCE_equity.npz')),action='SUPPLEMENTARY_RAW_REPLAY',original_status=m['status']))
  else:
   fail=json.loads((mf/'failure.json').read_text())if(mf/'failure.json').exists()else{};progress=json.loads((mf/'whole/progress.json').read_text())if(mf/'whole/progress.json').exists()else{};rows.append(dict(version='MA_DIRECTION_REFERENCE',period=y,asset=a,status='UNVERIFIED',action='ATTEMPTED_BLOCKED'if fail else'RUNNING_OR_PENDING',failure=fail.get('error'),progress_through=progress.get('next_time')))
 for name,version in [('ER','ER_V2_REFERENCE'),('MA','MA_DIRECTION_REFERENCE')]:
  if('BTC',name)in acc and('ETH',name)in acc:
   x,xv,xr=acc['BTC',name];z,zv,zr=acc['ETH',name];assert len(xv)==len(zv)and xr['start_Beijing']==zr['start_Beijing']and xr['end_Beijing']==zr['end_Beijing'];q=dict(ending_equity=x['ending_equity']+z['ending_equity'],cash=x.get('cash',x['state_at_end']['cash'])+z.get('cash',z['state_at_end']['cash']),trades=x['trades']+z['trades']);rows.append(dict(version=version,period=y,asset='COMBINED',status='COMPLETED_WITH_DATA_ANOMALY'if year==2025 else'COMPLETE',action='COMBINE_SAME_MINUTE_ACCOUNTS',start_Beijing=xr['start_Beijing'],end_Beijing=xr['end_Beijing'],**metrics(xv+zv,1000,q)))
  else:rows.append(dict(version=version,period=y,asset='COMBINED',status='UNVERIFIED',action='NO_COMPLETE_SAME_ENGINE_PAIR'))
# Old2026 is evidence of recovered rule, NOT substituted for the unified engine.
for a in ['BTC','ETH']:
 p=R/'outputs/attribution_2026'/f'{a}_MA_result.json';q=json.loads(p.read_text());v=np.load(p.with_name(f'{a}_MA_equity.npy'));r=dict(version='MA_DIRECTION_REFERENCE_HISTORICAL_ENGINE',period='2026',asset=a,status='HISTORICAL_COMPLETE_NOT_UNIFIED_ENGINE',source=str(p.relative_to(R)),source_SHA256=sha(p),**metrics(v,500,q));old.append(r)
 published=O/'historical/2026'/a;published.mkdir(parents=True,exist_ok=True);dst=published/'MA_result.json'
 if not dst.exists():os.link(p,dst)
 if not(published/'MA_equity.npz').exists():np.savez_compressed(published/'MA_equity.npz',marks=v)
for r in rows:
 other=next((z for z in rows if z['period']==r['period']and z['asset']==r['asset']and z['version']!=r['version']and z.get('return_pct')is not None),None)
 if r.get('return_pct')is not None and other:r.update(difference_vs_other_USDT=r['net_pnl_USDT']-other['net_pnl_USDT'],return_difference_vs_other_pp=r['return_pct']-other['return_pct'],drawdown_difference_vs_other_pp=r['minute_max_drawdown_pct']-other['minute_max_drawdown_pct'])
write(O/'comparison.csv',rows);write(O/'historical_ma_2026.csv',old);write(O/'source_code_manifest.csv',codes);dump(O/'account_reuse_manifest.json',evidence);dump(O/'account_checks.json',checks)
dump(O/'audit_summary.json',dict(reused_ER_accounts=sum(r.get('action')=='REUSED_EXISTING_ACCOUNT'for r in rows),completed_MA_supplementary_accounts=sum(r.get('action')=='SUPPLEMENTARY_RAW_REPLAY'for r in rows),complete_comparable_intervals=sum(r['asset']=='COMBINED'and r['version']=='MA_DIRECTION_REFERENCE'and r.get('return_pct')is not None for r in rows),source_files_match_commit133=True,main_changed=False,actual_deployment='UNKNOWN',built_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()))
print(json.loads((O/'audit_summary.json').read_text()))
