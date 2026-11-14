"""Explicit independent-book subset migration, same financial code and input path."""
import sys,gzip,pickle,json,hashlib
from pathlib import Path
import shared as s
import replay as old
import sizing_only_replay as new
import cost_engine as E
np=s.np

def migrate(period):
 src=s.OUT/'runs'/period/'ETH/experiment/whole/checkpoint.pkl.gz'
 dst=s.OUT/'sizing_only/runs'/period/'ETH/experiment/whole/checkpoint.pkl.gz'
 if dst.exists()or not src.exists():return
 assert period!='2025','Only single-whole-segment migration is eligible'
 for n,sha in json.loads((s.OUT/'frozen_code.json').read_text()).items():assert hashlib.file_digest((s.OUT/n).open('rb'),'sha256').hexdigest()==sha
 info=s.z.prepare(period,'ETH');btc=s.z.prepare(period,'BTC');native={n:hashlib.file_digest((info['data']/n).open('rb'),'sha256').hexdigest()for n in ['ETH_15m.csv','ETH_1m.npy']}
 oldcfg=old.configurations('ETH','experiment');cfg=new.configurations('ETH','experiment')
 data=lambda configs:s.o.digest(dict(hashes=native,core=info['core'],wide=info['wide'],BTC=btc['core'],configs=configs,period=period,asset='ETH'))
 with gzip.open(src,'rb')as f:q=pickle.load(f)
 assert q['fp']==s.fp()and q['datafp']==data(oldcfg)and q['start']==info['start']and q['end']==info['end']
 assert q['keys']==[c['key']for c in oldcfg]and q['start']<=q['next']<=q['end']and(q['next']-q['start'])%60==0
 keys=[c['key']for c in cfg];checks=[]
 for c in cfg:
  key=c['key'];x=q['books'][key];assert x.asset=='ETH'and x.leg is None and x.fee==c['fee']and x.slippage==c['slip']and x.fill_mode=='F_TOUCH'and x.priority
  assert x.extra_ratio==s.GROUPS[c['group']][1]and x.core==info['core']and x.funding_total==0 and not x.funding_events
  assert len(q['marks'][key])==(q['next']-q['start'])//60;E.cash_check(x)
  checks.append(dict(key=key,full_original_book_SHA256=s.o.digest(s.o.full_state(x)),equity_prefix_SHA256=hashlib.sha256(q['marks'][key].tobytes()).hexdigest(),cash=x.cash))
 saved=dict(q,fp=new.sizing_fp(),datafp=data(cfg),keys=keys,books={k:q['books'][k]for k in keys},marks={k:q['marks'][k]for k in keys})
 dst.parent.mkdir(parents=True,exist_ok=True)
 with gzip.open(dst.with_suffix('.tmp'),'wb',compresslevel=1)as f:pickle.dump(saved,f,protocol=5)
 dst.with_suffix('.tmp').replace(dst)
 s.dump(s.OUT/f'sizing_subset_compatibility_{period}.json',dict(source_checkpoint=str(src),source_checkpoint_SHA256=hashlib.file_digest(src.open('rb'),'sha256').hexdigest(),source_runtime_fingerprint=s.fp(),destination_runtime_fingerprint=new.sizing_fp(),source_data_fingerprint=q['datafp'],new_data_fingerprint=data(cfg),next_time=s.r.local_s(q['next']),checks=checks,financial_code_identical=True,only_scheduling_subset_and_output_path_changed=True,other_accounts_never_shared_cash=True,history_preserved=True,not_a_fingerprint_bypass=True))
 print('COMPATIBLE_SUBSET',period,s.r.local_s(q['next']),keys)
if __name__=='__main__':migrate(sys.argv[1])
