"""Reuse only unchanged BTC controls, never ETH or a new order's price path."""
from pathlib import Path
import hashlib,json,shutil
import strategy as z
w=z.module('priority_btc_reuse_worker',z.OUT/'worker.py')
if __name__=='__main__':
 for period in['2020','2021','2022','2023','2026','NOV']:
  info=z.prepare(period,'BTC');old=z.OLD/'runs'/period/'BTC';target=z.OUT/'runs'/period/'BTC'/'B';target.mkdir(parents=True,exist_ok=True)
  oldmaps=json.loads((old/'signals.json').read_text());assert info['core']=={int(k):v for k,v in oldmaps['0.25'].items()};assert info['core']==info['wide']
  expected=json.loads((old/'input_provenance.json').read_text())['derived_file_hashes']
  for name in['BTC_15m.csv','BTC_1m.npy']:
   file=info['data']/name;assert hashlib.sha256(file.read_bytes()).hexdigest()==expected[str(file)]
  assert json.loads((old/'status.json').read_text())['completed']
  copied=[]
  for cost in z.COSTS:
   for suffix in['_result.json','_equity.npy']:
    source=old/(cost+'_B'+suffix);dest=target/source.name
    if not dest.exists():dest.hardlink_to(source)
    copied.append(dict(source=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
  for name in['config.json','raw_sources.json','input_provenance.json','candle_tick_disagreements.json']:
   if(old/name).exists():shutil.copyfile(old/name,target/name)
  z.dump(target/'signals.json',dict(core=info['core'],wide=info['wide'],BTC=info['core'],accepted={'B':info['core']}))
  z.dump(target/'reuse_manifest.json',dict(unchanged_BTC_control_only=True,new_ETH_orders_never_use_saved_trade_paths=True,native_caches_SHA256_match=True,complete_signals_exact=True,files=copied,source_commit=z.BASE_COMMIT,note='Fresh 2024/25 BTC and ETH B/D reruns establish shared engine regression; remaining BTC independent control has no rule or account change'))
  z.dump(target/'status.json',dict(completed=True,code_fingerprint=w.fingerprint(),groups=['B'],keys=[x+'_B'for x in z.COSTS],reused_unchanged_verified_BTC_control=True,not_a_fresh_replay=True))
  print('REUSED_UNCHANGED_BTC',period,flush=True)
