"""Isolate one independent fee book; reuse only the identical frozen-code checkpoint."""
import argparse,hashlib,json,traceback,gzip,pickle,shutil
from pathlib import Path
import strategy as z
import priority_engine
OUT=z.OUT
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('group',choices=list('DGHI'));parser.add_argument('cost',choices=list(z.COSTS));args=parser.parse_args()
 w=z.module('priority_cost_isolated_worker',OUT/'worker.py');original_fp=w.fingerprint();rate=z.COSTS[args.cost];z.COSTS={args.cost:rate};w.OUT=OUT/'cost_isolation'/args.cost
 # No financial source changes: select one independent account and its complete
 # prefix from the same worker fingerprint, never an old version's checkpoint.
 w.fingerprint=lambda:original_fp
 source=OUT/'runs/2025/ETH'/args.group/'checkpoint.pkl.gz';folder=w.OUT/'runs/2025/ETH'/args.group;folder.mkdir(parents=True,exist_ok=True);target=folder/'checkpoint.pkl.gz'
 if not target.exists()and source.exists():
  with gzip.open(source,'rb')as f:saved=pickle.load(f)
  key=args.cost+'_'+args.group
  assert saved['code_fingerprint']==original_fp and saved['groups']==[args.group]
  assert key in saved['books']and saved['books'][key].fee==rate
  assert saved['books'][key].leg is None
  subset=dict(saved,books={key:saved['books'][key]},marks={key:saved['marks'][key]})
  with gzip.open(target,'wb',compresslevel=1)as f:pickle.dump(subset,f,protocol=5)
  z.dump(folder/'checkpoint_subset_manifest.json',dict(source=str(source),source_SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),financial_code_fingerprint=original_fp,selected_key=key,selected_fee=rate,next_time=saved['next_time'],groups=saved['groups'],other_accounts_removed_only=True,independence='per-book cash/order/position/V2 state; runtime FEE reset before each step; immutable precomputed signals; raw cache supplies prices only',not_old_version_checkpoint=True))
  for n in('raw_sources.json','candle_tick_disagreements.json'):
   if(source.parent/n).exists():shutil.copyfile(source.parent/n,folder/n)
 try:w.run('2025','ETH',[args.group])
 except Exception as error:
  z.dump(folder/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),financial_code_fingerprint=original_fp,isolated_cost=args.cost,same_fingerprint_checkpoint_only=True));raise
