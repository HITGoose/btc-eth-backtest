from pathlib import Path
import urllib.request,urllib.error,json,hashlib,datetime,re
O=Path(__file__).resolve().parent
urls=['https://developers.binance.com/llms.txt','https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Trade-Streams.md','https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Trade-Streams']
rows=[]
for i,url in enumerate(urls):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'text/markdown'}),timeout=15)as f:raw=f.read();status=f.status
 except urllib.error.HTTPError as e:raw=e.read();status=e.code
 except Exception as e:raw=repr(e).encode();status='ERROR'
 p=O/f'zero_doc_{i}.raw';p.write_bytes(raw);text=raw.decode(errors='replace');matches=[text[max(0,m.start()-120):m.end()+180]for m in re.finditer(r'zero|placeholder|RPI|"NA"|zero.quantity',text,re.I)][:12]
 rows.append(dict(url=url,status=status,acquired_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),SHA256=hashlib.sha256(raw).hexdigest(),path=p.name,bytes=len(raw),matches=matches))
(O/'zero_doc_probes.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
