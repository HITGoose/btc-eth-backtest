import numpy as np,json
from pathlib import Path
import features
r=np.zeros((4000,6));r[:,4]=100;r[:,2]=102;r[:,3]=98
tr,atr=features.atr96(r);assert np.isnan(atr[:95]).all()and atr[95]==4
r[96,2]=106;tr,atr=features.atr96(r);assert atr[96]==(95*4+8)/96
z=features.compute(r);assert np.isnan(z['v_ref'][2974])and np.isfinite(z['v_ref'][2975])
assert abs(z['v_ref'][3100]-np.median(z['v'][220:3100]))<1e-12
b=r.copy();b[3200:,2]=150;b[3200:,4]=125;zz=features.compute(b)
for k in ['ATR','v','v_ref','m']:assert np.allclose(z[k][:3200],zz[k][:3200],equal_nan=True)
assert(z['L']>=1.5).all()and(z['L']<=3).all()and(z['L'][:2975]==3).all()
# Alter CURRENT close/range: previous-only reference is unchanged.
b=r.copy();b[3100,2]=500;zz=features.compute(b);assert zz['v_ref'][3100]==z['v_ref'][3100]and zz['L'][3100]==1.5
Path(__file__).with_name('feature_checks.json').write_text(json.dumps(dict(ATR_seed_and_recursion=True,previous_2880_only=True,future_data_invariant=True,clip_and_fallback=True),indent=2))
print('FEATURE_CHECKS_PASSED')
