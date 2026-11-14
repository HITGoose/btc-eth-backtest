from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
for f in sorted((OUT/'runs').glob('*/*/*/status.json')):
 q=json.loads(f.read_text());print('COMPLETE',str(f.parent.relative_to(OUT/'runs')),'REUSED_BTC'if q.get('reused_unchanged_verified_BTC_control')else'FRESH_REPLAY')
for f in sorted((OUT/'runs').glob('*/*/*/progress.json')):
 if(f.parent/'status.json').exists():continue
 q=json.loads(f.read_text());print('ACTIVE',str(f.parent.relative_to(OUT/'runs')),q['time'],'raw days',q['raw_days'])
for f in sorted((OUT/'runs').glob('*/*/*/failure.json')):
 print('FAILED',str(f.parent.relative_to(OUT/'runs')),json.loads(f.read_text())['error'])
