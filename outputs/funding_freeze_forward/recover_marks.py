"""Official minute mark archives: never relabel estimates as exact settlements."""
from pathlib import Path
import sys,json,urllib.request,hashlib,zipfile,csv,io,datetime,concurrent.futures
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;OLD=R/'outputs/extra_sizing_cost_stress';D=O/'mark_archives';D.mkdir(exist_ok=True)
def get(url,p):
 if not p.exists():
  with urllib.request.urlopen(url,timeout=60)as q:raw=q.read()
  p.write_bytes(raw)
 raw=p.read_bytes();return raw,dict(url=url,file=str(p.relative_to(O)),bytes=len(raw),SHA256=hashlib.sha256(raw).hexdigest(),acquired_UTC=datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),inspected_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),market='BINANCE_USDT_PERPETUAL',kind='markPriceKlines',timestamp_unit='ms')
def month_task(key):
 asset,month,wanted=key;stem=f'{asset}USDT-1m-{month}.zip';url=f'https://data.binance.vision/data/futures/um/monthly/markPriceKlines/{asset}USDT/1m/{stem}'
 try:
  checksum,cs=get(url+'.CHECKSUM',D/(stem+'.CHECKSUM'));raw,src=get(url,D/stem);assert src['SHA256']==checksum.decode().split()[0];src['official_checksum_match']=True;src['checksum_response']=cs
  found={}
  with zipfile.ZipFile(io.BytesIO(raw))as z:
   assert len(z.namelist())==1
   for row in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]))):
    if not row[0].isdigit():continue
    t=int(row[0]);end=int(row[6]);assert 0<end-t<=60000 and t%60000==0
    if t in wanted:
     o,h,l,c=map(float,row[1:5]);assert 0<l<=min(o,c)<=max(o,c)<=h
     found[t]=dict(open=o,high=h,low=l,close=c,open_time_ms=t,close_time_ms=end,raw=row)
  src['missing_minute_opens_ms']=sorted(set(wanted)-set(found));return asset,month,found,src
 except Exception as e:return asset,month,{},dict(url=url,error=repr(e),status='UNVERIFIED')
def main():
 sources={};needs={};base={}
 for period in ['2020','2021','2022','2023']:
  for asset in ['BTC','ETH']:
   p=OLD/'funding_data'/period/asset/'result.json';q=json.loads(p.read_text());base[(period,asset)]=q
   for r in q['invalid_records']:
    t=int(r['fundingTime']);m=datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).strftime('%Y-%m');needs.setdefault((asset,m),set()).add(t//60000*60000)
 allmarks={};provenance=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
  for asset,m,found,src in pool.map(month_task,[(a,m,w)for(a,m),w in sorted(needs.items())]):
   allmarks.update({(asset,t):v for t,v in found.items()});sources[(asset,m)]=src;provenance.append(src);print(asset,m,'minutes',len(found),src.get('error','OK'),flush=True)
   (O/'mark_archive_sources.json').write_text(json.dumps(provenance,indent=2))
 # Monthly official mark archives themselves have some absent minutes.
 # Query only still-missing exact minute windows, preserve raw API responses.
 for (asset,month),wanted in sorted(needs.items()):
  for t in sorted(wanted):
   if (asset,t) in allmarks:continue
   url=f'https://www.binance.com/fapi/v1/markPriceKlines?symbol={asset}USDT&interval=1m&startTime={t}&endTime={t+59999}&limit=1'
   try:
    raw,src=get(url,D/f'{asset}_{t}_API.json');rows=json.loads(raw);assert len(rows)==1 and int(rows[0][0])==t and int(rows[0][6])==t+59999
    b=rows[0];o,h,l,c=map(float,b[1:5]);assert 0<l<=min(o,c)<=max(o,c)<=h
    allmarks[(asset,t)]=dict(open=o,high=h,low=l,close=c,open_time_ms=t,close_time_ms=t+59999,raw=[str(v)for v in b])
    src['official_checksum_match']=None;src['api_minute_recovery']=True;provenance.append(src)
   except Exception as e:provenance.append(dict(url=url,status='UNVERIFIED',error=repr(e)))
 (O/'mark_archive_sources.json').write_text(json.dumps(provenance,indent=2))
 summary=[]
 for (period,asset),q in base.items():
  feeds={mode:[]for mode in ['OPEN','HIGH','LOW']};missing=[];exact=0
  invalid={int(r['fundingTime'])for r in q['invalid_records']}
  for r in q['records']:
   t=int(r['fundingTime']);estimate=t in invalid;bar=allmarks.get((asset,t//60000*60000))if estimate else None
   if estimate and(bar is None or not bar['open_time_ms']<=t<=bar['close_time_ms']):missing.append(r);continue
   if not estimate:exact+=1
   for mode in feeds:
    price=bar[mode.lower()]if estimate else float(r['markPrice'])
    feeds[mode].append(dict(time_ms=t,rate=float(r['fundingRate']),mark_price=price,complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',price_quality=('APPROXIMATE_FUNDING_MINUTE_'+mode if estimate else'EXACT_OFFICIAL_SETTLEMENT'),official_rate_record=r,mark_minute=bar if estimate else None))
  data=dict(period=period,asset=asset,status='APPROXIMATE_FUNDING'if not missing else'UNVERIFIED',strict_exact_status='UNVERIFIED',exact_price_records=exact,estimated_price_records=len(q['records'])-exact-len(missing),missing=missing,feeds=feeds,original_rate_source_SHA256=hashlib.sha256((OLD/'funding_data'/period/asset/'result.json').read_bytes()).hexdigest(),minute_extremes_are_not_account_bounds=True,signals_never_use_estimated_mark_prices=True)
  folder=O/'funding_feeds'/period/asset;folder.mkdir(parents=True,exist_ok=True);(folder/'result.json').write_text(json.dumps(data));summary.append({k:v for k,v in data.items()if k!='feeds'})
 (O/'funding_recovery_summary.json').write_text(json.dumps(summary,indent=2));print('FINISHED',len(summary),'feeds')
if __name__=='__main__':main()
