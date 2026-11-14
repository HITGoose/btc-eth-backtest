"""Export trustworthy checkpoint prefix evidence, never annual results."""
from pathlib import Path
import gzip,pickle,json
import strategy as z
import priority_engine # trusted project pickle class resolution
OUT=z.OUT
if __name__=='__main__':
 index=[]
 for cp in list((OUT/'runs').rglob('checkpoint.pkl.gz'))+list((OUT/'cost_isolation').rglob('checkpoint.pkl.gz')):
  if(cp.parent/'status.json').exists()and json.loads((cp.parent/'status.json').read_text()).get('completed'):continue
  with gzip.open(cp,'rb')as f:saved=pickle.load(f)
  records=[]
  for key,b in saved['books'].items():
   records.append(dict(key=key,cutoff_exclusive=z.r.local_s(saved['next_time']),cash=b.cash,ending_prefix_equity=float(saved['marks'][key][-1]),trades=b.journal,events=b.events,cash_events=b.cash_events,place_attempts=b.place_attempts,stats=dict(b.stats),state=z.p.state(b),source_tag_at_cutoff=b.order_info,replacement=b.replacement,shadow_snapshot_count=len(b.shadow_snapshots),status='INCOMPLETE_PREFIX_ONLY_NOT_ANNUAL_RESULT',after_cutoff='NOT_EVALUATED'))
  path=cp.parent/'incomplete_prefix.json.gz'
  with gzip.open(path,'wt',encoding='utf-8')as f:json.dump(dict(code_fingerprint=saved['code_fingerprint'],prefix=records),f,ensure_ascii=False,default=lambda x:x.item())
  index.append(dict(path=str(path.relative_to(OUT)),cutoff=z.r.local_s(saved['next_time']),keys=list(saved['books']),status='UNVERIFIED_ANNUAL'))
 z.dump(OUT/'incomplete_index.json',index);print('EXPORTED',len(index),'checkpoint prefixes')
