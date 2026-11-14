"""Derive missing same-venue bars only from checksum-verified complete trade days."""
from datetime import datetime,timezone,timedelta
import numpy as np

def restore(rows,expected,step,asset,year,out,d,r):
 missing=np.setdiff1d(expected,rows[:,0]);proofs=[];cache={};added=[];edges={}
 for stamp in missing:
  day=datetime.fromtimestamp(stamp,timezone.utc).strftime('%Y-%m-%d')
  if day not in cache:
   path=out/str(year)/f'{asset}_gap_{day}.zip';url=f'{d.BASE}/daily/aggTrades/{asset}USDT/{asset}USDT-aggTrades-{day}.zip'
   meta=d.acquire(url,path);raw=d.read_zip(path,[0,1,2,5]);scale=1e6 if raw[0,3]>1e14 else 1000
   times=raw[:,3]/scale
   if not np.all(np.diff(raw[:,0])==1) or np.any(np.diff(times)<0):raise RuntimeError('Cannot establish complete contiguous trade IDs for missing candle '+day)
   lower=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
   if times[0]<lower or times[-1]>=lower+86400:raise RuntimeError('Gap archive timestamp mismatch')
   cache[day]=(raw,times);path.unlink();proofs.append(dict(date=day,source=meta,contiguous_agg_trade_ids=True,first_id=float(raw[0,0]),last_id=float(raw[-1,0]),records=len(raw)))
  raw,times=cache[day];left,right=np.searchsorted(times,[stamp,stamp+step])
  if right>left:
   price=raw[left:right,1];row=[stamp,price[0],price.max(),price.min(),price[-1],raw[left:right,2].sum()];kind='DERIVED_OHLCV_FROM_COMPLETE_REAL_TRADES'
  else:
   # A missing edge of an archive cannot establish an empty market interval.
   # Verify adjacent archive IDs too when no print brackets the interval.
   for delta,need in ((-1,left==0),(1,right==len(raw))):
    if not need:continue
    neighbor=(datetime.strptime(day,'%Y-%m-%d')+timedelta(days=delta)).strftime('%Y-%m-%d')
    if neighbor not in edges:
     path=out/str(year)/f'{asset}_edge_{neighbor}.zip';url=f'{d.BASE}/daily/aggTrades/{asset}USDT/{asset}USDT-aggTrades-{neighbor}.zip'
     meta=d.acquire(url,path);edge=d.read_zip(path,[0,5]);scale=1e6 if edge[0,1]>1e14 else 1000;edge[:,1]/=scale
     if not np.all(np.diff(edge[:,0])==1):raise RuntimeError('Adjacent archive has missing IDs')
     edges[neighbor]=edge;path.unlink();proofs.append(dict(date=neighbor,boundary_archive=True,source=meta))
    edge=edges[neighbor]
    if delta==-1:
     if edge[-1,0]+1!=raw[0,0] or edge[-1,1]>=stamp:raise RuntimeError('Cannot verify missing interval at archive start')
    elif raw[-1,0]+1!=edge[0,0] or edge[0,1]<stamp+step:raise RuntimeError('Cannot verify missing interval at archive end')
   # Previous observed native close or earlier verified derived bar only.
   previous=added[-1] if added and added[-1][0]==stamp-step else None
   if previous is None:
    index=np.searchsorted(rows[:,0],stamp)-1
    if index<0 or rows[index,0]!=stamp-step:raise RuntimeError('Missing previous observed close for empty interval')
    previous=rows[index]
   price=float(previous[4]);row=[stamp,price,price,price,price,0.];kind='VERIFIED_NO_TRADES_PREVIOUS_OBSERVED_CLOSE'
  added.append(row);proofs.append(dict(interval_start=r.local_s(int(stamp)),seconds=step,derivation=kind,actual_trades=int(right-left),OHLCV=list(map(float,row[1:]))))
 if added:rows=np.concatenate((rows,np.asarray(added)));rows=rows[np.argsort(rows[:,0])]
 d.dump(out/str(year)/f'{asset}_{step}s_gap_proofs.json',proofs)
 return rows
