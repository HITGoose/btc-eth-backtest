from pathlib import Path
import argparse,subprocess,sys,json,datetime
OUT=Path(__file__).resolve().parent
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('group',choices=list('DGHI'));args=parser.parse_args()
 for cost in('ZERO','ASSUMED_005_SIDE'):
  folder=OUT/'cost_isolation'/cost/'runs/2025/ETH'/args.group;folder.mkdir(parents=True,exist_ok=True)
  cmd=[sys.executable,str(OUT/'isolate_cost.py'),args.group,cost]
  with(folder/'run.log').open('w')as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
  (folder/'isolation_attempt.json').write_text(json.dumps(dict(group=args.group,cost=cost,command=cmd,code=r.returncode,completed_attempt=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2));print('COST_ATTEMPT',args.group,cost,r.returncode,flush=True)
