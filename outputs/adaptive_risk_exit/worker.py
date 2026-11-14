from pathlib import Path
import sys,inspect,argparse,math,json
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/binance_perpetual_raw_execution'))
import worker as old
import engine as e
OUT=Path(__file__).resolve().parent
class Adaptive(e.x.Dynamic):
 def update_ladder(self,price):e.p.AuditSleeve.update_ladder(self,price)

def check(book,t):
 pos=book.position
 if book.profile!='DYNAMIC' or not pos or t%900:return
 i=(t*1000-book.leg.first)//900000-1
 if i<1:return
 side=pos.order.side
 def weak(j):return not ((book.leg.up[j] if side==1 else book.leg.down[j])==6) and side*book.leg.histogram[j]<=0
 if not (weak(i) and weak(i-1)):return
 # Latest closed15m price is already known at this clock boundary.
 price=book.leg.bars[t*1000-900000].c
 distance=side*(price-pos.stop)
 if distance<=0:return # existing stop gets priority on the next actual print
 step=book.sizing.btc_step if book.asset=='BTC' else e.r.model.RULES[book.asset][0]
 target=math.floor((15./distance+1e-12)/step)*step
 reduction=pos.order.qty-target
 if reduction<step-1e-10 or pos.partial_queue:return
 # Quantity fixed from information available at request; no increase allowed.
 lots=round(reduction/step);initial_lots=round(pos.initial_quantity/step)
 fraction=(lots+.000001)/initial_lots
 book.tranches.append((0.,fraction));stage=len(book.tranches)
 pos.partial_queue.append(stage);pos.partial_stage=stage
 book.events.append(dict(event='adaptive_request',time_us=t*1000000,budget=15.,known_close=price,stop=pos.stop,target_quantity=target,requested_quantity=lots*step))

def newbook(asset,profile,leg):
 if profile=='CONTROL':return original(asset,profile,leg)
 b=Adaptive(asset,e.r.ENTRY.exit_policy,cash=500.,sizing=e.r.model.Sizing(3.,.0001,False),journal=[])
 b.tranches=[];b.events=[];b.audit_timestamp=None;b.observing_event=False;b.profile='DYNAMIC';b.boundary_probes=[];b.leg=leg
 return b
original=e.new_book;e.new_book=newbook;e.x.check_trend=check
# Engine's injected clock hook reads this same module object.
old.OUT=OUT
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int);a.add_argument('asset');q=a.parse_args()
 old.run(q.year,q.asset)
 folder=OUT/str(q.year)/q.asset
 config=json.loads((folder/'config.json').read_text());config['dynamic']='ADAPTIVE_RISK: two closed15m both six-line and MACD failure; fixed15USDT prospective stop giveback budget; no1pct prerequisite';config['risk_budget']=15.;(folder/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
