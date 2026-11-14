"""Restore only missing native caches through frozen official download flows.

Each legacy preparer runs in a fresh process to avoid the repository's run/
worker module-name collisions. Does not call their backtest entry functions.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,importlib.util,subprocess,sys,shutil,json
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent

def location(period):
 return ROOT/('outputs/er_partial_2020/data'if period=='2020'else'outputs/attribution_2026/data'if period=='2026'else'outputs/nov9_today_simultaneous/data'if period=='NOV'else f'outputs/other_years_050/{period}/data')

def child(period,asset):
 file=ROOT/('outputs/er_partial_2020/run_2020.py'if period=='2020'else'outputs/attribution_2026/binance_inputs.py'if period=='2026'else'outputs/nov9_today_simultaneous/run.py'if period=='NOV'else'outputs/other_years_050/batch.py')
 spec=importlib.util.spec_from_file_location('frozen_native_preparer',file);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
 if period=='2026':module.prepare()
 elif period=='NOV':module.prepare()
 elif period=='2020':module.d.BASE='https://data.binance.vision/data/futures/um';module.prepare(asset)
 else:module.e.d.BASE='https://data.binance.vision/data/futures/um';module.prepare(int(period),asset)

def restore(period):
 data=location(period);files=[data/f'{a}_{suffix}'for a in ('BTC','ETH')for suffix in ('15m.csv','1m.npy')]
 if all(p.exists()and p.stat().st_size>0 for p in files):print('CACHE_PRESENT',period,'no overwrite');return
 if period=='NOV':restore('2026')
 # Protect any existing derived inputs before a preparer that writes both assets.
 backup=OUT/'input_backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')/period
 for p in files:
  if p.exists():backup.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup/p.name)
 assets=['BOTH']if period in ('2026','NOV')else['BTC','ETH']
 for asset in assets:
  result=subprocess.run([sys.executable,__file__,'--child',period,asset])
  if result.returncode:raise SystemExit(result.returncode)
 print('RESTORED',period,flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--period',choices=['2020','2021','2022','2023','2024','2025','2026','NOV','ALL'],default='ALL');a.add_argument('--child',nargs=2);args=a.parse_args()
 if args.child:child(*args.child)
 else:
  for period in (['2024','2025','2020','2021','2022','2023','2026','NOV']if args.period=='ALL'else[args.period]):restore(period)
