from pathlib import Path
import sys,json,hashlib,pickle
from types import FunctionType
from dataclasses import replace,asdict
import numpy as np
import pandas as pd
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/extra_sizing_cost_stress'));import shared as s
z=s.z;r=s.r;SETTINGS=r.model.Settings(96,5,.25,'uncapped');POLICY=r.RegimeOverlay(.25,.50,2.,True);PAIR=((12,.28284271247461906),(120,.10));SPECS={'A':dict(family='A',parameters=[.25,.50]),'B15':dict(family='B',parameters=[.15,.40]),'B20':dict(family='B',parameters=[.20,.45]),'B25':dict(family='B',parameters=[.25,.50]),'C05':dict(family='C',parameters=[.5,1.]),'C10':dict(family='C',parameters=[1.,2.]),'C15':dict(family='C',parameters=[1.5,3.])}
def digest_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rolling_min(x,n):return pd.Series(np.where(np.isfinite(x),x,np.nan)).rolling(n,min_periods=n).min().to_numpy()
def past_quantile(x,q):return pd.Series(np.where(np.isfinite(x),x,np.nan)).shift(1).rolling(2880,min_periods=2880).quantile(q,interpolation='linear').to_numpy()
def atr_wilder(raw,n=96):
 tr=np.full(len(raw),np.nan);tr[1:]=np.maximum.reduce([raw[1:,2]-raw[1:,3],np.abs(raw[1:,2]-raw[:-1,4]),np.abs(raw[1:,3]-raw[:-1,4])]);atr=np.full(len(raw),np.nan);buf=[];prev=None
 for i,t in enumerate(tr):
  if not np.isfinite(t):buf=[];prev=None;continue
  if prev is None:
   buf.append(float(t))
   if len(buf)==n:prev=sum(buf)/n;atr[i]=prev
  else:prev=((n-1)*prev+t)/n;atr[i]=prev
 return tr,atr
class MaskLeg:
 def __init__(self,leg,mask):self.leg=leg;self.mask=mask
 def __getattr__(self,k):return getattr(self.leg,k)
 def signals(self,settings,**kw):
  # The fixed .25 gate is removed only from candidate construction here;
  # the explicitly selected A/B/C historical mask is the actual admission gate.
  candidates=self.leg.signals(replace(SETTINGS,squeeze_threshold=float('inf')),**kw)
  return {t:v for t,v in candidates.items()if self.mask[(t-self.leg.first)//900000-1]}
def schedule(asset,leg,file):
 fn=r.regime.market_schedules;clone=FunctionType(fn.__code__,dict(fn.__globals__,ENTRY=SETTINGS),fn.__name__,fn.__defaults__,fn.__closure__);clone.__kwdefaults__=dict(fn.__kwdefaults__ or {})
 return clone(asset,leg,price_file=file,include_gate_confirmation=True,regime_thresholds=PAIR,use_entry_crosses=False)
def make(asset,data,start,end,names=None):
 names=list(SPECS)if names is None else names;file=data/f'{asset}_15m.csv';leg=r.model.build(file,(start-30*86400)*1000,end*1000);raw=np.loadtxt(file,delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)];assert len(raw)==len(leg.width)
 W=np.array(leg.width);S=rolling_min(W,96);tr,atr=atr_wilder(raw);lines=np.stack([r.model.sma(raw[:,4],n)for n in [20,60,120]]+[r.model.ema(raw[:,4],n)for n in [20,60,120]]);gap=lines.max(axis=0)-lines.min(axis=0);N=np.divide(gap,atr,out=np.full(len(atr),np.nan),where=np.isfinite(atr)&(atr>0));NS=rolling_min(N,96);maps={};details={};thresholds={};first_i=(start*1000-leg.first)//900000
 for name in names:
  spec=SPECS[name];family=spec['family'];a,b=spec['parameters']
  if family=='A':metric,current,ht,wt=S,W,np.full(len(W),a),np.full(len(W),b)
  elif family=='B':metric,current,ht,wt=S,W,past_quantile(S,a),past_quantile(W,b)
  else:metric,current,ht,wt=NS,N,np.full(len(W),a),np.full(len(W),b)
  hist=np.isfinite(metric)&np.isfinite(ht)&(metric<=ht);width=np.isfinite(current)&np.isfinite(wt)&(current<=wt);proxy=MaskLeg(leg,hist);schedules,ctx=schedule(asset,proxy,file);out={};rows=[]
  for t,side in schedules['baseline'].items():
   if not start*1000<=t<end*1000:continue
   i=(t-leg.first)//900000-1;gate=ctx[t]['gate_confirmation'];state=ctx[t]['regime']
   if gate['aligned_lines']<6:continue
   if state=='range':eligible=bool(hist[i]and width[i])
   elif state=='transition':eligible=not POLICY.pause_transition
   elif r.regime.DIRECTIONS.get(state)==side:
    distance=gate['distance_to_confirmed_hourly_level_pct'];eligible=bool(gate['short_term_alignment']and((distance is not None and distance<=2.)or gate['directional_volume_breakout']or gate['confirmed_retest']))
   else:eligible=False
   rows.append(dict(signal_close_ms=t,side=side,regime=state,historical_metric=float(metric[i]),historical_threshold=float(ht[i]),current_metric=float(current[i]),current_threshold=float(wt[i])if np.isfinite(wt[i])else None,historical_pass=bool(hist[i]),range_width_pass=bool(width[i]),accepted=eligible,aligned_lines=gate['aligned_lines'],short_term_alignment=gate['short_term_alignment'],distance_pct=gate['distance_to_confirmed_hourly_level_pct'],volume_breakout=gate['directional_volume_breakout'],confirmed_retest=gate['confirmed_retest']))
   if eligible:out[t]=side
  if family=='A':
   original_schedules,original_ctx=schedule(asset,leg,file);reference=r.stacked_signals(original_schedules['baseline'],original_ctx,POLICY);reference={t:v for t,v in reference.items()if start*1000<=t<end*1000};assert reference==out
  if family=='B':assert np.isfinite(ht[first_i])and np.isfinite(wt[first_i]),'Insufficient fully finite past2880 warmup'
  maps[name]=out;details[name]=rows;thresholds[name]=dict(family=family,parameters=[a,b],finite_history_at_start=bool(np.isfinite(ht[first_i])),first_historical_threshold=float(ht[first_i])if np.isfinite(ht[first_i])else None,first_current_threshold=float(wt[first_i])if np.isfinite(wt[first_i])else None)
 return dict(leg=leg,maps=maps,diagnostics=details,thresholds=thresholds,first=leg.first,raw=raw,W=W,S=S,N=N,NS=NS,ATR=atr)
def mix(core,extra):
 out=dict(extra);out.update(core);return out
