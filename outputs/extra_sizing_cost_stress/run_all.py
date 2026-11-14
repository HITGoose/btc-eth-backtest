"""Current-cloud full replay/recovery entry; requires original validated input caches."""
from pathlib import Path
import subprocess,sys,json
O=Path(__file__).resolve().parent
assert sys.version_info[:2]==(3,12),'Use locked Python3.12 environment'
def run(script):
 with (O/(script+'.entry.log')).open('a')as f:subprocess.run([sys.executable,'-u',str(O/script)],stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
 for script in ['validate_cache.py','run_parent_tests.py','tests.py','anomaly_validation/tests.py','funding_fetch.py','funding_tests.py','subset_tests.py','through_tests.py']:run(script)
 active=[]
 for script in ['supervisor.py','funded_supervisor.py','through_supervisor.py']:
  f=(O/(script+'.entry.log')).open('a');active.append((subprocess.Popen([sys.executable,'-u',str(O/script)],stdout=f,stderr=subprocess.STDOUT),f))
 for p,f in active:p.wait();f.close()
 for script in ['report.py','audit_finances.py','fill_sensitivity.py','funding_blockers.py','scenario_audit.py','cost_decomposition.py','raw_source_consistency.py','conclude.py','coverage_audit.py','package.py']:
  if(O/script).exists():run(script)
if __name__=='__main__':main()
