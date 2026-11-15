"""Exact receipt-clock replay of a SEALED capture; does not fill absent market prices."""
from pathlib import Path
import json,gzip,pickle,hashlib,sys
import online as n
from live import Tape

def main(folder):
 folder=Path(folder).resolve()
 with(folder/'checkpoint.pkl').open('rb')as f:actual=pickle.load(f)
 manifest=actual.manifest
 for file,sha in manifest['code_SHA256'].items():assert hashlib.sha256((n.R/file).read_bytes()).hexdigest()==sha,'Use the matching frozen code commit; never bypass fingerprints'
 Tape(folder);out=folder.parent/(folder.name+'_receipt_replay');out.mkdir(exist_ok=True);sg=n.Signals(manifest['T0_ms'],out);engine=None;start=None;lasttype=None
 with gzip.open(folder/'events.jsonl.gz','rt')as f:
  for line in f:
   q=json.loads(line)['event'];typ=q['type'];lasttype=typ
   if typ=='COLLECTOR_STARTED':start=q['received_us']
   if typ=='PREWARM':sg.add(q['asset'],q['data'],q['received_us']);continue
   if typ in('WS_CONNECTED','TRADES','PREMIUM','FUNDING','KLINES','ACTOR_CLOCK','SIGNALS_READY')and engine is None:engine=n.Engine(manifest,sg.calculate())
   if engine is None:continue
   try:
    if typ in('NETWORK_ERROR','WS_DISCONNECTED','WS_CONNECTED'):
     engine.event(typ,**{k:v for k,v in q.items()if k!='type'})
     if typ=='WS_DISCONNECTED'and q['received_us']>=manifest['T0_ms']*1000:engine.last_seen=q['received_us'];engine.halt('WS_GAP_REQUIRES_LABELLED_REPLAY',error=q['error'])
    elif typ=='KLINES':sg.add(q['asset'],q['data'],q['received_us'],confirmed_closed=bool(q.get('confirmed_exchange_closed')))
    elif typ=='SIGNALS_READY':engine.last_seen=q['received_us'];engine.advance(q['received_us']);engine.update_signals(sg.calculate(),q['received_us'])
    elif typ in('TRADES','PREMIUM','FUNDING'):engine.consume(q)
    elif typ=='ACTOR_CLOCK':
     now=q['received_us']
     for a in ['BTC','ETH']:
      if a not in engine.funding_due:engine.last_seen=now;engine.halt('FUNDING_SCHEDULE_UNAVAILABLE',asset=a)
      last=engine.latest.get(a,{}).get('received_us',start)
      if now-last>3000000 and not engine.halts:engine.last_seen=now;engine.halt('STALE_RAW_FEED',asset=a,last_receive_us=last)
     engine.advance(now)
   except Exception as e:engine.last_seen=q['received_us'];engine.halt('PROCESSING_ERROR',error=repr(e))
 assert lasttype=='OBSERVATION_STOPPED','Only replay a sealed capture; do not race an active writer'
 assert engine is not None;checks=[]
 for key,x in engine.books.items():
  y=actual.books[key];assert n.s.o.encoded(n.s.o.full_state(x))==n.s.o.encoded(n.s.o.full_state(y)),('full financial state mismatch',key);checks.append('/'.join(key))
 for field in ['last_clock','last_seen','lastid','pending','seen_signals','halts','funding_due','known_funding','marks','events','raw_count','raw_records']:
  assert getattr(engine,field)==getattr(actual,field),('driver-state mismatch',field)
 engine.save(out);result=dict(passed=True,accounts=len(checks),complete_book_state_and_driver_state_exact=True,label='REPLAY_OF_OBSERVED_TAPE_NOT_ADDITIONAL_FORWARD_SAMPLE',unresolved_gaps_not_filled=True,source_financial_halted=bool(actual.halts),original_forward_not_overwritten=True)
 (out/'replay_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main(sys.argv[1])
