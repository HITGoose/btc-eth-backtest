from pathlib import Path
import sys
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/extra_sizing_cost_stress'));import shared as s
z=s.z;np=s.np

def form(a,prev):return prev[4]>prev[1] and a[4]<a[1] and a[4]<prev[3]
def admission(shape,state,lines,outside,macd,sma,extra):return bool(shape and state=='down' and lines>=6 and outside and macd<0 and sma and extra)
def build(asset,data,start,end):
 leg,_,_,_,policy,pair=s.b.p.prepare(asset,data/f'{asset}_15m.csv',start,end)
 _,core,_,_,_=z.s.prepare(asset,data,start,end,.25,leg,policy,pair)
 # Fresh read-only original trend/retest instance; never consumes live CORE state.
 _,context=z.s.clone_schedule(.25)(asset,z.s.Probe(leg,-1),price_file=data/f'{asset}_15m.csv',include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
 raw=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)]
 sma5=s.r.model.sma(raw[:,4],5);sma20=s.r.model.sma(raw[:,4],20);new={};diagnostics=[]
 for t,c in context.items():
  if not start*1000<=t<end*1000:continue
  i=(t-leg.first)//900000-1
  if i<32:continue
  a=raw[i];prev=raw[i-1];gate=c['gate_confirmation'];shape=bool(form(a,prev));state=c['regime'];dist=gate['distance_to_confirmed_hourly_level_pct'];near=dist is not None and dist<=2.;edge=min(raw[i-32:i,3]);median=np.median(raw[i-20:i,5]);volume=bool(a[4]<edge and a[4]<a[1] and a[4]<prev[4] and median>0 and a[5]>=1.5*median);retest=bool(gate['confirmed_retest']);extra=near or volume or retest
  ok=admission(shape,state,int(leg.down[i]),bool(leg.below_band[i]),float(leg.histogram[i]),sma5[i]<sma20[i],extra)
  if ok and t not in core:new[t]=-1
  if shape:
   future=raw[i+1:i+5];reclaim=bool(len(future) and np.any(future[:,4]>prev[3]));states=[context.get(t+j*900000,{}).get('regime','NOT_EVALUATED')for j in range(1,5)]
   diagnostics.append(dict(signal_close_ms=t,shape=True,regime=state,down_lines=int(leg.down[i]),outside=bool(leg.below_band[i]),macd=float(leg.histogram[i]),SMA5_20=bool(sma5[i]<sma20[i]),near_absolute_2pct=bool(near),volume_breakout=volume,retest=retest,historical_minimum_bandwidth_pct=float(leg.squeeze[96][i]),new_signal=t in new,core_direction=core.get(t,0),broken_level=float(prev[3]),false_break_reclaim_within4=reclaim,posthoc_closed_bars=len(future),posthoc_regime_becomes_range=any(v in ['range','transition']for v in states),posthoc_not_used_for_entry=True))
 core={t:v for t,v in core.items()if start*1000<=t<end*1000}
 return leg,core,new,diagnostics,policy,pair
