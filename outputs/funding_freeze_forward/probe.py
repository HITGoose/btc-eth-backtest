import urllib.request,json,hashlib,datetime
from pathlib import Path
O=Path(__file__).resolve().parent
urls=['https://www.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=1581840000000&endTime=1581926400000&limit=10','https://data.binance.vision/data/futures/um/monthly/markPriceKlines/BTCUSDT/1m/BTCUSDT-1m-2020-02.zip.CHECKSUM','https://www.binance.com/fapi/v1/markPriceKlines?symbol=BTCUSDT&interval=1m&startTime=1581840000000&limit=1','https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=1581840000000&limit=1','https://www.binance.com/fapi/v1/time']
rows=[]
for i,url in enumerate(urls):
 try:
  with urllib.request.urlopen(url,timeout=25)as r:raw=r.read();status=r.status
 except Exception as e:raw=str(e).encode();status='ERROR'
 p=O/f'probe_{i}.raw';p.write_bytes(raw);rows.append(dict(url=url,status=status,received_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),SHA256=hashlib.sha256(raw).hexdigest(),path=p.name,preview=raw[:700].decode(errors='replace')))
(O/'probes.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
