"""Sequential recovery of the same frozen2025 cohorts after observed cgroup OOM."""
from pathlib import Path
import subprocess,sys,json,time
O=Path(__file__).resolve().parent

def main():
 tasks=[('sizing_only_replay.py','experiment','2025_ETH_experiment.log'),('funded_replay.py','funded','funded_2025_ETH.log')];records=[]
 for script,stage,log in tasks:
  with(O/log).open('a')as f:
   f.write('\n# SEQUENTIAL_OOM_RECOVERY '+str(time.time())+'; financial source/config unchanged\n');f.flush();p=subprocess.run([sys.executable,'-u',str(O/script),'2025','ETH',stage],stdout=f,stderr=subprocess.STDOUT)
  records.append(dict(script=script,stage=stage,returncode=p.returncode,command=[sys.executable,str(O/script),'2025','ETH',stage]));(O/'resource_recovery.json').write_text(json.dumps(dict(cgroup_memory_limit_bytes=8589934592,observed_oom_kills=2,original_failed_returncodes=[-9,-9],schedule='sequential, no financial/data/fee/source changes',records=records),indent=2))
  print(json.dumps(records[-1]),flush=True)
  if p.returncode:raise SystemExit(p.returncode)
if __name__=='__main__':main()
