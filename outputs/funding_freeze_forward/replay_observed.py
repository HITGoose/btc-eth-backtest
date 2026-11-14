"""Deterministic replay of recorded receipt/actor clocks, never called live observation."""
from pathlib import Path
import sys,json,gzip,pickle
import online as n
from live import Tape

def main(folder):
 folder=Path(folder);manifest=json.loads((n.O/'FREEZE.json').read_text());Tape(folder) # full chain verification
 out=folder.parent/(folder.name+'_observed_replay');out.mkdir(exist_ok=True);sg=n.Signals(manifest['T0_ms'],out);engine=None
 with gzip.open(folder/'events.jsonl.gz','rt')as f:
  for line in f:
   q=json.loads(line)['event'];typ=q['type']
   if typ=='PREWARM':sg.add(q['asset'],q['data'],q['received_us']);continue
   if typ in('TRADES','PREMIUM','FUNDING','KLINES','ACTOR_CLOCK','SIGNALS_READY')and engine is None:engine=n.Engine(manifest,sg.calculate())
   if engine is None:continue
   if typ=='KLINES':sg.add(q['asset'],q['data'],q['received_us'])
   elif typ=='SIGNALS_READY':engine.last_seen=q['received_us'];engine.advance(q['received_us']);engine.update_signals(sg.calculate(),q['received_us'])
   elif typ in('TRADES','PREMIUM','FUNDING'):engine.consume(q)
   elif typ=='ACTOR_CLOCK':engine.advance(q['received_us'])
   elif typ=='RECONNECT'and q['received_us']>=manifest['T0_ms']*1000:engine.last_seen=q['received_us'];engine.halt('OFFLINE_GAP_REQUIRES_REPLAY',gap_start_us=max(engine.last_clock,manifest['T0_ms']*1000),gap_end_us=q['received_us'])
   elif typ=='PROCESSING_ERROR':engine.halt('PROCESSING_ERROR',error=q['error'])
 assert engine is not None;engine.save(out)
 with(folder/'checkpoint.pkl').open('rb')as f:actual=pickle.load(f)
 checks=[]
 for key,x in engine.books.items():
  y=actual.books[key];assert x.cash==y.cash and x.journal==y.journal and x.events==y.events and n.s.b.p.state(x)==n.s.b.p.state(y),('replay mismatch',key);checks.append('/'.join(key))
 q=dict(label='REPLAYED_AFTER_GAP',meaning='post-hoc replay of captured tape, not additional realtime sample; unresolved external gaps remain unresolved',cash_trades_events_positions_exact=True,accounts=checks,last_clock_exact=engine.last_clock==actual.last_clock,original_forward_not_overwritten=True)
 (out/'replay_validation.json').write_text(json.dumps(q,indent=2));print(json.dumps(q))
if __name__=='__main__':main(sys.argv[1])
