"""Audited state migration, exact old fingerprints first, no forced compatibility."""
from pathlib import Path
import os,json,gzip,pickle,hashlib,shutil,numpy as np
HERE=Path(__file__).resolve().parent

def old_root():
 p=os.environ.get('BTC_REVISION_PREVIOUS')
 return Path(p)if p else None

def old_fingerprint(c):
 root=old_root();assert root and root.is_dir(),'Original MA result directory missing'
 att=json.loads((HERE/'source_attestation.json').read_text());base=c.revision_parent_fingerprint()
 assert base==att['parent_suite_fingerprint'],'MA financial/signals fingerprint changed; refuse migration'
 for name,h in att['files'].items():assert c.digest(c.HERE/name)==h
 return base

def check_sources(c,asset,sources):
 assert sources,'No consumed data provenance; migration refused'
 revision=json.loads((c.OUT/'data_revision.json').read_text());pins=revision['pins'][asset]
 for day,meta in sources.items():
  assert meta.get('asset')==asset and meta.get('date')==day and(meta.get('raw_IDs_strictly_increasing')is True or(asset=='ETH'and day=='2025-08-29')),('Unverified parsed source',asset,day)
  assert meta.get('official_checksum_match')is True,('Source was not official-checksum verified',asset,day)
  if day in pins:assert meta['sha256']==pins[day]['sha256'],('Consumed data changed; cannot migrate',asset,day)
 return {d:m['sha256']for d,m in sources.items()}

def migrate_checkpoint(c,folder,ctx,maps,used_freeze,keys,cache):
 if(folder/'whole/checkpoint.pkl.gz').exists():return False
 root=old_root()
 if not root:return False
 source=root/'tasks'/ctx['period']/ctx['asset']/('-'.join(keys));cp=source/'whole/checkpoint.pkl.gz'
 if not cp.exists():return False
 oldfp=old_fingerprint(c);source_cp_sha=c.digest(cp)
 with gzip.open(cp,'rb')as f:q=pickle.load(f)
 expected=c.s.o.digest(dict(code=oldfp,inputs=ctx['migration_inputs'],maps=maps,config=ctx['migration_config'],freeze=used_freeze,start=ctx['start'],end=ctx['end']))
 assert(q['fp'],q['datafp'],q['start'],q['end'],q['keys'])==(oldfp,expected,ctx['start'],ctx['end'],keys),'Old checkpoint fingerprint/config/data mismatch; not migrated'
 assert ctx['start']<=q['next']<=ctx['end']
 sources=json.loads((source/'raw_sources.json').read_text());proof=check_sources(c,ctx['asset'],sources)
 assert c.digest(cp)==source_cp_sha,'Previous checkpoint changed during audit; stop original task first'
 for key,book in q['books'].items():
  c.v.E.cash_check(book)
  assert len(q['marks'][key])==(q['next']-ctx['start'])//60,'Historical equity length mismatch'
 state=pickle.dumps((q['books'],q['marks'],q['next']),protocol=5)
 q['fp']=c.fingerprint();q['datafp']=ctx['fingerprint']
 dest=folder/'whole/checkpoint.pkl.gz';dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_suffix('.migrating')
 with gzip.open(tmp,'wb',compresslevel=1)as f:pickle.dump(q,f,protocol=5)
 with gzip.open(tmp,'rb')as f:test=pickle.load(f)
 assert np.all([np.array_equal(test['marks'][k],q['marks'][k])for k in keys])and test['next']==q['next']
 assert pickle.dumps((test['books'],test['marks'],test['next']),protocol=5)==state,'Financial state changed during migration'
 tmp.replace(dest)
 cache.sources=sources;c.dump(folder/'raw_sources.json',sources)
 c.dump(folder/'whole/progress.json',dict(next_time=c.s.r.local_s(q['next']),migration=True,cash={k:b.cash for k,b in q['books'].items()}))
 c.dump(folder/'migration_receipt.json',dict(old_checkpoint_sha256=source_cp_sha,old_fingerprint=oldfp,new_fingerprint=q['fp'],old_datafp=expected,new_datafp=q['datafp'],next=q['next'],consumed_data=proof,financial_state_and_equity_preserved=True,old_files_modified=False))
 c.backup(folder);print('AUDITED_RESUME',ctx['asset'],'-'.join(keys),c.s.r.local_s(q['next']),flush=True)
 return True

def reuse_completed(c):
 root=old_root()
 if not root:return
 oldfp=old_fingerprint(c)
 for status in (root/'runs').glob('*/*/*/status.json'):
  key,year,asset=status.parent.relative_to(root/'runs').parts;src=status.parent;st=json.loads(status.read_text())
  if not st.get('complete'):continue
  assert st['fingerprint']==oldfp and c.digest(src/'result.json')==st['result_SHA256']and c.digest(src/'equity.npz')==st['equity_SHA256']
  q=json.loads((src/'result.json').read_text());assert q.get('V2')is False and q.get('baseline')=='MA_DIRECTION_REFERENCE'and q['retest_fingerprint']==oldfp
  if year=='2026':assert q['retest_end']==c.END2026
  matches=list((root/'tasks'/year/asset).glob('*/raw_sources.json'));matches=[p for p in matches if key in p.parent.name.split('-')]
  assert len(matches)==1,('Ambiguous completed provenance',key,asset)
  try:proof=check_sources(c,asset,json.loads(matches[0].read_text()))
  except AssertionError as error:print('CANNOT_REUSE_COMPLETED',key,asset,str(error),flush=True);continue
  dest=c.OUT/'imported'/key/year/asset;dest.mkdir(parents=True,exist_ok=True)
  for p in src.iterdir():
   if p.is_file()and p.suffix in ['.json','.npz']:shutil.copy2(p,dest/p.name)
  c.dump(dest/'reuse_receipt.json',dict(old_runtime_fingerprint=oldfp,consumed_data=proof,old_result_sha256=st['result_SHA256'],financial_ledger_unmodified=True))
  print('REUSE_VERIFIED_COMPLETED',key,asset,flush=True)
