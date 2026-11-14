from pathlib import Path
import json,hashlib,math
import numpy as np
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent;checks=[]
for year in (2024,2025):
 for asset in ('BTC','ETH'):
  folder=OUT/str(year)/asset;assert json.loads((folder/'status.json').read_text())['completed']
  cfg=json.loads((folder/'config.json').read_text());assert cfg['source']=='BINANCE_USDT_PERPETUAL_ONLY' and cfg['fee']==0 and cfg['leverage']==3 and cfg['slippage']==.0002
  assert cfg['policy']['trend_level_distance_pct']==2 and cfg['ER']==[[12,.28284271247461906],[120,.1]]
  assert cfg['versions']==['CONTROL','DYNAMIC'] and not cfg['minute_HL_pruning']
  sources=json.loads((folder/'raw_sources.json').read_text());assert all(v['official_checksum_match'] and '/data/futures/um/daily/trades/' in v['url'] and not v['price_rewritten'] for v in sources.values())
  for profile in cfg['versions']:
   q=json.loads((folder/f'{profile}_result.json').read_text());assert q['no_OHLC_fallback'] and q['source']=='BINANCE_USDT_PERPETUAL_ONLY'
   assert q['period'][0].startswith(f'{year}-01-01') and q['period'][1].startswith(f'{year+1}-01-01')
   if profile=='CONTROL':assert q['stats'].get('partial_exits',0)==0
   marks=np.load(folder/f'{profile}_equity.npy');assert len(marks)==(int(__import__('datetime').datetime(year+1,1,1).timestamp())-int(__import__('datetime').datetime(year,1,1).timestamp()))//60
   assert abs(float(marks[-1])-q['ending_equity'])<1e-8
  checks.append(dict(year=year,asset=asset,source='BINANCE_USDT_PERPETUAL_ONLY',raw_archive_days=len(sources),ID_jump_steps=sum(v['non_contiguous_ID_steps'] for v in sources.values()),complete_calendar_window=True))
source=json.loads((ROOT/'outputs/retry_nov9_nov12/source_restore.json').read_text())
for row in source['files']:
 b=(ROOT/row['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==row['sha']
manifest=json.loads((ROOT/'outputs/er_dynamic_annual_2019_2026/rule_manifest.json').read_text());assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest['sha256'].items())
validation=json.loads((OUT/'event_selection_validation.json').read_text());assert len(validation['checks'])==64 and all(v['passed'] for v in validation['checks'])
(OUT/'completion.json').write_text(json.dumps(dict(completed=True,years=[2024,2025],only_perpetual=True,original_source_unchanged=True,dynamic_rule_unchanged=True,financial_event_selection_synthetic_cases=64,checks=checks),ensure_ascii=False,indent=2))
print('Perpetual-only full-year outputs, frozen rules and original source verified.')
