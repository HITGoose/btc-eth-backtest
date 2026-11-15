"""New observer start only; copy fixed strategy/costs, never replace existing freezes."""
from pathlib import Path
import json,hashlib,time,os,datetime
import online as n
O=n.O

def main():
 template=O/'FREEZE_WS_V3.json';q=json.loads(template.read_text())
 for file,sha in q['code_SHA256'].items():assert hashlib.sha256((n.R/file).read_bytes()).hexdigest()==sha,'Use exactly the frozen runtime version'
 made=n.nowus();t0=((made//1000000+60)//900+1)*900000
 q.update(run_id='external_same_strategy_'+str(t0),created_us=made,created_UTC=n.utc(made),T0_ms=t0,T0_UTC=n.utc(t0*1000),T0_Beijing=datetime.datetime.fromtimestamp(t0/1000,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),first_signal_close_ms=t0+900000,template_SHA256=hashlib.sha256(template.read_bytes()).hexdigest(),previous_records_not_overwritten=True,new_observation_not_continuation_of_old_gap=True)
 q['checkpoints']=[dict(day=d,UTC=n.utc(t0*1000+d*86400*1000000),purpose='quality sample costs risk; never automatic statistical significance')for d in [30,60,90]]
 folder=O/'freezes';folder.mkdir(exist_ok=True);p=folder/(q['run_id']+'.json');raw=json.dumps(q,ensure_ascii=False,indent=2).encode()
 with p.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 assert n.nowus()<t0*1000;p.chmod(0o444);p.with_suffix('.sha256').write_text(hashlib.sha256(raw).hexdigest());print(str(p));print(q['T0_UTC'],q['T0_Beijing'])
if __name__=='__main__':main()
