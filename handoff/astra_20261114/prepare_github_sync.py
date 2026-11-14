from pathlib import Path
import json,csv,hashlib
ROOT=Path('/workspace/btc-eth-backtest');OUT=ROOT/'handoff/astra_20261114';BRANCH='codex/adaptive-v2-astra-20261114'
status=OUT/'git_status.json'
if not (OUT/'git_status_before_sync.json').exists():(OUT/'git_status_before_sync.json').write_text(status.read_text())
q=json.loads(status.read_text());q.update(branch=BRANCH,revision_V2_pushed=True,new_commit_created=True,remote_ref_updated=True,statement='This branch publishes the V2 source and review artifacts; previous pre-sync check is preserved in git_status_before_sync.json.');status.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n')
p=OUT/'README_FIRST.md';s=p.read_text().replace('修正版Git状态：尚未提交/推送。','修正版Git状态：本次已发布在独立分支codex/adaptive-v2-astra-20261114，main保留。此前同步前状态如下：').replace('包中代码不等于远端已更新。','本分支包含修正版及依赖；Git网页查看指引见仓库根ASTRA_REVIEW.md。').replace('用户本轮询问同步状态，本次没有向远端写入、创建PR或自动通知任何人。','本次用户已明确要求同步，修正版推送到独立分支，不覆盖main，不自动通知任何人。');p.write_text(s)
p=OUT/'STRATEGY_CURRENT.md';s=p.read_text().replace('读交接Git状态。','读交接Git状态；当前同步分支codex/adaptive-v2-astra-20261114。');p.write_text(s)
# Git-friendly shards retain every row and all Chinese headers in source CSV.
index=[]
for source in ('trades.csv','conditions.csv'):
 src=ROOT/'outputs/cross_asset_entry_audit'/source;dest=ROOT/'outputs/cross_asset_entry_audit/review_shards'/src.stem;dest.mkdir(parents=True,exist_ok=True)
 with src.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
 count=0
 for offset in range(0,len(rows),40 if source=='trades.csv' else 200):
  chunk=rows[offset:offset+(40 if source=='trades.csv' else 200)];path=dest/f'part_{count:03}.csv'
  with path.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(chunk)
  index.append(dict(source=source,path=str(path.relative_to(ROOT)),start_row=offset+1,rows=len(chunk),sha256=hashlib.sha256(path.read_bytes()).hexdigest()));count+=1
(ROOT/'outputs/cross_asset_entry_audit/review_shards/index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
original={x['path'] for x in json.loads((ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text())['files']}
files=set(ROOT.glob('outputs/**/*.py'));files.update(p for p in ROOT.glob('work/*.py') if str(p.relative_to(ROOT)) not in original)
for dirname in ('adaptive_risk_exit_v2','adaptive_risk_exit_v2_extended','nov9_today_simultaneous'):
 for p in (ROOT/'outputs'/dirname).rglob('*'):
  if p.is_file() and not any(x in ('data','temporary','__pycache__') for x in p.relative_to(ROOT/'outputs'/dirname).parts) and p.suffix in ('.json','.csv','.md','.log','.py'):files.add(p)
for name in ('summary.csv','audit.json','commands.md','run.log'):files.add(ROOT/'outputs/cross_asset_entry_audit'/name)
files.update((ROOT/'outputs/cross_asset_entry_audit/review_shards').rglob('*.csv'));files.add(ROOT/'outputs/cross_asset_entry_audit/review_shards/index.json')
files.update(p for p in OUT.iterdir() if p.suffix in ('.md','.csv','.json','.py') and p.name not in ('delivery_check.json','build_bundle.py','verify_bundle.py'))
files.add(ROOT/'outputs/retry_nov9_nov12/source_restore.json');files.add(ROOT/'ASTRA_REVIEW.md')
files={p for p in files if p.is_file() and str(p.relative_to(ROOT)) not in original}
entries=[dict(path=str(p.relative_to(ROOT)),mode='100644',type='blob',content=p.read_text(encoding='utf-8')) for p in sorted(files)]
# File manifest gives reviewers reproducible path and SHA of each published text.
manifest=dict(branch=BRANCH,base_commit='e66859aff89490b9b02c286e59d7d8270802972a',files=[dict(path=e['path'],bytes=len(e['content'].encode()),sha256=hashlib.sha256(e['content'].encode()).hexdigest()) for e in entries])
mp=OUT/'github_sync_manifest.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');entries.append(dict(path=str(mp.relative_to(ROOT)),mode='100644',type='blob',content=mp.read_text()))
batches=[];current=[];size=0
for entry in entries:
 n=len(json.dumps(entry,ensure_ascii=False).encode())
 if current and (size+n>260000 or len(current)>=35):batches.append(current);current=[];size=0
 current.append(entry);size+=n
if current:batches.append(current)
folder=Path('/tmp/btc_eth_github_sync');folder.mkdir(exist_ok=True)
for i,batch in enumerate(batches):(folder/f'batch_{i:03}.json').write_text(json.dumps(batch,ensure_ascii=False))
print(json.dumps(dict(files=len(entries),batches=len(batches),bytes=sum(len(e['content'].encode()) for e in entries),max_file=max(len(e['content'].encode()) for e in entries))))
