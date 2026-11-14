from pathlib import Path
import sys,inspect,argparse,traceback,json
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/er_partial_variants_2020'))
import run_variants as v
e=v.e;p=v.p;r=v.r;d=v.d;OUT=Path(__file__).resolve().parent
class Dynamic(v.VariantSleeve):
 def update_ladder(self,price):
  p.AuditSleeve.update_ladder(self,price)
  pos=self.position
  if pos and pos.partial_stage==0 and pos.order.side*(price/pos.order.price-1)*100>=1-1e-10:
   pos.partial_stage=1;pos.partial_queue.append(1)
   self.events.append(dict(event='partial_exit_requested',stage=1,time_us=round(self.audit_timestamp*1e6),last_price=float(price)))
 def visit(self,*args,**kw):
  n=len(self.events);super().visit(*args,**kw)
  for event in self.events[n:]:
   if event.get('event')=='partial_exit' and event.get('stage')==2:
    event['trigger_gain_pct']=None;event['trigger_reason']='first15m six-MA or MACD weakening after first partial fill'
def reachable(b,*args):
 if b.profile=='DYNAMIC' and b.position and b.position.partial_stage>=1:return False
 return v.reachable(b,*args)
def check_trend(b,t):
 pos=b.position
 if b.profile!='DYNAMIC' or pos is None or getattr(pos,'partial_stage',0)!=1 or not getattr(pos,'partial_fills',[]):return
 if t%900:return
 i=(t*1000-b.leg.first)//900000-1
 assert 0<=i<len(b.leg.histogram)
 aligned=b.leg.up[i]==6 if pos.order.side==1 else b.leg.down[i]==6
 macd=pos.order.side*b.leg.histogram[i]>0
 if not (aligned and macd):
  pos.partial_stage=2;pos.partial_queue.append(2)
  b.events.append(dict(event='dynamic_exit_requested',stage=2,time_us=t*1000000,
    closed_bar_end_us=t*1000000,all_six_same_direction=bool(aligned),MACD_same_direction=bool(macd)))
source=inspect.getsource(e.generator)
source=source.replace('    source=inspect.getsource(r.seconds.replay_asset)','    source=inspect.getsource(r.seconds.replay_asset)\n    source=source.replace("        expire(book, t)\\n", "        expire(book, t)\\n        check_trend(book, t)\\n")')
source=source.replace('or original_can_move(b,*args)','or reachable(b,*args) or original_can_move(b,*args)')
source=source.replace('namespace.update(Sleeve=', 'namespace.update(check_trend=check_trend,Sleeve=')
ns=dict(e.__dict__);ns.update(reachable=reachable,check_trend=check_trend);exec(compile(source,'<original executor, closed15m dynamic exit hook>','exec'),ns);generator=ns['generator']
def run(year,asset):
 folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True);p.OUT=folder;d.TEMP=folder/'temporary';d.TEMP.mkdir(exist_ok=True)
 if year==2020:
  d.START=v.driver.START;d.END=v.driver.END;d.FIRST15=d.START-45*86400;d.FIRST1=d.START-86400;d.DATA=v.driver.OUT/'data'
 # 2026 uses original d module defaults in separate process.
 start,end=d.START,d.END;leg,signals,ctx,base,policy,pair=p.prepare(asset,d.DATA/f'{asset}_15m.csv',start,end)
 native=p.Canonical(asset);cache=p.DayCache(asset,native);market=p.ActualMarket(native,cache)
 profiles=['DYNAMIC'] if year==2020 else ['DYNAMIC','EARLY_2'];books={}
 for name in profiles:
  if name=='EARLY_2':b=v.book(asset,name)
  else:
   b=Dynamic(asset,r.ENTRY.exit_policy,cash=500.,sizing=r.model.Sizing(3.,.0001,False),journal=[])
   b.tranches=[(1.,.25),(0.,.25)];b.events=[];b.audit_timestamp=None;b.observing_event=False;b.profile=name;b.boundary_probes=[]
  b.leg=leg;books[name]=b
 gens={name:generator(b)(asset,leg=leg,signals=signals['ER'],market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False) for name,b in books.items()}
 d.dump(folder/'config.json',dict(year=year,start=r.local_s(start),end=r.local_s(end),entry='original old sixMA+ER BASELINE unchanged',dynamic='1pct fixed25pct of initial; after fill, first closed15m failure of all-six3bar slopes or MACD sign exits another25pct; remainder original trailing stop',fee=0,leverage=3,slippage=.0002,SR_absolute_distance_pct=2,first_exit_next_actual_print=True,stop_priority=True,original_files_unchanged=True,full_year=False))
 for t in range(start,end,60):
  for g in gens.values():assert next(g)==t
  if t%86400==0:d.dump(folder/'progress.json',dict(time=r.local_s(t)))
 for name,g in gens.items():
  try:next(g);raise RuntimeError('Overshot')
  except StopIteration as stop:q=stop.value
  assert not q['approximated_minutes'];b=books[name];mark=float(market.market[end-60][3]);realized=sum(x['net'] for x in b.journal)+(getattr(b.position,'partial_net',0.) if b.position else 0.)
  assert abs(b.cash-500-realized)<1e-7
  for row in b.journal:assert abs(sum(x['quantity'] for x in row['partial_fills'])+row['final_exit_quantity']-row['quantity'])<1e-8
  result=dict(asset=asset,profile=name,year=year,period=[r.local_s(start),r.local_s(end)],ending_equity=b.equity(mark),return_pct=100*(b.equity(mark)/500-1),opens=q['opens'],trades=b.journal,events=b.events,stats=dict(b.stats),state_at_end=p.state(b),no_OHLC_fallback=True)
  d.dump(folder/f'{name}_result.json',result);np.save(folder/f'{name}_equity.npy',q['marks']);print(year,asset,name,'COMPLETE',result['return_pct'],flush=True)
 d.dump(folder/'status.json',dict(completed=True))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int,choices=[2020,2026]);a.add_argument('asset',choices=['BTC','ETH']);args=a.parse_args()
 try:run(args.year,args.asset)
 except Exception as error:d.dump(OUT/f'{args.year}_{args.asset}_failure.json',dict(error=repr(error),traceback=traceback.format_exc()));raise
