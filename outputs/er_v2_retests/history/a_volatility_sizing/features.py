import numpy as np
import pandas as pd

def atr96(raw):
 h=raw[:,2];lo=raw[:,3];c=raw[:,4];tr=np.full(len(raw),np.nan)
 if len(raw):tr[0]=h[0]-lo[0]
 tr[1:]=np.maximum.reduce([h[1:]-lo[1:],np.abs(h[1:]-c[:-1]),np.abs(lo[1:]-c[:-1])]);out=np.full(len(raw),np.nan);buf=[];prev=None
 for i,x in enumerate(tr):
  if not np.isfinite(x)or x<0:buf=[];prev=None;continue
  if prev is None:
   buf.append(float(x))
   if len(buf)==96:prev=sum(buf)/96;out[i]=prev
  else:prev=(95*prev+x)/96;out[i]=prev
 return tr,out

def compute(raw):
 tr,atr=atr96(raw);close=raw[:,4];v=np.divide(atr,close,out=np.full(len(close),np.nan),where=np.isfinite(close)&(close>0));x=pd.Series(np.where(np.isfinite(v)&(v>=0),v,np.nan));past=x.shift(1);n=past.rolling(2880,min_periods=1).count().fillna(0).to_numpy();ref=past.rolling(2880,min_periods=2880).median().to_numpy();valid=np.isfinite(v)&(v>0)&np.isfinite(ref)&(ref>=0)&(n==2880);m=np.ones(len(v));m[valid]=np.clip(ref[valid]/v[valid],.5,1.);reason=np.where(valid,'VALID',np.where(n<2880,'INSUFFICIENT_2880_VALID_PAST_V',np.where(~np.isfinite(v)|(v<=0),'INVALID_CURRENT_V','INVALID_REFERENCE')))
 return dict(TR=tr,ATR=atr,v=v,v_ref=ref,history_valid_count=n,m=m,L=3*m,valid=valid,fallback_reason=reason)
