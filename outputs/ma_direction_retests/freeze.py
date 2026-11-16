"""Only original training rules, no new grid; atomically freeze before evaluation."""
import common as c
from catalog import SPECS
import json,datetime
np=c.np
def metric(q,v):
 x=np.r_[1000.,v];return 100*(q/1000-1),float(np.max(100*(1-x/np.maximum.accumulate(x))))
def fixed():
 vals=[];evidence=[]
 for y in [2020,2021,2022]:
  for a in ['BTC','ETH']:
   p=c.existing('VOL_SIZE',y,a)
   if not p:raise RuntimeError('MA_VOL_SIZE_TRAINING_INCOMPLETE: fixed leverage cannot be invented')
   q=json.loads((p/'result.json').read_text());accepted={r['signal_close_ms'] for r in q['sizing_audit']if r['accepted']};rows=[r for r in q['events']if r['event']=='volatility_sizing'and r['signal_close_ms']in accepted]
   assert len(rows)==len(accepted);vals.extend(3*r['multiplier']for r in rows);evidence.append(dict(year=y,asset=a,result_SHA256=c.digest(p/'result.json'),accepted_orders=len(rows)))
 assert vals;return dict(L_fixed=float(np.mean(vals)),accepted_orders=len(vals),calibration='2020-2022 combined per accepted order, arithmetic mean target L',evidence=evidence)
def adaptive(family):
 rows=[]
 for key,cfg in SPECS.items():
  if cfg.get('family')!=family:continue
  years=[]
  for y in [2020,2021,2022]:
   paths=[c.existing(key,y,a)for a in ['BTC','ETH']];assert all(paths),'Training incomplete, cannot freeze'
   q=[json.loads((p/'result.json').read_text())for p in paths];m=[np.load(p/'equity.npz')['marks']for p in paths];assert m[0].shape==m[1].shape
   ret,dd=metric(sum(t['ending_equity']for t in q),m[0]+m[1]);fills=sum(t['stats']['long']+t['stats']['short']for t in q);years.append(dict(year=y,return_pct=ret,max_drawdown_pct=dd,entry_fills=fills,evidence=[c.digest(p/'result.json')for p in paths]))
  rows.append(dict(key=key,parameters=cfg['parameters'],score=float(np.mean([x['return_pct']-x['max_drawdown_pct']for x in years])),worst_drawdown=max(x['max_drawdown_pct']for x in years),total_fills=sum(x['entry_fills']for x in years),preset_index=list(SPECS).index(key),years=years))
 winner=sorted(rows,key=lambda x:(-x['score'],x['worst_drawdown'],x['total_fills'],x['preset_index']))[0]
 return {family+'_winner':winner['key'],family+'_scores':rows}
def save(name,q):
 p=c.OUT/f'freeze_{name}.json';q.update(fingerprint=c.fingerprint(),training_years=[2020,2021,2022],V2=False,fee=0,not_unseen_out_of_sample=True)
 if p.exists():assert json.loads(p.read_text())==q,'Frozen selection differs; preserve old and use a new experiment root'
 else:c.dump(p,q)
 c.backup(c.OUT) # contains only local experiment products, not market cache
 return q
