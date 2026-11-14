from pathlib import Path
import sys,inspect,json,argparse,traceback
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_partial_2020'))
import run_2020 as driver
e=driver.e;p=e.p;r=e.r;d=e.d
OUT=Path(__file__).resolve().parent
PROFILES={'EARLY_2':[(1.,.25),(2.,.25)],'THREE_3':[(2.,.25),(3.,.25),(4.,.25)],'LATE_2':[(3.,.25),(5.,.25)]}
source=inspect.getsource(e.PartialSleeve).replace('class PartialSleeve','class VariantSleeve')
source=source.replace('initial_lots//3','floor(initial_lots*self.tranches[stage-1][1]+1e-12)')
source=source.replace('trigger_gain_pct=stage+1','trigger_gain_pct=self.tranches[stage-1][0]')
source=source.replace('for stage,threshold in ((1,2.),(2,3.)):','for stage,(threshold,fraction) in enumerate(self.tranches,1):')
namespace=dict(e.__dict__);exec(compile(source,'<fixed variant tranche engine>','exec'),namespace);VariantSleeve=namespace['VariantSleeve']
def reachable(b,high,low,previous):
 pos=b.position
 if not pos or pos.partial_stage>=len(b.tranches):return False
 best=max(high,previous) if pos.order.side==1 else min(low,previous)
 gain=pos.order.side*(best/pos.order.price-1)*100
 return gain>=b.tranches[pos.partial_stage][0]-1e-10
source=inspect.getsource(e.generator).replace('or original_can_move(b,*args)','or reachable(b,*args) or original_can_move(b,*args)')
namespace=dict(e.__dict__);namespace['reachable']=reachable;exec(compile(source,'<same executor, wake for requested partial thresholds>','exec'),namespace);generator=namespace['generator']
def book(asset,name):
 b=VariantSleeve(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
 b.tranches=PROFILES[name];b.events=[];b.audit_timestamp=None;b.observing_event=False;b.profile=name;b.boundary_probes=[]
 return b

def run(asset):
 folder=OUT/asset;folder.mkdir(parents=True,exist_ok=True);p.OUT=folder;d.TEMP=folder/'temporary';d.TEMP.mkdir(exist_ok=True)
 d.START=driver.START;d.END=driver.END;d.FIRST15=d.START-45*86400;d.FIRST1=d.START-86400;d.DATA=driver.OUT/'data'
 leg,signals,contexts,base,policy,pair=p.prepare(asset,d.DATA/f'{asset}_15m.csv',d.START,d.END)
 native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
 books={name:book(asset,name) for name in PROFILES}
 gens={name:generator(b)(asset,leg=leg,signals=signals['ER'],market=market,start=d.START*1000,end=d.END*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False) for name,b in books.items()}
 d.dump(folder/'config.json',dict(profiles=PROFILES,start=r.local_s(d.START),end=r.local_s(d.END),full_year=False,fee=0,leverage=3,slippage=.0002,SR_absolute_distance_pct=2,entry='unchanged original ER BASELINE',original_files_unchanged=True,parameter_search='only three prespecified variants, no adaptive search'))
 for t in range(d.START,d.END,60):
  for g in gens.values():assert next(g)==t
  if t%86400==0:d.dump(folder/'progress.json',dict(time=r.local_s(t)))
 for name,g in gens.items():
  try:next(g);raise RuntimeError('Overshot end')
  except StopIteration as stop:q=stop.value
  assert not q['approximated_minutes'];b=books[name];mark=float(market.market[d.END-60][3])
  realized=sum(v['net'] for v in b.journal)+(getattr(b.position,'partial_net',0.) if b.position else 0.)
  assert abs(b.cash-500-realized)<1e-7
  for row in b.journal:
   assert abs(sum(f['quantity'] for f in row['partial_fills'])+row['final_exit_quantity']-row['quantity'])<1e-8
  result=dict(asset=asset,profile=name,tranches=PROFILES[name],starting_equity=500,ending_equity=b.equity(mark),return_pct=100*(b.equity(mark)/500-1),opens=q['opens'],trades=b.journal,events=b.events,stats=dict(b.stats),state_at_end=p.state(b),no_OHLC_fallback=True)
  d.dump(folder/f'{name}_result.json',result);np.save(folder/f'{name}_equity.npy',q['marks']);print(asset,name,'COMPLETE',result['return_pct'],flush=True)
 d.dump(folder/'status.json',dict(completed=True))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('asset',choices=['BTC','ETH']);args=a.parse_args()
 try:run(args.asset)
 except Exception as error:d.dump(OUT/f'{args.asset}_failure.json',dict(error=repr(error),traceback=traceback.format_exc()));raise
