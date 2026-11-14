from pathlib import Path
import json,hashlib
ROOT=Path('/workspace/btc-eth-backtest');OUT=ROOT/'outputs/eth_density_experiment';TMP=Path('/tmp/eth_density_publication');TMP.mkdir(exist_ok=True)
files=[ROOT/'ETH_DENSITY_EXPERIMENT.md']
files +=[p for p in OUT.iterdir()if p.is_file()and(p.suffix in('.py','.md','.json','.csv','.log')or p.name.endswith('.csv.gz')or p.name=='incomplete_snapshots_2025.json.gz')and p.name not in('PROGRESS.md','bundle_receipt.json','publication_manifest.json','github_receipt.json')]
files+=list((OUT/'artifacts').glob('period_*.zip'))
files+=list((OUT/'validation32').glob('*.py'))+list((OUT/'validation32').glob('*.json'))+list((OUT/'validation32').glob('*.log'))
files+=list((OUT/'baseline').glob('status.json'))+list((OUT/'baseline').glob('*/*/regression.json'))
files+=list((OUT/'recovery_20250829_ETH').glob('*.json'))
files=sorted(set(files));inline=[];blobs=[];manifest=[]
for p in files:
 body=p.read_bytes();sha=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest();name=str(p.relative_to(ROOT));item=dict(path=name,bytes=len(body),git_sha=sha,sha256=hashlib.sha256(body).hexdigest());manifest.append(item)
 if p.suffix in('.zip','.gz')or len(body)>170000:blobs.append(item)
 else:inline.append(dict(path=name,mode='100644',type='blob',content=body.decode('utf-8')))
(ROOT/'outputs/eth_density_experiment/publication_manifest.json').write_text(json.dumps(dict(base_commit='0ad7902161b91e7cf5538c5c06195c4a39086c24',financial_code_commit='48491ee19b7cb96a77a0a90e2481c55c0350e678',full_history_complete=False,files=manifest,excludes=['raw archives','equity.npy','checkpoint.pkl.gz','full duplicated delivery ZIP']),ensure_ascii=False,indent=2)+'\n')
p=OUT/'publication_manifest.json';inline.append(dict(path=str(p.relative_to(ROOT)),mode='100644',type='blob',content=p.read_text()))
(TMP/'inline.json').write_text(json.dumps(inline,ensure_ascii=False));(TMP/'blobs.json').write_text(json.dumps(blobs,ensure_ascii=False));print(json.dumps(dict(inline=len(inline),blobs=len(blobs),total_bytes=sum(x['bytes']for x in manifest),largest=max(x['bytes']for x in blobs))))
