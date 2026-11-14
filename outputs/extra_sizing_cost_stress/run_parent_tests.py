from pathlib import Path
import subprocess,sys,json
OUT=Path(__file__).resolve().parent
if __name__=='__main__':
 results=[]
 for name in ['validation32/tests.py','tests.py','analysis_tests.py','shadow_tests.py','boundary_tests.py','checkpoint_tests.py']:
  folder=OUT/'parent_validation';log=folder/(name.replace('/','_')+'.log')
  with log.open('w')as f:r=subprocess.run([sys.executable,str(folder/name)],stdout=f,stderr=subprocess.STDOUT)
  results.append(dict(script=name,code=r.returncode,log=str(log.relative_to(OUT))));print('PARENT_TEST',name,r.returncode,flush=True)
  if r.returncode:break
 (OUT/'parent_tests.json').write_text(json.dumps(dict(passed=all(x['code']==0 for x in results)and len(results)==6,checks=107,results=results),indent=2))
 if not all(x['code']==0 for x in results):raise SystemExit(1)
