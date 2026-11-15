"""Targeted comparison repair: legacy reused BTC journals lack enrichment keys.
No account execution, checkpoint mutation or price/data changes.
"""
from pathlib import Path
import sys,json,hashlib,gzip,pickle
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent
sys.path.insert(0,str(O));import worker as w
s=w.s;np=w.np

def validate(period,asset):
 folder=O/'runs'/period/asset;actual=folder/'results/CONTROL_result.json';var=folder/'results/REBOUND_result.json'
 if not actual.exists()or not var.exists():return False
 q=json.loads(actual.read_text());v=json.loads(var.read_text());ref,eq=w.reference(period,asset);old=json.loads(ref.read_text());assert old['fee']==0 and old['configuration']['slip']==.0002 and not old['configuration']['funding']
 assert len(q['trades'])==len(old['trades']);extra_keys=set()
 for new,t in zip(q['trades'],old['trades']):
  assert all(new.get(k)==val for k,val in t.items()),('actual recorded field differs',period,asset,t['signal_close_ms'])
  extra_keys.update(set(new)-set(t))
 assert (q['cash'],q['ending_equity'])==(old['cash'],old['ending_equity']);assert np.array_equal(np.load(eq)['marks'],np.load(actual.with_name('CONTROL_equity.npz'))['marks'])
 for row in [q,v]:
  pos=row['state_at_end']['position'];part=row.get('open_partial_state',{}).get('partial_net')or 0.;assert abs(row['cash']-500-sum(t['net']for t in row['trades'])-part)<1e-7
  assert abs(row['cash']-500-sum(e['delta']for e in row['cash_events']))<1e-7
 with gzip.open(folder/'whole/checkpoint.pkl.gz','rb')as f:cp=pickle.load(f)
 assert cp['fp']==w.fp() and cp['next']==cp['end'] and cp['keys']==['CONTROL','REBOUND']
 config=json.loads((folder/'config.json').read_text());assert cp['end']*1000==int(__import__('datetime').datetime.fromisoformat(q['window'][1]).timestamp()*1000)
 s.dump(folder/'baseline_comparison.json',dict(passed=True,all_original_trade_fields_exact=True,trade_cash_equity_minutes_exact=True,new_enrichment_fields_not_present_in_reference=sorted(extra_keys),reference=str(ref.relative_to(R)),reference_SHA256=hashlib.sha256(ref.read_bytes()).hexdigest(),financial_engine_unchanged=True,only_comparator_fix=True))
 s.dump(folder/'status.json',dict(completed=True,fingerprint=w.fp(),status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'and asset=='ETH'else'COMPLETE',comparator='OLD_FIELDS_EXACT_NEW_ENRICHMENT_ALLOWED',original_worker_error_retained=(folder/'failure.json').exists()))
 return True
if __name__=='__main__':
 rows=[]
 for period in ['2020','2021','2022','2023','2024','2025','2026']:
  for asset in ['BTC','ETH']:
   try:passed=validate(period,asset);rows.append(dict(period=period,asset=asset,verified=passed))
   except Exception as e:rows.append(dict(period=period,asset=asset,verified=False,error=repr(e)))
 s.dump(O/'baseline_validation.json',rows);print(json.dumps(rows))
