from pathlib import Path
import urllib.request,urllib.error,hashlib,json,datetime
O=Path(__file__).resolve().parent;rows=[]
for a in ['BTC','ETH']:
 url=f'https://data.binance.vision/data/futures/um/daily/trades/{a}USDT/{a}USDT-trades-2026-11-14.zip.CHECKSUM'
 try:
  with urllib.request.urlopen(url,timeout=20)as f:raw=f.read();status=f.status
 except urllib.error.HTTPError as e:raw=e.read();status=e.code
 except Exception as e:raw=repr(e).encode();status='ERROR'
 (O/(a+'_20261114_daily_checksum_response.raw')).write_bytes(raw);rows.append(dict(asset=a,url=url,status=status,acquired_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),SHA256=hashlib.sha256(raw).hexdigest(),body=raw[:1000].decode(errors='replace')))
(O/'daily_recovery_probe.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
