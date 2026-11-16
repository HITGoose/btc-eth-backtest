"""Tiny in-memory official-endpoint fixture, not a claim to repair remote Colab."""
from pathlib import Path
import tempfile,io,zipfile,hashlib,json
import cache_doctor as d
b=io.BytesIO()
with zipfile.ZipFile(b,'w')as z:z.writestr('fixture.csv','id,price\n1,100\n')
payload=b.getvalue();expected=hashlib.sha256(payload).hexdigest()
class Response(io.BytesIO):
 def __init__(self,payload):super().__init__(payload);self.headers={'Content-Length':str(len(payload))}
def opened(request,**kw):
 url=getattr(request,'full_url',request)
 return Response((expected+' fixture.zip\n').encode()if url.endswith('.CHECKSUM')else payload)
original=d.urlopen;d.urlopen=opened
try:
 with tempfile.TemporaryDirectory()as tmp:
  p=Path(tmp)/'fixture.zip';p.write_bytes(b'broken-cache')
  r=d.recover('https://fixture.invalid/fixture.zip',p,expected);assert d.sha(p)==expected and Path(r['preserved_original']).read_bytes()==b'broken-cache';assert r['status']=='LOCAL_CACHE_REPLACED_WITH_VERIFIED_OFFICIAL_BYTES'
  r2=d.recover('https://fixture.invalid/fixture.zip',p,expected);assert r2['status']=='VALID_UNCHANGED'
  try:d.recover('https://fixture.invalid/fixture.zip',p,'0'*64);raise AssertionError('pin should reject')
  except RuntimeError as e:assert 'UNVERIFIED_OFFICIAL_CHANGED' in str(e)
  assert d.sha(p)==expected
  snapshot=Path(tmp)/'BTCUSDT-trades-2026-10-29.zip';snapshot.write_bytes(payload)
  saved=d.FROZEN_SNAPSHOTS[snapshot.name];d.FROZEN_SNAPSHOTS[snapshot.name]=expected
  def revised(request,**kw):
   url=getattr(request,'full_url',request);return Response(('1'*64+' revised.zip\n').encode()if url.endswith('.CHECKSUM')else payload)
  d.urlopen=revised
  result=d.recover('https://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/'+snapshot.name,snapshot,expected);assert result['status']=='VALID_PINNED_HISTORICAL_SNAPSHOT'and d.sha(snapshot)==expected
  from types import SimpleNamespace as NS
  root=Path(tmp)/'repository';record=root/'outputs/baseline_registry/runs/2026/BTC/raw_sources.json';record.parent.mkdir(parents=True);record.write_text(json.dumps({'2026-10-29':{'sha256':expected,'official_checksum_match':True}}))
  cache=Path(tmp)/'market';central=cache/'archives/daily/trades/BTCUSDT'/snapshot.name;central.parent.mkdir(parents=True);central.write_bytes(payload)
  def rejected(url,path):raise RuntimeError('Official checksum mismatch: fixture')
  driver=NS(acquire_original_colab=rejected)
  driver.acquire=lambda url,path:driver.acquire_original_colab(url,path)
  D=NS(ROOT=root,DATA=cache,v=NS(s=NS(b=NS(d=driver))))
  d.install_safe_acquire(D);meta=driver.acquire('https://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/'+snapshot.name,central);assert meta['pinned_snapshot_match']and not meta['official_checksum_match']and meta['sha256']==expected
  d.FROZEN_SNAPSHOTS[snapshot.name]=saved
 print('ZIP preservation, checksum/CRC recovery, unchanged cache and baseline-pin rejection PASS')
finally:d.urlopen=original
