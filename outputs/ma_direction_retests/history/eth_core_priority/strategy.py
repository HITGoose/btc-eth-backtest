"""Fixed five groups; import the locked density code with explicit paths."""
from pathlib import Path
import importlib.util,sys,json
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
OLD=ROOT/'outputs/eth_density_experiment'
def module(name,path):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
s=module('priority_locked_density_strategy',OLD/'strategy.py')
# worker.py's ordinary import must refer to the locked strategy, never old collect.
previous=sys.modules.get('strategy');sys.modules['strategy']=s
w=module('priority_locked_density_worker',OLD/'worker.py')
if previous is None:sys.modules.pop('strategy',None)
else:sys.modules['strategy']=previous
v=s.v;e=s.e;r=s.r;p=s.p;d=s.d
h=module('priority_analysis_helpers',OLD/'analysis_helpers.py')
BASE_COMMIT='01937b2d4a1306ab211a9c1853bda285258c2853'
GROUPS={'B':dict(threshold=.25,btc_confirm=False,priority=False),'D':dict(threshold=.30,btc_confirm=False,priority=False),'G':dict(threshold=.30,btc_confirm=True,priority=False),'H':dict(threshold=.30,btc_confirm=False,priority=True),'I':dict(threshold=.30,btc_confirm=True,priority=True)}
COSTS={'ZERO':0.,'ASSUMED_005_SIDE':.0005}
PERIODS=['2024','2025','2020','2021','2022','2023','2026','NOV']
dump=s.dump;csv_dump=s.csv_dump;inputs=s.inputs

def prepare(period,asset):
 ref,data,start,end,first,sources=inputs(period,asset)
 leg,old,ctx,base,policy,pair=p.prepare(asset,data/f'{asset}_15m.csv',start,end)
 core=s.prepare(asset,data,start,end,.25,leg,policy,pair)[1]
 wide=s.prepare(asset,data,start,end,.30,leg,policy,pair)[1]
 assert core==old['ER'];assert set(core.items())<=set(wide.items())
 if asset=='BTC':assert core==wide
 return dict(ref=ref,data=data,start=start,end=end,first=first,sources=sources,leg=leg,core=core,wide=wide,policy=policy,pair=pair)

def classify(core,wide,btc,group):
 cfg=GROUPS[group];signals=core if group=='B'else wide
 out={};decisions=[]
 for stamp,side in sorted(signals.items()):
  origin='CORE'if core.get(stamp)==side else'EXTRA'
  btc_side=btc.get(stamp,0)
  passed=origin=='CORE'or not cfg['btc_confirm']or btc_side==side
  decisions.append(dict(signal_close_ms=stamp,side=side,origin=origin,BTC_complete_signal=btc_side,BTC_filter_required=origin=='EXTRA'and cfg['btc_confirm'],accepted=passed))
  if passed:out[stamp]=side
 return out,decisions
