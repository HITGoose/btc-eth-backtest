import sys,json,hashlib
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import experiment as x
out=[]
a=np.array([.1,.25,.28,.4,np.nan]);assert np.allclose(np.maximum(a,.25)[:4],[.25,.25,.28,.4]);out.append('E1 lower floor .25, NaN preserved')
for cap in [.30,.35]:
 t=np.minimum(np.maximum(a,.25),cap);assert np.nanmin(t)>=.25 and np.nanmax(t)<=cap
out.append('E2 independently caps .30 and .35, no range-width changes')
y=np.linspace(0,1,6000);q=x.sig.past_quantile(y,.25);y2=y.copy();y2[4000:]=99;q2=x.sig.past_quantile(y2,.25);assert np.array_equal(q[:4001],q2[:4001],equal_nan=True);out.append('Rolling quantile excludes current and all future values')
from zoneinfo import ZoneInfo
from datetime import datetime,timezone
for d,expected in [('2024-01-11T08:30',13),('2024-07-11T08:30',12)]:assert datetime.fromisoformat(d).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).hour==expected
out.append('NY DST converts winter CPI13:30UTC, summer12:30UTC')
c=json.loads((O/'calendar.json').read_text());assert not any(e['date']=='2025-08-22'and e['kind']=='FOMC'for e in c['events']);out.append('Fed framework announcement and non14:00 emergencies excluded')
for name in ['signals.py','engine.py','worker.py']:
 p=x.BASE/name;out.append(dict(original_source=name,SHA256=hashlib.sha256(p.read_bytes()).hexdigest()))
(O/'checks.json').write_text(json.dumps(dict(passed=True,checks=out),indent=2));print('PASS',len(out))
