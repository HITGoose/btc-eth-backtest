"""Read native arrays only: no account replay or downloads. Targeted index regression."""
from pathlib import Path
from types import SimpleNamespace as NS
import os,json
import variant_engine as v
from data import spec
np=v.np
R=Path(os.environ.get('BTC_EXISTING_DATA_REPO',v.ROOT))
checks=[]
for year in range(2020,2027):
 for asset in ['BTC','ETH']:
  m=spec(year,asset);file=R/m['legacy_data']/f'{asset}_15m.csv'
  leg,*_=v.s.b.p.prepare(asset,file,m['start'],m['end']);f=v.indicators(leg,file)
  assert len(f['close'])==len(leg.width)and f['time_ms'][-1]==m['end']*1000-900000
  i=(m['end']*1000-leg.first)//900000-1;assert f['time_ms'][i]==m['end']*1000-900000
  if year==2021 and asset=='ETH':
   n=5000;prefix=NS(first=leg.first,end=leg.first+n*900000,width=leg.width[:n]);p=v.indicators(prefix,file)
   for key in f:assert np.array_equal(p[key],f[key][:n],equal_nan=True),('future contamination',key)
  checks.append(dict(year=year,asset=asset,full_length=len(f['close']),original_first_ms=leg.first,feature_first_ms=int(f['time_ms'][0]),last_close_ms=int(f['time_ms'][-1])+900000,passed=True))
print(json.dumps(dict(checks=checks,causal_prefix_2021_ETH=True,financial_replays=0),indent=2))
