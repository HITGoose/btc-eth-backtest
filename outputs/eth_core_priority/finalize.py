"""Run after supervisor; explicit complete attempts, then independent reporting."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,json
OUT=Path(__file__).resolve().parent
if __name__=='__main__':
 state=json.loads((OUT/'supervisor_status.json').read_text());assert state['completed'],'Wait for main supervisor to finish'
 tasks=[]
 for item in state['failures']:
  if item['period']=='2025'and item['asset']=='ETH':
   for g in item['groups']:
    completed=OUT/'runs'/item['period']/item['asset']/g/'status.json'
    if completed.exists()and json.loads(completed.read_text()).get('completed'):continue
    for cost in('ZERO','ASSUMED_005_SIDE'):tasks.append((g,cost))
 def job(item):
  g,cost=item;folder=OUT/'cost_isolation'/cost/'runs/2025/ETH'/g;folder.mkdir(parents=True,exist_ok=True)
  if(folder/'isolation_attempt.json').exists()and(folder/'failure.json').exists():
   attempt=json.loads((folder/'isolation_attempt.json').read_text());failure=json.loads((folder/'failure.json').read_text())
   if attempt.get('completed_attempt')and'Duplicate or unordered raw trade IDs'in failure.get('error',''):return dict(group=g,cost=cost,code=attempt['code'],reused_current_task_completed_strict_failure=True)
  with(folder/'run.log').open('w')as log:r=subprocess.run([sys.executable,str(OUT/'isolate_cost.py'),g,cost],stdout=log,stderr=subprocess.STDOUT)
  return dict(group=g,cost=cost,code=r.returncode)
 with ThreadPoolExecutor(max_workers=3)as pool:results=list(pool.map(job,tasks))
 (OUT/'cost_isolation_status.json').write_text(json.dumps(results,indent=2))
 for script in('export_incomplete.py','collect.py','extra_analysis.py','shadows.py','audit.py'):
  with(OUT/(script.replace('.py','')+'_final.log')).open('w')as log:proc=subprocess.run([sys.executable,str(OUT/script)],stdout=log,stderr=subprocess.STDOUT)
  if proc.returncode:raise SystemExit('Failed '+script+'; inspect its log, do not publish fake complete result')
