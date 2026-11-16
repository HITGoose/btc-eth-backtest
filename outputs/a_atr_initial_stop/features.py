import numpy as np

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

def parameters(atr,price):
 valid=bool(np.isfinite(atr)and atr>=0 and np.isfinite(price)and price>0)
 d=float(np.clip(2*atr/price,.01,.03))if valid else .02
 return dict(ATR96=float(atr)if np.isfinite(atr)else None,d=d,L=min(3.,.06/d),fallback=not valid)
