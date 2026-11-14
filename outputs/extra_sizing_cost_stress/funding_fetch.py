"""Official funding API records including exact event time and markPrice; never impute."""
from pathlib import Path
from decimal import Decimal
import urllib.request,urllib.parse,gzip,json,hashlib,concurrent.futures,time
import shared as s
O=s.OUT/'funding_data';O.mkdir(exist_ok=True)
BASE='https://www.binance.com/fapi/v1/fundingRate'
def request(params,path):
 url=BASE+'?'+urllib.parse.urlencode(params)
 if path.exists():raw=path.read_bytes()
 else:
  for attempt in range(3):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/json','Accept-Encoding':'identity','User-Agent':'quant-data-audit/1.0'}),timeout=25)as r:raw=r.read()
    if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
    obj=json.loads(raw);assert isinstance(obj,list)
    path.write_bytes(raw);break
   except Exception:
    if attempt==2:raise
    time.sleep(1)
 return json.loads(raw),dict(url=url,response_SHA256=hashlib.sha256(raw).hexdigest(),response_bytes=len(raw),stored=str(path.relative_to(s.OUT)))
def fetch(period,asset):
 folder=O/period/asset;folder.mkdir(parents=True,exist_ok=True)
 try:
  _,data,start,end,_,_=s.z.inputs(period,asset);cursor=(start-2*86400)*1000;limit_end=(end+2*86400)*1000;records=[];sources=[];page=0
  while cursor<limit_end:
   params=dict(symbol=asset+'USDT',startTime=cursor,endTime=limit_end,limit=1000)
   obj,source=request(params,folder/f'page_{page:03}.json');source['requested_start_ms']=cursor;sources.append(source)
   if not obj:break
   times=[int(x['fundingTime'])for x in obj];assert all(x['symbol']==asset+'USDT'for x in obj)
   assert times==sorted(set(times))and cursor<=times[0]<=times[-1]<=limit_end
   records.extend(obj);cursor=times[-1]+1;page+=1
   if len(obj)<1000:break
  assert records and int(records[0]['fundingTime'])<=start*1000 and int(records[-1]['fundingTime'])>=end*1000,'boundary coverage missing'
  times=[int(x['fundingTime'])for x in records];assert len(times)==len(set(times))
  relevant=[x for x in records if start*1000<=int(x['fundingTime'])<end*1000]
  invalid=[];events=[]
  for x in relevant:
   try:
    mark=Decimal(x['markPrice']);rate=Decimal(x['fundingRate']);assert mark.is_finite()and mark>0 and rate.is_finite()
   except Exception:invalid.append(x);continue
   events.append(dict(time_ms=int(x['fundingTime']),rate=float(rate),mark_price=float(mark),complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',official_record=x))
  status='COMPLETE'if not invalid else'PARTIAL'
  result=dict(period=period,asset=asset,status=status,window_ms=[start*1000,end*1000],events=events,records=relevant,invalid_records=invalid,sources=sources,preceding_record=next((x for x in reversed(records)if int(x['fundingTime'])<start*1000),None),following_record=next((x for x in records if int(x['fundingTime'])>=end*1000),None),constant_interval_assumed=False,imputed_marks=False,official_rate_is_not_account_fee=True)
  s.dump(folder/'result.json',result);print(period,asset,status,'events',len(events),'invalid',len(invalid),flush=True)
 except Exception as e:s.dump(folder/'failure.json',dict(error=repr(e),period=period,asset=asset,status='UNVERIFIED'));print('FAIL',period,asset,repr(e),flush=True)
def main():
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:list(pool.map(lambda x:fetch(*x),[(p,a)for p in s.z.PERIODS for a in ('ETH','BTC')]))
if __name__=='__main__':main()
