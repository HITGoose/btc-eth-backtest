"""Synthetic source-handling test only, never historical validation."""
from pathlib import Path
from types import SimpleNamespace
import json,tempfile
import numpy as np
from restore_gaps import restore
with tempfile.TemporaryDirectory() as temp:
 out=Path(temp);(out/'1970').mkdir()
 raw=np.array([[1,100,1,100000],[2,101,1,200000],[3,999,1,600000],[4,999,1,800000]],float)
 def acquire(url,path):path.touch();return {'synthetic':True}
 def dump(path,value):path.write_text(json.dumps(value))
 d=SimpleNamespace(BASE='SYNTHETIC',acquire=acquire,read_zip=lambda path,cols:raw.copy(),dump=dump)
 r=SimpleNamespace(local_s=lambda t:str(t))
 rows=np.array([[240,101,101,101,101,0],[360,101,101,101,101,0]],float)
 result=restore(rows,np.array([240,300,360]),60,'BTC',1970,out,d,r)
 assert result[1].tolist()==[300,101,101,101,101,0], 'Must not use future price999'
 raw[2,0]=4
 try:restore(rows,np.array([240,300,360]),60,'BTC',1970,out,d,r);raise AssertionError('Missing trade IDs must fail')
 except RuntimeError as e:assert 'contiguous' in str(e)
Path(__file__).with_name('gap_restore_test.json').write_text(json.dumps(dict(passed=True,historical_validation=False,tests=['empty interval uses previous observed close, not future price','non-contiguous trade IDs abort reconstruction']),indent=2))
print('PASS missing-bar no-lookahead and incomplete-ID tests')
