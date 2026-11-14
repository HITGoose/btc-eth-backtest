"""Data adapter repair v2: official raw @trade WebSocket, unchanged online.Engine.
V1 REST freeze/tape remain immutable. New freeze/T0, no strategy or cost changes.
"""
from pathlib import Path
import sys,json,time,hashlib,pickle,queue,threading,concurrent.futures,traceback,gzip,shutil,asyncio,os
import aiohttp
import online as n
from live import Tape
O=n.O;URL='wss://fstream.binance.com/stream?streams=btcusdt@trade/ethusdt@trade'
async def socket_reader(output,stop):
 while not stop.is_set():
  try:
   async with aiohttp.ClientSession(trust_env=True)as session:
    async with session.ws_connect(URL,proxy=os.environ.get('https_proxy')or os.environ.get('HTTPS_PROXY'),heartbeat=20,timeout=10)as ws:
     output.put(dict(type='WS_CONNECTED',url=URL,received_us=n.nowus()))
     while not stop.is_set():
      try:m=await asyncio.wait_for(ws.receive(),timeout=1.)
      except asyncio.TimeoutError:continue
      received=n.nowus()
      if m.type!=aiohttp.WSMsgType.TEXT:
       if m.type in(aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED,aiohttp.WSMsgType.ERROR):raise OSError('public raw stream disconnected')
       continue
      payload=json.loads(m.data);d=payload.get('data',{});assert d.get('e')=='trade'and d['s']in('BTCUSDT','ETHUSDT'),'raw trade stream required; aggTrade forbidden'
      assert type(d['t'])is int and type(d['T'])is int
      output.put(dict(type='TRADES',asset=d['s'][:-4],endpoint='WS_RAW_TRADE',url=URL,received_us=received,SHA256=hashlib.sha256(m.data.encode()).hexdigest(),raw_UTF8=m.data,data=[dict(id=d['t'],time=d['T'],price=d['p'],qty=d['q'],isBuyerMaker=d['m'])]))
  except Exception as e:
   output.put(dict(type='WS_DISCONNECTED',received_us=n.nowus(),error=repr(e),url=URL));await asyncio.sleep(1.)
def warm(sg,tape,reuse):
 if reuse and Path(reuse).exists():
  parent=Path(reuse);Tape(parent.parent);source_SHA=hashlib.file_digest(parent.open('rb'),'sha256').hexdigest()
  with gzip.open(parent,'rt')as f:
   for line in f:
    if'"type":"PREWARM"'not in line and'"type":"KLINES"'not in line:continue
    row=json.loads(line);q=row['event']
    if q['type']not in('PREWARM','KLINES'):continue
    sg.add(q['asset'],q['data'],q['received_us']);q=dict(q,type='PREWARM',reused_from=str(parent),reused_source_SHA256=source_SHA);tape.write(q)
 else:sg.warm(tape.write)
def collect(manifest_path,seconds,reuse):
 manifest=json.loads(Path(manifest_path).read_text())
 for file,sha in manifest['code_SHA256'].items():assert hashlib.sha256((n.R/file).read_bytes()).hexdigest()==sha,('Frozen code changed',file)
 folder=O/'forward'/manifest['run_id'];folder.mkdir(parents=True,exist_ok=True);tape=Tape(folder);q=queue.Queue();pending={};lastfetch={};start=n.nowus();deadline=start+int(seconds*1e6);state=folder/'checkpoint.pkl';sg=n.Signals(manifest['T0_ms'],folder);stop=threading.Event()
 if state.exists():
  with state.open('rb')as f:engine=pickle.load(f)
  assert engine.manifest==manifest;tape.system('RECONNECT',last_verified_us=engine.last_clock);warm(sg,tape,reuse)
  if n.nowus()>=manifest['T0_ms']*1000:engine.last_seen=n.nowus();engine.halt('OFFLINE_GAP_REQUIRES_REPLAY',gap_start_us=max(engine.last_clock,manifest['T0_ms']*1000),gap_end_us=n.nowus())
 else:
  assert n.nowus()<manifest['T0_ms']*1000,'Cannot rename a late start as forward'
  tape.system('COLLECTOR_STARTED',adapter='WS_RAW_V2',no_real_orders=True);clock=n.fetch('time');tape.write(dict(type='CLOCK_CHECK',**clock));assert abs(clock['received_us']//1000-clock['data']['serverTime'])<2000
  warm(sg,tape,reuse);engine=n.Engine(manifest,sg.calculate())
  if n.nowus()>=manifest['T0_ms']*1000:engine.last_seen=n.nowus();engine.halt('PREWARM_COMPLETED_AFTER_T0')
 thread=threading.Thread(target=lambda:asyncio.run(socket_reader(q,stop)),daemon=True);thread.start()
 def request(a,kind):
  try:
   if kind=='KLINES':v=n.fetch('klines',symbol=a+'USDT',interval='15m',limit=3)
   elif kind=='PREMIUM':v=n.fetch('premiumIndex',symbol=a+'USDT')
   else:v=n.fetch('fundingRate',symbol=a+'USDT',startTime=manifest['T0_ms'],limit=1000)
   q.put(dict(type=kind,asset=a,**v))
  except Exception as e:q.put(dict(type='NETWORK_ERROR',asset=a,kind=kind,error=repr(e),received_us=n.nowus()))
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
  saved=0
  while n.nowus()<deadline and not(folder/'STOP_REQUESTED').exists():
   if shutil.disk_usage(folder).free<268435456:tape.system('STOP_DISK_LOW');break
   now=n.nowus()
   for a in ['BTC','ETH']:
    for kind,interval in [('KLINES',4.),('PREMIUM',30.),('FUNDING',30.)]:
     key=(a,kind)
     if(key not in pending or pending[key].done())and now-lastfetch.get(key,0)>=interval*1e6:pending[key]=pool.submit(request,a,kind);lastfetch[key]=now
   rows=[]
   while not q.empty():rows.append(q.get())
   for v in sorted(rows,key=lambda x:x['received_us']):
    v['available_to_sim_us']=n.nowus();tape.write(v)
    try:
     if v['type']in('NETWORK_ERROR','WS_DISCONNECTED','WS_CONNECTED'):
      engine.event(v['type'],**{k:w for k,w in v.items()if k!='type'})
      if v['type']=='WS_DISCONNECTED'and v['received_us']>=manifest['T0_ms']*1000:engine.last_seen=v['received_us'];engine.halt('WS_GAP_REQUIRES_LABELLED_REPLAY',error=v['error'])
     elif v['type']=='KLINES':
      before=max(sg.bars[v['asset']]);sg.add(v['asset'],v['data'],v['received_us'])
      if max(sg.bars[v['asset']])>before:
       legs=sg.calculate();ready=n.nowus();tape.write(dict(type='SIGNALS_READY',received_us=ready,source_record_SHA256=n.digest(v)));engine.last_seen=ready;engine.advance(ready);engine.update_signals(legs,ready)
     else:engine.consume(v)
    except Exception as e:engine.last_seen=v['received_us'];engine.halt('PROCESSING_ERROR',error=repr(e));tape.system('PROCESSING_ERROR',error=repr(e),traceback=traceback.format_exc())
   now=n.nowus()
   if now>=manifest['T0_ms']*1000:
    for a in ['BTC','ETH']:
     if a not in engine.funding_due:engine.last_seen=now;engine.halt('FUNDING_SCHEDULE_UNAVAILABLE',asset=a)
     last=engine.latest.get(a,{}).get('received_us',start)
     if now-last>3000000 and not engine.halts:engine.last_seen=now;engine.halt('STALE_RAW_FEED',asset=a,last_receive_us=last)
    tape.write(dict(type='ACTOR_CLOCK',received_us=now));engine.advance(now)
   if now-saved>1000000:engine.save(folder);saved=now
   time.sleep(.04)
  stop.set();thread.join(timeout=3);tape.system('OBSERVATION_STOPPED',reason='bounded observation/operator stop; no residency guarantee');engine.save(folder)
 print((folder/'status.json').read_text())
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--manifest',default=str(O/'FREEZE_WS_V2.json'));p.add_argument('--seconds',type=int,default=300);p.add_argument('--reuse-tape',default=str(O/'forward/freeze_1794697200000/events.jsonl.gz'));a=p.parse_args();collect(a.manifest,a.seconds,a.reuse_tape)
