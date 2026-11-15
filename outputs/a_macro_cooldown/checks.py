from pathlib import Path
import sys,json,datetime,importlib.util
from zoneinfo import ZoneInfo
O=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('macro_cooldown_check_runner',O/'run.py');w=importlib.util.module_from_spec(sp);sys.modules[sp.name]=w;sp.loader.exec_module(w)
e=json.loads((O/'calendar.json').read_text())['events'];out=[]
for z in e:
 t=z['release_ms'];f=[z]
 assert not w.blocked(t-1,'A_MACRO_60',f)and w.blocked(t,'A_MACRO_60',f)and w.blocked(t+3600000,'A_MACRO_60',f)and not w.blocked(t+3600001,'A_MACRO_60',f)
 if z['kind']=='CPI':assert not w.blocked(t,'A_FOMC_60',f)
 else:assert w.blocked(t,'A_FOMC_60',f)
out.append('Inclusive signal-close boundaries, CPI excluded from FOMC-only')
for d,h in [('2020-03-03',15),('2020-03-15',21)]:
 z=next(x for x in e if x['kind']=='FOMC'and x['date']==d);assert datetime.datetime.fromtimestamp(z['release_ms']/1000,datetime.timezone.utc).hour==h
out.append('Emergency decisions use actual15:00UTC and21:00UTC, not14:00ET')
assert w.sig.SETTINGS.squeeze_threshold==.25 and w.sig.POLICY.range_squeeze_pct==.25 and w.sig.POLICY.range_entry_bandwidth_pct==.50 and w.sig.POLICY.trend_level_distance_pct==2.0 and w.sig.POLICY.pause_transition is True
out.append('Original fixed A squeeze .25; macro wrapper calls only A')
for p in(O/'runs').glob('*/*/signals.json'):
 x=json.loads(p.read_text());mm={g:{int(t):v for t,v in z.items()}for g,z in x['accepted'].items()};a=mm['A']
 for g in w.GROUPS:assert mm[g]=={t:v for t,v in a.items()if not w.blocked(t,g,e)}
out.append('Every generated variant signal is an unchanged A signal outside its exact cooldown')
(O/'checks.json').write_text(json.dumps(dict(passed=True,checks=out),indent=2));print('PASS',len(out))
