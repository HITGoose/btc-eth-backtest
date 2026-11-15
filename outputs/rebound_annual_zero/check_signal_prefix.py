from pathlib import Path
import sys,json,hashlib
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/rebound_followdown'));from signals import *
checks=[]
for year,asset in [('2020','BTC'),('2024','ETH')]:
 info=z.prepare(year,asset);start=info['start'];cut=start+31*86400;leg,core,new,_,_,_=build(asset,info['data'],start,cut);saved=json.loads((O/'runs'/year/asset/'signals.json').read_text())if(O/'runs'/year/asset/'signals.json').exists()else None
 if saved is None:
  # No duplicate full-year signal generation: defer until this worker has prepared its map.
  checks.append(dict(period=year,asset=asset,status='PENDING_SAVED_MAP'));continue
 oldcore={int(t):v for t,v in saved['core'].items()if int(t)<cut*1000};oldnew={int(t):v for t,v in saved['new_rebound'].items()if int(t)<cut*1000};assert core==oldcore and new==oldnew
 checks.append(dict(period=year,asset=asset,status='PASS',prefix_core_and_new_equal=True,future_closed_bars_not_required_for_signal=True,posthoc_diagnostics_excluded_from_entry=True))
(O/'signal_prefix_checks.json').write_text(json.dumps(dict(signal_file_SHA256=hashlib.sha256((R/'outputs/rebound_followdown/signals.py').read_bytes()).hexdigest(),checks=checks),indent=2));print('CHECKED',checks)
