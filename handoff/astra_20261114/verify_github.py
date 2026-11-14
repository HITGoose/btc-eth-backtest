"""Offline verification of GitHub text artifacts, excluding raw market data."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[2]
manifest=json.loads((root/'handoff/astra_20261114/github_sync_manifest.json').read_text())
failed=[]
for item in manifest['files']:
 path=root/item['path']
 # Published text uses LF newlines, even on a checkout with autocrlf enabled.
 if not path.is_file() or hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()!=item['sha256']:failed.append(item['path'])
if failed:raise SystemExit('FAILED: '+', '.join(failed))
print('PASS',len(manifest['files']),'published text files; market data intentionally excluded')
