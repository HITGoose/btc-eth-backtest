"""Isolated parameterization and side-effect-free complete candidate diagnostics."""
from pathlib import Path
from dataclasses import replace
from types import FunctionType
import importlib.util,json,csv,gzip
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('density_locked_v2',ROOT/'outputs/adaptive_risk_exit_v2/worker.py');v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v)
e=v.e;p=e.p;r=e.r;d=e.d
BASE_COMMIT='0ad7902161b91e7cf5538c5c06195c4a39086c24'
GROUPS={'A':(.25,False),'B':(.25,True),'C':(.30,False),'D':(.30,True),'E':(.35,False),'F':(.35,True)}

def clone_schedule(threshold):
 original=r.regime.market_schedules
 fn=FunctionType(original.__code__,dict(original.__globals__,ENTRY=replace(r.regime.ENTRY,squeeze_threshold=threshold)),original.__name__,original.__defaults__,original.__closure__)
 fn.__kwdefaults__=dict(original.__kwdefaults__ or {});return fn

def inputs(period,asset):
 if period=='NOV':folder=ROOT/'outputs/nov9_today_simultaneous/2026';data=ROOT/'outputs/nov9_today_simultaneous/data';manifest=data.parent/'candle_sources.json'
 else:
  year=int(period);folder=ROOT/(f'outputs/adaptive_risk_exit_v2/{year}' if year in (2024,2025) else f'outputs/adaptive_risk_exit_v2_extended/{year}')
  data=ROOT/('outputs/er_partial_2020/data' if year==2020 else 'outputs/attribution_2026/data' if year==2026 else f'outputs/other_years_050/{year}/data')
  manifest=ROOT/('outputs/attribution_2026/candle_sources.json' if year==2026 else f'outputs/er_partial_2020/{asset}_candle_sources.json' if year==2020 else f'outputs/other_years_050/{year}/{asset}_candle_sources.json')
 q=json.loads((folder/asset/'CONTROL_result.json').read_text())
 from datetime import datetime
 start,end=[int(datetime.fromisoformat(x).timestamp())for x in q['period']]
 sources=json.loads(manifest.read_text());assert sources and all('/data/futures/um/' in x['url'] and x['official_checksum_match']for x in sources)
 raw=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1);assert np.array_equal(raw[:,0],np.arange(raw[0,0],raw[-1,0]+900000,900000));assert raw[0,0]<=(start-150*3600)*1000 and raw[-1,0]>=(end-900)*1000
 minute=np.load(data/f'{asset}_1m.npy',mmap_mode='r');first=end-len(minute)*60;assert first<=start-60 and minute.shape[1]==5
 return folder,data,start,end,first,sources

def prepare(asset,data,start,end,threshold,leg=None,policy=None,pair=None):
 effective=threshold if asset=='ETH' else .25
 if leg is None:leg,old,ctx,base,policy,pair=p.prepare(asset,data/f'{asset}_15m.csv',start,end)
 policy=replace(policy,range_squeeze_pct=effective)
 schedule,context=clone_schedule(effective)(asset,leg,price_file=data/f'{asset}_15m.csv',include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
 signals=r.stacked_signals(schedule['baseline'],context,policy)
 return leg,signals,context,policy,pair

class Probe:
 def __init__(self,leg,side):self.leg=leg;self.side=side
 def __getattr__(self,k):return getattr(self.leg,k)
 def signals(self,settings,**kwargs):
  return {self.leg.first+(i+1)*900000:self.side for i in range(len(self.leg.width)-1) if self.leg.first+i*900000>=self.leg.start}

def diagnose(asset,data,leg,policy,pair):
 """Fresh read-only state per direction; never touches a live retest/account."""
 contexts={}
 for side in (1,-1):
  _,contexts[side]=clone_schedule(.25)(asset,Probe(leg,side),price_file=data/f'{asset}_15m.csv',include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
 # Complete pre-bandwidth baseline candidate set, including the bottom-level
 # five-line candidates subsequently rejected by the final six-line filter.
 candidates=leg.signals(replace(r.regime.ENTRY,squeeze_threshold=float('inf')))
 raw=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)]
 regimes,_=r.regime.hourly_context(leg.first,raw[:,4],raw[:,2],raw[:,3],regime_thresholds=pair)
 sma5=r.model.sma(raw[:,4],5);sma20=r.model.sma(raw[:,4],20)
 result={}
 for stamp,side in candidates.items():
  i=(stamp-leg.first)//900000-1;context=contexts[side][stamp];gate=context['gate_confirmation'];state=context['regime'];er=regimes.get(stamp//3600000*3600000)
  knowntrend=r.regime.DIRECTIONS.get(state)==side
  # Volume geometry is independently evaluated for either direction.
  edge=max(raw[i-32:i,2]) if side==1 else min(raw[i-32:i,3]);median=np.median(raw[i-20:i,5])
  volume=bool(side*(raw[i,4]-edge)>0 and side*(raw[i,4]-raw[i,1])>0 and side*(raw[i,4]-raw[i-1,4])>0 and median>0 and raw[i,5]>=1.5*median)
  result[stamp]=dict(signal_close_ms=stamp,side=side,signal_close=raw[i,4],historical_minimum_bandwidth_pct=float(leg.squeeze[96][i]),current_bandwidth_pct=float(leg.width[i]),aligned_lines=int((leg.up if side==1 else leg.down)[i]),close_outside_six=bool((leg.above_band if side==1 else leg.below_band)[i]),MACD_histogram=float(leg.histogram[i]),MACD_direction_pass=bool(side*leg.histogram[i]>0),ER_regime=state,ER_fast=er[1] if er else 'NOT_EVALUATED',ER_slow=er[2] if er else 'NOT_EVALUATED',SMA5=float(sma5[i]),SMA20=float(sma20[i]),SMA5_20_confirmation=bool(side*(sma5[i]-sma20[i])>0),distance_pct=gate['distance_to_confirmed_hourly_level_pct'] if gate['distance_to_confirmed_hourly_level_pct'] is not None else 'NOT_EVALUATED',near_absolute_2pct=bool(gate['distance_to_confirmed_hourly_level_pct'] is not None and gate['distance_to_confirmed_hourly_level_pct']<=2),directional_volume_breakout=volume,confirmed_retest=bool(gate['confirmed_retest']) if knowntrend else 'NOT_EVALUATED',retest_scope='separate fresh copied-source state; same-side trend gate' if knowntrend else 'NOT_EVALUATED: original retest admission only evaluated for matching ER trend',trend_confirmation_pass=bool(gate['short_term_alignment']),extra_trend_pass=bool((gate['distance_to_confirmed_hourly_level_pct'] is not None and gate['distance_to_confirmed_hourly_level_pct']<=2)or volume or gate['confirmed_retest']) if knowntrend else 'NOT_EVALUATED')
 return result

def dump(path,obj):d.dump(path,obj)
def csv_dump(path,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for row in rows for k in row));op=gzip.open if str(path).endswith('.gz')else open
 with op(path,'wt',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
