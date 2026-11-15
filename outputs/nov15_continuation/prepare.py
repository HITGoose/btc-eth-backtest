from pathlib import Path
import sys,json,urllib.request,urllib.parse,hashlib,datetime,concurrent.futures
import numpy as np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;DATA=O/'data';DATA.mkdir(exist_ok=True);RAW=O/'responses';RAW.mkdir(exist_ok=True)
START=1794528000000;NOW=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000);END=NOW//900000*900000
sources=[]
def req(endpoint,params):
 url='https://www.binance.com/fapi/v1/'+endpoint+'?'+urllib.parse.urlencode(params);name=hashlib.sha256(url.encode()).hexdigest()+'.json';p=RAW/name
 if not p.exists():
  with urllib.request.urlopen(url,timeout=35)as f:p.write_bytes(f.read())
 b=p.read_bytes();obj=json.loads(b);assert isinstance(obj,list),(url,obj)
 sources.append(dict(url=url,SHA256=hashlib.sha256(b).hexdigest(),file=str(p.relative_to(O)),acquired_UTC=datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()));return obj
old=R/'outputs/nov9_today_simultaneous/data'
for a in ['BTC','ETH']:
 for k,step in [('15m',900000),('1m',60000)]:
  cursor=START-step;rows=[]
  while cursor<END:
   v=req('klines',dict(symbol=a+'USDT',interval=k,startTime=cursor,endTime=END-1,limit=1500));assert v;rows.extend(v);cursor=int(v[-1][0])+step
  q=np.array([[float(x)for x in row[:6]]for row in rows]);assert np.array_equal(q[:,0],np.arange(START-step,END,step));assert np.all(q[:,3]>0)
  if k=='15m':
   base=np.loadtxt(old/f'{a}_15m.csv',delimiter=',',skiprows=1);assert np.allclose(base[-1],q[0],rtol=1e-12,atol=1e-7),(a,'overlap15m differs');out=np.r_[base,q[1:]];np.savetxt(DATA/f'{a}_15m.csv',out,delimiter=',',header='timestamp,open,high,low,close,volume',comments='',fmt='%.17g')
  else:
   base=np.load(old/f'{a}_1m.npy');assert np.allclose(base[-1],q[0,1:6],rtol=1e-12,atol=1e-7),(a,'overlap1m differs');np.save(DATA/f'{a}_1m.npy',np.r_[base,q[1:,1:6]])
 cursor=START;rows=[]
 while cursor<END:
  v=req('fundingRate',dict(symbol=a+'USDT',startTime=cursor,endTime=END-1,limit=1000));rows+=v
  if len(v)<1000:break
  cursor=int(v[-1]['fundingTime'])+1
 prior=json.loads((R/f'outputs/extra_sizing_cost_stress/funding_data/NOV/{a}/result.json').read_text());feed=list(prior['events']);seen={x['time_ms']for x in feed}
 for x in rows:
  t=int(x['fundingTime']);assert x['symbol']==a+'USDT' and float(x['markPrice'])>0
  if t not in seen:feed.append(dict(time_ms=t,rate=float(x['fundingRate']),mark_price=float(x['markPrice']),complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',official_record=x));seen.add(t)
 assert [x['time_ms']for x in feed]==sorted(seen)
 (DATA/f'{a}_funding.json').write_text(json.dumps(dict(events=feed,new_raw_records=rows,prior_SHA256=hashlib.sha256(json.dumps(prior,sort_keys=True).encode()).hexdigest()),indent=2))
(O/'data_manifest.json').write_text(json.dumps(dict(signal_end_ms=END,actual_execution_end_ms=1794614400000,actual_execution_end_UTC='2026-11-14T00:00:00+00:00',missing_execution_dates=['2026-11-14','2026-11-15'],sources=sources,old_candles_overlap_exact=True),indent=2));print('PREPARED',END,len(sources))
