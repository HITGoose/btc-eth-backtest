from pathlib import Path
import json,csv,collections
O=Path(__file__).resolve().parent;rows=[]
for folder in(O/'runs').glob('*/*'):
 if not(folder/'signals.json').exists():continue
 m=json.loads((folder/'signals.json').read_text())['accepted'];a={int(t):v for t,v in m['A'].items()};e={int(t):v for t,v in m['E1'].items()};di={int(r['signal_close_ms']):r for r in csv.DictReader((folder/'E1_conditions.csv').open(encoding='utf-8-sig'))}
 for t,side in a.items():
  if e.get(t)!=side:rows.append(dict(period=folder.parent.name,asset=folder.name,**di.get(t,dict(signal_close_ms=t,side=side))))
with(O/'floor_remaining_removed_signals.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
assert all(r['regime']=='range'and r['historical_pass']=='True'and r['range_width_pass']=='False'for r in rows)
print('Verified remaining removals',len(rows),'all due current range width')
