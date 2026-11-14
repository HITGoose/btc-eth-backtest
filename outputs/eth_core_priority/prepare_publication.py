from pathlib import Path
import json,hashlib,base64
ROOT=Path('/workspace/btc-eth-backtest');OUT=ROOT/'outputs/eth_core_priority'
if __name__=='__main__':
 files=[ROOT/'ETH_CORE_PRIORITY_EXPERIMENT.md']
 ignored={'publication_manifest.json','github_receipt.json','analysis_smoke_2024_result.json','report_smoke_2024.md','publication_prepare.log'}
 for p in OUT.iterdir():
  if p.is_file()and p.name not in ignored and p.suffix in('.py','.md','.csv','.json','.log','.gz'):files.append(p)
 for scope in['validation32','data_evidence','download_recovery']:
  folder=OUT/scope
  if folder.exists():files.extend(p for p in folder.rglob('*')if p.is_file()and p.suffix in('.py','.json','.log'))
 # Keep runtime checkpoints/status and price inputs out of loose Git paths.
 # Complete ledgers/provenance are supplied in reviewed per-period ZIPs.
 files.extend((OUT/'artifacts').glob('*.zip'))
 files=sorted(set(files));manifest=[]
 for p in files:
  data=p.read_bytes();manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()))
 (OUT/'publication_manifest.json').write_text(json.dumps(dict(base_commit='01937b2d4a1306ab211a9c1853bda285258c2853',financial_code_commit='2292b8a2cfc7d802c639014cba1b8ae7d1ef917c',full_history_complete=False,files=manifest),indent=2)+'\n')
 files.append(OUT/'publication_manifest.json');inline=[];blobs=[];temp=Path('/tmp/priority_publication');temp.mkdir(exist_ok=True)
 for p in files:
  raw=p.read_bytes();path=str(p.relative_to(ROOT))
  if len(raw)<45000 and p.suffix not in('.zip','.gz'):
   inline.append(dict(path=path,mode='100644',type='blob',content=raw.decode('utf-8')))
  else:
   sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();encoded=base64.b64encode(raw).decode();file=temp/(sha+'.b64');file.write_text(encoded)
   blobs.append(dict(path=path,git_sha=sha,bytes=len(raw),base64_path=str(file),base64_length=len(encoded)))
 (temp/'inline.json').write_text(json.dumps(inline,ensure_ascii=True));(temp/'blobs.json').write_text(json.dumps(blobs));print(json.dumps(dict(files=len(files),inline=len(inline),blobs=len(blobs),total_bytes=sum(p.stat().st_size for p in files),inline_chars=(temp/'inline.json').stat().st_size)))
