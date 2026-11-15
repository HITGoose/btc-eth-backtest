from pathlib import Path
import importlib.util,sys,json,csv,hashlib
O=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('exit_sizing_checks_runner',O/'runner.py');w=importlib.util.module_from_spec(sp);sys.modules[sp.name]=w;sp.loader.exec_module(w);m=w.sig.r.model;out=[]
assert m.LADDER_CAP==5
for gain,base,uncap,trail in [(2,1,1,1),(6,5,5,5),(7,5,6,5),(8,5,7,7),(20,5,19,19)]:
 assert [m.ladder_rung(gain,p)for p in ['fixed','uncapped','trail_from_8pct']]==[base,uncap,trail]
out.append('Existing exit policies: cap5, uncapped, release cap at favorable8%, no invented cap8')
assert w.sig.SETTINGS.squeeze_threshold==.25 and w.sig.POLICY.range_squeeze_pct==.25 and w.sig.POLICY.range_entry_bandwidth_pct==.5 and w.sig.POLICY.pause_transition
out.append('Original fixed squeeze/current-width/transition unchanged')
n=0
for folder in(O/'runs').glob('*/*'):
 if not(folder/'signals.json').exists():continue
 q=json.loads((folder/'signals.json').read_text());core={int(t):v for t,v in q['A'].items()};period=folder.parent.name;asset=folder.name;old=json.loads((w.P/'runs'/period/asset/'signals.json').read_text())['accepted']['A'];assert core=={int(t):v for t,v in old.items()}
 for row in csv.DictReader((folder/'regime_weights.csv').open(encoding='utf-8-sig')):
  assert int(row['last_closed_hour_ms'])<=int(row['signal_close_ms']);er=float(row['slow_ER']);side=int(row['side']);d=1 if er>=.10 else-1 if er<=-.10 else 0;assert float(row['weight'])==(1.3 if d==side else .7)
 for path in folder.glob('*_result.json'):
  x=json.loads(path.read_text());assert x['configuration']['exit_policy']==w.GROUPS[x['configuration']['group']]
  for t in x['trades']:assert core[t['signal_close_ms']]==(1 if t['side']=='LONG'else-1)
  for a in x['sizing_audit']:
   if a['accepted']:
    assert a['actual_notional']<=a['target_notional']+1e-6
    if x['configuration']['group']=='A_REGIME_SIZE':assert a['requested_weight']in [.7,1.3]
  n+=1
out.append('All available complete signals identical to fixed A; weights only past closed120h information')
out.append('Accepted notional rounds down; regime weights do not remove or add indicator signals')
(O/'checks.json').write_text(json.dumps(dict(passed=True,account_results_checked=n,checks=out),indent=2));print('PASS',len(out),'checks',n,'available results')
