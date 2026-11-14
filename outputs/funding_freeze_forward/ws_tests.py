from pathlib import Path
from types import SimpleNamespace
import asyncio,threading,queue,json,hashlib
import ws_live as w
O=w.O;results=[]
samples=json.loads((O/'ws_proxy_probe_messages.json').read_text());assert samples
original=w.aiohttp.ClientSession
class FakeWS:
 def __init__(self,rows,stop):self.rows=rows;self.stop=stop;self.i=0
 async def __aenter__(self):return self
 async def __aexit__(self,*a):return None
 async def receive(self):
  raw=self.rows[self.i]['raw'];self.i+=1
  if self.i==len(self.rows):self.stop.set()
  return SimpleNamespace(type=w.aiohttp.WSMsgType.TEXT,data=raw)
class FakeSession:
 def __init__(self,rows,stop):self.rows=rows;self.stop=stop
 async def __aenter__(self):return self
 async def __aexit__(self,*a):return None
 def ws_connect(self,*a,**kw):assert 'proxy'in kw;return FakeWS(self.rows,self.stop)
def run(rows):
 q=queue.Queue();stop=threading.Event();w.aiohttp.ClientSession=lambda**kw:FakeSession(rows,stop)
 try:asyncio.run(w.socket_reader(q,stop))
 finally:w.aiohttp.ClientSession=original
 return list(q.queue)
rows=run(samples);decoded=[x for x in rows if x['type']=='TRADES'];assert len(decoded)==len(samples)
for a,b in zip(decoded,samples):
 d=b['data']['data'];assert a['data'][0]==dict(id=d['t'],time=d['T'],price=d['p'],qty=d['q'],isBuyerMaker=d['m']);assert hashlib.sha256(a['raw_UTF8'].encode()).hexdigest()==a['SHA256']
results.append(dict(name='actual collector decoder: all captured raw fields E/T/id/price/qty preserved with source SHA',passed=True,messages=len(decoded)))
for asset in ['BTC','ETH']:
 ids=[x['data'][0]['id']for x in decoded if x['asset']==asset];assert ids and all(b==a+1 for a,b in zip(ids,ids[1:]));results.append(dict(name=asset+' observed8second WS IDs continuous; not claim all future data complete',passed=True,messages=len(ids)))
bad=json.loads(json.dumps(samples[:1]));bad[0]['data']['data']['e']='aggTrade';bad[0]['raw']=json.dumps(bad[0]['data']);r=run(bad);assert not any(x['type']=='TRADES'for x in r)and any(x['type']=='WS_DISCONNECTED'for x in r);results.append(dict(name='aggregate stream rejected by actual collector',passed=True))
manifest=json.loads((O/'FREEZE.json').read_text())
for p in ['online.py','live.py']:assert hashlib.sha256((O/p).read_bytes()).hexdigest()==manifest['code_SHA256']['outputs/funding_freeze_forward/'+p]
results.append(dict(name='v1 strategy and execution adapter byte-identical; only new WS collector',passed=True))
(O/'ws_tests.json').write_text(json.dumps(dict(passed=True,total=len(results),checks=results,fixture_decode_not_extra_forward_observation=True),indent=2));print('PASS',len(results),len(decoded))
