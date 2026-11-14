"""Capture public unaggregated REST trades and run receipt-causal simulation.
No service daemon guarantee; resume never silently fills an offline gap.
"""
from pathlib import Path
import sys,json,time,hashlib,pickle,queue,threading,concurrent.futures,traceback,gzip,shutil
import online as n
O=n.O
class Tape:
 def __init__(self,folder):
  self.folder=folder;folder.mkdir(exist_ok=True);self.seq=0;self.prev='0'*64;self.path=folder/'events.jsonl.gz'
  if self.path.exists():
   with gzip.open(self.path,'rt')as f:
    for line in f:
     r=json.loads(line);assert r['previous_SHA256']==self.prev and n.digest(r['event'])==r['body_SHA256'];assert n.digest({k:v for k,v in r.items()if k!='chain_SHA256'})==r['chain_SHA256'];self.seq=r['sequence'];self.prev=r['chain_SHA256']
 def write(self,q):
  row=dict(sequence=self.seq+1,previous_SHA256=self.prev,body_SHA256=n.digest(q),event=q);row['chain_SHA256']=n.digest(row)
  with gzip.open(self.path,'at',compresslevel=3)as f:f.write(json.dumps(row,separators=(',',':'))+'\n');f.flush()
  self.seq+=1;self.prev=row['chain_SHA256']
 def system(self,kind,**kw):self.write(dict(type=kind,received_us=n.nowus(),**kw))
def collect(manifest_path,seconds):
 manifest=json.loads(Path(manifest_path).read_text());expected=manifest['code_SHA256']
 for file,sha in expected.items():assert hashlib.sha256((n.R/file).read_bytes()).hexdigest()==sha,('Frozen code changed',file)
 folder=O/'forward'/manifest['run_id'];tape=Tape(folder);q=queue.Queue();pending={};lastfetch={};start=n.nowus();deadline=start+int(seconds*1e6);state=folder/'checkpoint.pkl';signals=n.Signals(manifest['T0_ms'],folder)
 if state.exists():
  with state.open('rb')as f:engine=pickle.load(f)
  assert engine.manifest==manifest
  tape.system('RECONNECT',last_verified_us=engine.last_clock)
  if n.nowus()>=manifest['T0_ms']*1000:engine.last_seen=n.nowus();engine.halt('OFFLINE_GAP_REQUIRES_REPLAY',gap_start_us=max(engine.last_clock,manifest['T0_ms']*1000),gap_end_us=n.nowus())
  # Resume stored indicator input; replayable raw tape remains untouched.
  for a in ['BTC','ETH']:
   f=folder/(a+'_closed.csv')
   if f.exists():
    import csv
    for b in list(csv.DictReader(f.open())):
     t=int(b['timestamp']);signals.bars[a][t]=[t,b['open'],b['high'],b['low'],b['close'],b['volume'],t+899999]
 else:
  assert n.nowus()<manifest['T0_ms']*1000,'Fresh forward launch after T0 forbidden; use labelled replay or a new freeze'
  tape.system('COLLECTOR_STARTED',no_real_orders=True);clock=n.fetch('time');tape.write(dict(type='CLOCK_CHECK',**clock));assert abs(clock['received_us']//1000-clock['data']['serverTime'])<2000,'Clock skew exceeds2 seconds';signals.warm(tape.write);legs=signals.calculate();engine=n.Engine(manifest,legs)
  if n.nowus()>=manifest['T0_ms']*1000:engine.last_seen=n.nowus();engine.halt('PREWARM_COMPLETED_AFTER_T0')
 def request(a,kind):
  try:
   if kind=='TRADES':m=n.fetch('trades',symbol=a+'USDT',limit=1000)
   elif kind=='KLINES':m=n.fetch('klines',symbol=a+'USDT',interval='15m',limit=3)
   elif kind=='PREMIUM':m=n.fetch('premiumIndex',symbol=a+'USDT')
   else:m=n.fetch('fundingRate',symbol=a+'USDT',startTime=manifest['T0_ms'],limit=1000)
   q.put(dict(type=kind,asset=a,**m))
  except Exception as e:q.put(dict(type='NETWORK_ERROR',asset=a,kind=kind,error=repr(e),received_us=n.nowus()))
 with concurrent.futures.ThreadPoolExecutor(max_workers=6)as pool:
  saved=0
  while n.nowus()<deadline and not(folder/'STOP_REQUESTED').exists():
   if shutil.disk_usage(folder).free<268435456:tape.system('STOP_DISK_LOW');break
   now=n.nowus()
   for a in ['BTC','ETH']:
    for kind,interval in [('TRADES',1.),('KLINES',4.),('PREMIUM',30.),('FUNDING',30.)]:
     key=(a,kind)
     if(key not in pending or pending[key].done())and now-lastfetch.get(key,0)>=interval*1e6:pending[key]=pool.submit(request,a,kind);lastfetch[key]=now
   events=[]
   while not q.empty():events.append(q.get())
   for e in sorted(events,key=lambda x:x['received_us']):
    e['available_to_sim_us']=n.nowus();tape.write(e)
    try:
     if e['type']=='NETWORK_ERROR':engine.event('CONNECTION_ERROR',**{k:v for k,v in e.items()if k!='type'})
     elif e['type']=='KLINES':
      before=max(signals.bars[e['asset']]);signals.add(e['asset'],e['data'],e['received_us'])
      if max(signals.bars[e['asset']])>before:
       legs=signals.calculate();ready=n.nowus();tape.write(dict(type='SIGNALS_READY',received_us=ready,source_record_SHA256=n.digest(e)));engine.last_seen=ready;engine.advance(ready);engine.update_signals(legs,ready)
     else:engine.consume(e)
    except Exception as error:engine.last_seen=e['received_us'];engine.halt('PROCESSING_ERROR',error=repr(error));tape.system('PROCESSING_ERROR',error=repr(error),traceback=traceback.format_exc())
   now=n.nowus()
   if now>=manifest['T0_ms']*1000:
    for a in ['BTC','ETH']:
     if a not in engine.funding_due:engine.last_seen=now;engine.halt('FUNDING_SCHEDULE_UNAVAILABLE',asset=a)
     last=engine.latest.get(a,{}).get('received_us',start)
     if now-last>3000000 and not engine.halts:engine.last_seen=now;engine.halt('STALE_RAW_FEED',asset=a,last_receive_us=last)
    tape.write(dict(type='ACTOR_CLOCK',received_us=now));engine.advance(now)
   if now-saved>1000000:engine.save(folder);saved=now
   time.sleep(.04)
  tape.system('OBSERVATION_STOPPED',reason='requested bounded observation complete; no promise of residency');engine.save(folder)
 print(json.dumps(json.loads((folder/'status.json').read_text()),indent=2))
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--manifest',default=str(O/'FREEZE.json'));p.add_argument('--seconds',type=int,default=300);a=p.parse_args();collect(a.manifest,a.seconds)
if __name__=='__main__':main()
