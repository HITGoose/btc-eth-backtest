from pathlib import Path
import json,datetime,hashlib,csv
import numpy as np
import worker as w
O=w.O
rows=[];summaries=[];evidence=[]
for period in w.TRAIN:
 for asset in ['BTC','ETH']:
  p=O/'runs/train'/period/asset/'status.json';d=json.loads(p.read_text());assert d['completed']and d['fp']==w.fp();evidence.append(dict(period=period,asset=asset,status_SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),data_fingerprint=d['datafp']))
for name,spec in w.sig.SPECS.items():
 yr=[]
 for period in w.TRAIN:
  q={a:json.loads((O/'runs/train'/period/a/'results'/f'ZERO_{name}_result.json').read_text())for a in ['BTC','ETH']};v={a:np.load(O/'runs/train'/period/a/'results'/f'ZERO_{name}_equity.npz')['marks']for a in ['BTC','ETH']};assert q['BTC']['window']==q['ETH']['window']and len(v['BTC'])==len(v['ETH']);eq=v['BTC']+v['ETH'];peak=np.maximum.accumulate(np.r_[1000.,eq]);dd=float(np.max(100*(1-np.r_[1000.,eq]/peak)));ret=100*(eq[-1]/1000-1);filled=sum(t['stats'].get('long',0)+t['stats'].get('short',0)for t in q.values());closed=sum(len(t['trades'])for t in q.values());r=dict(candidate=name,family=spec['family'],parameters=spec['parameters'],period=period,return_pct=float(ret),max_drawdown_pct=dd,score_component=float(ret-dd),filled_trades=filled,closed_trades=closed);rows.append(r);yr.append(r)
 summaries.append(dict(candidate=name,family=spec['family'],parameters=spec['parameters'],score=float(np.mean([r['score_component']for r in yr])),worst_annual_drawdown_pct=max(r['max_drawdown_pct']for r in yr),total_filled_trades=sum(r['filled_trades']for r in yr),total_closed_trades=sum(r['closed_trades']for r in yr),preset_index=list(w.sig.SPECS).index(name)))
def order(x):return(-x['score'],x['worst_annual_drawdown_pct'],x['total_filled_trades'],x['preset_index'])
b=sorted([r for r in summaries if r['family']=='B'],key=order)[0];c=sorted([r for r in summaries if r['family']=='C'],key=order)[0];d=sorted([b,c],key=order)[0];a=next(r for r in summaries if r['candidate']=='A')
for filename,rr in [('training_yearly_scores.csv',rows),('training_candidate_scores.csv',summaries)]:
 with(O/filename).open('w',encoding='utf-8-sig',newline='')as f:writer=csv.DictWriter(f,fieldnames=list(rr[0]));writer.writeheader();writer.writerows(rr)
freeze=dict(status='FROZEN_BEFORE_POST2022_OR_FEES',frozen_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),code_fingerprint=w.fp(),B=b['candidate'],B_parameters=b['parameters'],C=c['candidate'],C_parameters=c['parameters'],D_source=d['candidate'],D_family=d['family'],training_periods=w.TRAIN,selection_fee=0,funding=0,score='mean over3 intervals of combined(return_pct-max_drawdown_pct)',tie_breakers=['lower worst annual drawdown','fewer total entry fills including open','original preset order'],BTC_ETH_same_parameters=True,A_pause_transition=False,no_V2=True,no_rebound=True,exit_slippage=.0002,candidate_scores=summaries,training_evidence=evidence,A_score=a['score'],B_vs_A_score=b['score']-a['score'],C_vs_A_score=c['score']-a['score'],not_new_unseen_out_of_sample=True)
p=O/'FREEZE.json'
if p.exists():
 old=json.loads(p.read_text());assert all(old[k]==freeze[k]for k in ['code_fingerprint','B','C','D_source','candidate_scores','training_evidence']);print('EXISTING_FREEZE',old['frozen_UTC'])
else:
 with p.open('x')as f:json.dump(freeze,f,ensure_ascii=False,indent=2)
 (O/'FREEZE.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  FREEZE.json\n');p.chmod(0o444);print('FROZEN',freeze['frozen_UTC'],b['candidate'],c['candidate'],'Dsource',d['candidate'],flush=True)
