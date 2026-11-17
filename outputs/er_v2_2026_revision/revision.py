"""Frozen complete tail data manifest; original financial engine remains unchanged."""
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent
OLD={'BTC':'a634b1cc9e3858d732688afc6c8f5d51277a683a27254fc54f4ff70e29bc9d69','ETH':'a1380a5185eb2eff57a1975c5d004f92a77652d7f66799dece6103d08e20b1e8'}
def read(out):return json.loads((out/'data_revision.json').read_text())
def install(c):
 original=c.fingerprint;c.revision_parent_fingerprint=original
 def fingerprint():
  return hashlib.sha256(original().encode()+(c.OUT/'data_revision.json').read_bytes()+b''.join(p.read_bytes()for p in sorted(HERE.glob('*.py')))+(HERE/'official_preflight.json').read_bytes()+(HERE/'previous/source_attestation.json').read_bytes()).hexdigest()
 c.fingerprint=fingerprint

def apply(c,year,asset,sources):
 assert year==2026,'Recovery only allows 2026'
 q=read(c.OUT);assert q['mode']=='AUDITED_TAIL_REVISION_WITH_COMPATIBLE_STATE_MIGRATION'
 result=dict(sources)
 for day,entry in q['pins'][asset].items():result[day]=dict(result.get(day,{}),sha256=entry['sha256'])
 return result
