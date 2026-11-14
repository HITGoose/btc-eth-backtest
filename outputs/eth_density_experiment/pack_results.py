from pathlib import Path
import json,hashlib,zipfile
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];ARCH=OUT/'artifacts';ARCH.mkdir(exist_ok=True)
def selected(root):
 if not root.exists():return[]
 return[p for p in root.rglob('*')if p.is_file()and not any(x in ('temporary','__pycache__','data')for x in p.relative_to(root).parts)and(p.suffix in('.json','.log','.md')or p.name=='conditions.csv.gz')]
def archive(path,files):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for f in sorted(set(files)):z.write(f,str(f.relative_to(ROOT)))
 with zipfile.ZipFile(path)as z:assert z.testzip()is None
 return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),files=len(set(files)))
items=[]
for period in ('2020','2021','2022','2023','2024','2025','2026','NOV'):
 files=selected(OUT/'runs'/period)
 if period in ('2024','2025'):files+=selected(OUT/'baseline'/period)
 if period=='2025':
  for suffix in ('25','30','35'):files+=selected(OUT/'isolation'/suffix)
 items.append(archive(ARCH/f'period_{period}_ledgers.zip',files))
small=[p for p in OUT.iterdir()if p.is_file()and(p.suffix in('.py','.md','.json','.csv','.log')or p.name.endswith('.csv.gz')or p.name=='incomplete_snapshots_2025.json.gz')]
small+=selected(OUT/'validation32')
small+=list((OUT/'validation32').glob('*.py'))
# Include targeted source checks and conflict evidence; never the bad raw ZIP.
small+=selected(OUT/'recovery_20250829_ETH')
small+=list(ARCH.glob('period_*.zip'))
manifest=dict(base_commit='0ad7902161b91e7cf5538c5c06195c4a39086c24',experiment_branch='codex/eth-density-025-030-035-20261114',period_archives=items,files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in sorted(set(small))],exclusions=['raw market CSV/ZIP','minute equity.npy','checkpoint pickle','input caches'])
(OUT/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
summary=archive(ARCH/'ETH_DENSITY_ALL_RESULTS.zip',small+[OUT/'delivery_manifest.json']);(OUT/'bundle_receipt.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
