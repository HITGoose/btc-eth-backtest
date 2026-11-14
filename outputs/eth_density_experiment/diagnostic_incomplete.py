"""Failed cohorts: exact saved-prefix occupancy; unknown thereafter, never fake flat."""
from pathlib import Path
import importlib.util,sys,json,pickle,gzip
import numpy as np
import strategy as s
import analysis_helpers as h
collector_spec=importlib.util.spec_from_file_location("density_readonly_collector",Path(__file__).resolve().parent/"collect.py")
collector=importlib.util.module_from_spec(collector_spec);collector_spec.loader.exec_module(collector)
load_conditions=collector.load_conditions
OUT=s.OUT
sp=importlib.util.spec_from_file_location('density_incomplete_book',OUT/'worker.py');w=importlib.util.module_from_spec(sp);sys.modules[sp.name]=w;sp.loader.exec_module(w)
# Only trusted, locally generated experiment checkpoint, never an uploaded pickle.
Control=w.Control;Dynamic=w.Dynamic

def write():
 checkpoint=OUT/'runs/2025/ETH/checkpoint.pkl.gz'
 if not checkpoint.exists():return
 with gzip.open(checkpoint,'rb')as f:saved=pickle.load(f)
 features=load_conditions(OUT/'runs/2025/ETH');signals={float(k):{int(t):v for t,v in values.items()}for k,values in h.read(OUT/'runs/2025/ETH/signals.json').items()};config=h.read(OUT/'runs/2025/ETH/config.json');cutoff=saved['next_time']*1000000
 snapshots=[]
 for cost in ('ZERO','ASSUMED_005_SIDE'):
  output=[]
  for group in ('C','D','E','F'):
   key=cost+'_'+group;b=saved['books'][key];prefix=np.asarray(saved['marks'][key]);state=s.p.state(b)
   q=dict(asset='ETH',window=[config['period'][0],s.r.local_s(saved['next_time'])],trades=b.journal,events=b.events,place_attempts=b.place_attempts,cash_events=b.cash_events,state_at_end=state,fee=b.fee,cash=b.cash,ending_equity=float(prefix[-1]),open_contribution=float(prefix[-1])-500-sum(t['net']for t in b.journal))
   if b.position:q['open_partial_state']={k:getattr(b.position,k,None)for k in ('initial_quantity','partial_fills','partial_net')}
   snapshots.append(dict(cost=cost,group=group,complete_period=False,snapshot_scope='trusted saved checkpoint only; not full2025 result',**q))
   threshold=s.GROUPS[group][0];known={t:v for t,v in features.items()if t*1000<cutoff};unknown={t:v for t,v in features.items()if t*1000>=cutoff};dec=h.diagnostic(q,known,signals[threshold],threshold)
   for row in dec.values():output.append(dict(period='2025',asset='ETH',cost=cost,group=group,occupancy_verified_through_us=cutoff,**row))
   for stamp,feature in unknown.items():
    output.append(dict(period='2025',asset='ETH',cost=cost,group=group,**feature,threshold_pct=threshold,eligible=signals[threshold].get(stamp)==feature['side'],execution_status='NOT_EVALUATED_DATA_BLOCK',scheduled_submission_us=(stamp+10000)*1000,observed_submission_check_us='NOT_EVALUATED',occupancy_source='NOT_EVALUATED_AFTER_SAVED_CHECKPOINT',has_position='NOT_EVALUATED',has_pending_order='NOT_EVALUATED',occupying_signal_close_ms='NOT_EVALUATED',pending_signal_close_ms='NOT_EVALUATED',realized_balance_at_check='NOT_EVALUATED',occupancy_verified_through_us=cutoff))
  output.sort(key=lambda x:(x['signal_close_ms'],x['group']));s.csv_dump(OUT/f'diagnostics_unverified_2025_{cost}.csv.gz',output);print(cost,'prefix-and-unknown diagnostic rows',len(output),flush=True)
 with gzip.open(OUT/'incomplete_snapshots_2025.json.gz','wt',encoding='utf-8')as f:json.dump(snapshots,f,ensure_ascii=False)
if __name__=='__main__':write()
