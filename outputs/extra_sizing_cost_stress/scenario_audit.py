"""Every2025 configuration: verify all9 own histories and compare outcomes anew."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,gzip
import shared as s
np=s.np;O=s.OUT

def main():
 rawsha=hashlib.file_digest(s.b.ARCHIVE.open('rb'),'sha256').hexdigest();assert rawsha==s.b.EXPECTED_SHA
 manifest=json.loads((s.OLD/'whitelist_manifest.json').read_text())
 for name,sha in manifest['parsed_arrays_SHA256'].items():assert hashlib.file_digest((s.OLD/'raw_audit'/(name+'.npy')).open('rb'),'sha256').hexdigest()==sha
 cutsec=manifest['merge_second'];checks=[];differences=[];metrics=[]
 roots=[O/'runs/2025/ETH/baseline',O/'sizing_only/runs/2025/ETH/experiment',O/'funded/runs/2025/ETH/funded',O/'through_exact_clock/runs/2025/ETH/through']
 for folder in roots:
  if not(folder/'status.json').exists():continue
  pool=json.loads((folder/'pooling.json').read_text());membership=defaultdict(list)
  for row in pool['members']:scene,key=row['id'].split('|',1);membership[key].append((scene,row))
  for key,members in membership.items():
   assert len(members)==9 and{scene for scene,_ in members}==set(s.b.SCENARIOS)
   base=json.loads((folder/'results/S_ALL'/(key+'_result.json')).read_text());ref=np.load(folder/'results/S_ALL'/(key+'_equity.npz'))['marks'];start=s.z.h.us(base['window'][0])//1000000;cut=(cutsec-start)//60
   legacy=folder==O/'funded/runs/2025/ETH/funded'and key.endswith('F_THROUGH')
   for scene,row in members:
    p=folder/'results'/scene/(key+'_result.json');q=json.loads(p.read_text());marks=np.load(p.with_name(key+'_equity.npz'))['marks']
    assert hashlib.sha256(marks[:cut].tobytes()).hexdigest()==row['own_prefix_SHA256']
    dd=lambda a:float(np.max(1-np.r_[500.,a]/np.maximum.accumulate(np.r_[500.,a]))*100)
    idx=np.flatnonzero(marks!=ref);delta=marks-ref
    checks.append(dict(root=str(folder.relative_to(O)),key=key,scenario=scene,primary=not legacy,own_prefix_verified=True,full_state_hash_at_merge=row['full_state_SHA256'],pool=row['pool'],ending=q['ending_equity'],DD=dd(marks),changed_minutes=len(idx),max_abs_minute_difference=float(np.max(np.abs(delta))),trades_equal_S_ALL=q['trades']==base['trades'],cash_events_equal_S_ALL=q['cash_events']==base['cash_events'],cash_difference=q['cash']-base['cash']))
    for i in idx:differences.append(dict(root=str(folder.relative_to(O)),key=key,scenario=scene,primary=not legacy,minute_end_us=(start+(int(i)+1)*60)*1000000,equity_S_ALL=float(ref[i]),equity_scenario=float(marks[i]),difference=float(delta[i])))
   series=[x for x in checks if x['root']==str(folder.relative_to(O))and x['key']==key]
   for metric in ['ending','DD']:metrics.append(dict(root=str(folder.relative_to(O)),key=key,primary=not legacy,metric=metric,minimum=min(x[metric]for x in series),maximum=max(x[metric]for x in series),span=max(x[metric]for x in series)-min(x[metric]for x in series)))
 if checks:s.z.csv_dump(O/'scenario_history_checks.csv',checks)
 if metrics:s.z.csv_dump(O/'scenario_own_equity_ranges.csv',metrics)
 if differences:s.z.csv_dump(O/'scenario_minute_equity_differences.csv.gz',differences)
 s.dump(O/'scenario_audit.json',dict(original_raw_SHA256_unchanged=True,parsed_arrays_SHA256_unchanged=True,own_prefix_checks=len(checks),primary_checks=sum(x['primary']for x in checks),minute_difference_rows=len(differences),official_data_repaired=False,all_possible_errors_covered=False,old_strict_failures_unchanged=True));print('SCENARIO_AUDIT',len(checks),len(differences))
if __name__=='__main__':main()
