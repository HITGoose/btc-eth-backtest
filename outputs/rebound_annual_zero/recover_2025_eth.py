"""Logging-only ScenarioCache metadata delegate; resume exact financial checkpoint."""
from pathlib import Path
import sys,json,hashlib,gzip,pickle,inspect,datetime,traceback
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import worker as w
s=w.s;cls=s.a.ScenarioCache;before=hashlib.sha256(inspect.getsource(cls.load).encode()).hexdigest();fp=w.fp();folder=O/'runs/2025/ETH';cp=folder/'whole/checkpoint.pkl.gz'
with gzip.open(cp,'rb')as f:old=pickle.load(f)
assert old['fp']==fp,'Never ignore a financial fingerprint mismatch'
assert old['keys']==['CONTROL','REBOUND']
cls.sources=property(lambda self:self.strict.sources)
assert hashlib.sha256(inspect.getsource(cls.load).encode()).hexdigest()==before
s.dump(folder/'logging_adapter_recovery.json',dict(time_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),original_checkpoint_SHA256=hashlib.sha256(cp.read_bytes()).hexdigest(),original_financial_fingerprint=old['fp'],current_financial_fingerprint=fp,financial_fingerprint_exact=True,ScenarioCache_load_source_SHA256=before,change='readonly sources property delegates to strict cache for progress logging only',funding=0,fee=0,scenario='S_ALL',resume_time_Beijing=s.r.local_s(old['next']),no_nine_scenario_matrix=True,recovery_code_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
try:
 w.run('2025','ETH')
 import validate_baselines as v
 assert v.validate('2025','ETH')
 s.dump(O/'2025_ETH_recovery_status.json',dict(completed=True,baseline_verified=True,status='COMPLETED_WITH_DATA_ANOMALY'))
except Exception as e:s.dump(O/'2025_ETH_recovery_failure.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
