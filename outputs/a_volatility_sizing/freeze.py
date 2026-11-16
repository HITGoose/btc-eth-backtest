from pathlib import Path
import json,math,hashlib,datetime,csv
import runner
O=Path(__file__).resolve().parent
rows=[];sources=[]
for y in ['2020','2021','2022']:
 for a in ['BTC','ETH']:
  p=O/'runs'/y/a/'ZERO_A_VOL_result.json';q=json.loads(p.read_text());assert q['code_fingerprint']==runner.code_fp()
  accepted=[r for r in q['sizing_audit']if r['accepted']];assert len(accepted)==q['stats']['submitted']
  for r in accepted:rows.append(dict(period=y,asset=a,**r))
  sources.append(dict(path=str(p.relative_to(O)),SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),orders=len(accepted)))
L=math.fsum(r['target_leverage']for r in rows)/len(rows)
p=O/'FREEZE.json'
if p.exists():
 z=json.loads(p.read_text());assert z['L_fixed']==L and z['sources']==sources and z['code_fingerprint']==runner.code_fp()
else:
 z=dict(L_fixed=L,successful_submitted_orders=len(rows),method='Arithmetic mean of target leverage of ALL accepted ZERO A_VOL orders, 2020-2022 BTC and ETH; includes later unfilled orders',code_fingerprint=runner.code_fp(),frozen_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources)
 runner.dump(p,z)
runner.s.z.csv_dump(O/'calibration_orders.csv',rows)
print(json.dumps(z,ensure_ascii=False),flush=True)
