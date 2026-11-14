"""Public feed capability probe; never a financial strategy input."""
import asyncio,aiohttp,time,json,hashlib,os
from pathlib import Path
O=Path(__file__).resolve().parent
async def main():
 url='wss://fstream.binance.com/stream?streams=btcusdt@trade/ethusdt@trade/btcusdt@aggTrade';rows=[];error=None
 try:
  async with aiohttp.ClientSession(trust_env=True,timeout=aiohttp.ClientTimeout(total=18))as s:
   async with s.ws_connect(url,timeout=10,proxy=os.environ.get('https_proxy')or os.environ.get('HTTPS_PROXY'))as ws:
    until=time.time()+8
    while time.time()<until:
     try:m=await asyncio.wait_for(ws.receive(),timeout=max(.1,until-time.time()))
     except asyncio.TimeoutError:break
     if m.type==aiohttp.WSMsgType.TEXT:rows.append(dict(received_us=time.time_ns()//1000,raw=m.data,data=json.loads(m.data)))
 except Exception as e:error=repr(e)
 raw=json.dumps(rows).encode();(O/'ws_proxy_probe_messages.json').write_bytes(raw);q=dict(url=url,error=error,messages=len(rows),streams={k:sum(r['data'].get('stream')==k for r in rows)for k in sorted({r['data'].get('stream','unknown')for r in rows})},SHA256=hashlib.sha256(raw).hexdigest(),not_used_by_frozen_simulator=True)
 (O/'ws_proxy_probe_result.json').write_text(json.dumps(q,indent=2));print(json.dumps(q))
asyncio.run(main())
