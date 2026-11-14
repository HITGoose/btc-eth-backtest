"""Portable replay validation when Git contains ledger ZIPs but not reference NPY.
Financial execution is the exact frozen worker. Archive data is comparison-only.
"""
from pathlib import Path
import argparse,json,zipfile,traceback,hashlib
import strategy as z
OUT=z.OUT

def expected(period,asset,cost,group,w):
 file,eq=w.prior(period,asset,cost,group)
 if file.exists():return json.loads(file.read_text()),dict(source=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest()),eq.exists()
 archive=z.OLD/'artifacts'/f'period_{period}_ledgers.zip'
 if not archive.exists():return None,None,False
 suffix=f'/runs/{period}/{asset}/{cost}_{group}_result.json'
 with zipfile.ZipFile(archive)as a:
  hits=[n for n in a.namelist()if('/'+n).endswith(suffix)]
  if not hits:return None,None,False
  assert len(hits)==1,hits;data=a.read(hits[0])
 return json.loads(data),dict(archive=str(archive),member=hits[0],json_sha256=hashlib.sha256(data).hexdigest()),False

def compare_subset(actual,old):
 if isinstance(old,dict):
  for key,value in old.items():assert key in actual;compare_subset(actual[key],value)
 elif isinstance(old,list):
  assert len(actual)==len(old)
  for a,b in zip(actual,old):compare_subset(a,b)
 else:assert actual==old,(actual,old)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('period');parser.add_argument('asset',choices=['BTC','ETH']);parser.add_argument('--groups',default='BDGHI');args=parser.parse_args()
 groups=['B']if args.asset=='BTC'else list(args.groups);folder=OUT/'runs'/args.period/args.asset/''.join(groups);folder.mkdir(parents=True,exist_ok=True)
 w=z.module('priority_portable_frozen_worker',OUT/'worker.py');orig=w.prior;refs={}
 for cost in z.COSTS:
  for group in groups:
   if group not in('B','D'):continue
   refs[cost,group]=expected(args.period,args.asset,cost,group,w)
 def reference(period,asset,cost,group):
  file,eq=orig(period,asset,cost,group)
  if file.exists()and not eq.exists():return OUT/'NO_PUBLISHED_MINUTE_REFERENCE'/file.name,eq
  return file,eq
 w.prior=reference
 try:
  w.run(args.period,args.asset,groups);receipts=[]
  for(cost,group),(old,source,has_minute_ref)in refs.items():
   if old is None:
    if args.period=='2025'and group=='D':continue
    raise RuntimeError(f'Missing locked B/D comparison ledger: {args.period} {args.asset} {cost} {group}')
   actual=json.loads((folder/f'{cost}_{group}_result.json').read_text())
   assert abs(actual['ending_equity']-old['ending_equity'])<1e-7
   compare_subset(actual['trades'],old['trades']);compare_subset(actual['state_at_end'],old['state_at_end'])
   assert abs(actual['cash']-old['cash'])<1e-7
   receipts.append(dict(key=cost+'_'+group,closed_trades_exact=True,end_state_subset_exact=True,ending_equity_and_cash_exact=True,source=source,minute_path='EXACT_REFERENCE_CHECKED_BY_FROZEN_WORKER'if has_minute_ref else'REFERENCE_NPY_NOT_PUBLISHED_JSON_TRADES_AND_TERMINAL_EQUITY_CHECKED'))
  z.dump(folder/'portable_regression.json',dict(passed=True,financial_fingerprint=w.fingerprint(),checks=receipts,archive_used_as_prices=False))
 except Exception as error:
  z.dump(folder/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),code_fingerprint=w.fingerprint()));raise
