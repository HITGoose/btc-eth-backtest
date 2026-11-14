from pathlib import Path
import urllib.request,json,hashlib,datetime,importlib.util
O=Path(__file__).resolve().parent
urls=['https://www.binance.com/fapi/v1/historicalTrades?symbol=BTCUSDT&fromId=8274583249&limit=3','https://www.binance.com/fapi/v1/historicalTrades?symbol=ETHUSDT&fromId=8991228050&limit=3','https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Recent-Trades-List','https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams']
rows=[]
for i,url in enumerate(urls):
 try:
  with urllib.request.urlopen(url,timeout=20)as f:raw=f.read();status=f.status
 except urllib.error.HTTPError as e:raw=e.read();status=e.code
 except Exception as e:raw=repr(e).encode();status='ERROR'
 p=O/f'gap_probe_{i}.raw';p.write_bytes(raw);rows.append(dict(url=url,status=status,SHA256=hashlib.sha256(raw).hexdigest(),acquired_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),file=p.name,preview=raw[:700].decode(errors='replace')))
(O/'gap_probe.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2));print('WS modules',[(n,bool(importlib.util.find_spec(n)))for n in ['websockets','aiohttp']])
