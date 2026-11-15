import urllib.request,json,hashlib,datetime,pathlib,concurrent.futures
O=pathlib.Path(__file__).resolve().parent
urls=[f'https://data.binance.vision/data/futures/um/daily/trades/{a}USDT/{a}USDT-trades-2026-11-{d}.zip.CHECKSUM' for a in ['BTC','ETH'] for d in ['13','14','15']]
urls+=['https://www.binance.com/fapi/v1/time']
def run(url):
 try:
  with urllib.request.urlopen(url,timeout=25) as f:raw=f.read();code=f.status
 except urllib.error.HTTPError as e:raw=e.read();code=e.code
 except Exception as e:return dict(url=url,error=repr(e))
 name=hashlib.sha256(url.encode()).hexdigest()[:16]+'.raw';(O/name).write_bytes(raw)
 return dict(url=url,status=code,SHA256=hashlib.sha256(raw).hexdigest(),file=name,received_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),body=raw.decode(errors='replace')[:600])
r=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(run,urls));(O/'probe.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
