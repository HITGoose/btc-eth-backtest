"""Exact quantity-only replay on prior official-print event paths.

This is NOT a new download/full tick traversal. Prices and signal/exit paths are
reused only after the original25% books are reproduced and path invariants hold.
"""
from pathlib import Path
from datetime import datetime
import sys,json,csv,math,traceback
import numpy as np
ROOT=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(ROOT/'outputs/binance_perpetual_raw_execution'))
import engine as e
x=e.x;p=e.p;r=e.r;OUT=Path(__file__).resolve().parent


def paths(year):
 if year==2020:return ROOT/'outputs/er_dynamic_compare/2020',ROOT/'outputs/er_partial_2020/data'
 if year in (2021,2022,2023):return ROOT/f'outputs/er_dynamic_annual_2019_2026/{year}',ROOT/f'outputs/other_years_050/{year}/data'
 if year in (2024,2025):return ROOT/f'outputs/binance_perpetual_raw_execution/{year}',ROOT/f'outputs/other_years_050/{year}/data'
 return ROOT/'outputs/er_dynamic_compare/2026',ROOT/'outputs/attribution_2026/data'

def period(q):return q.get('period',q.get('period_beijing'))

def snapshot(book):
 pos=book.position
 return dict(cash=book.cash,quantity=pos.order.qty if pos else 0.,entry=pos.order.price if pos else None,side=pos.order.side if pos else None)

def drive(book,event,fraction):
 kind=event['event'];us=int(event['time_us']);stamp=us/1e6;book.audit_timestamp=stamp;book.observing_event=True
 r.seconds.expire(book,stamp)
 if kind=='order_sent':
  assert book.position is None and book.order is None, 'Accepted order occupancy changed: full tick replay required'
  side=event['side'];price=event['price'];ref=price/(1-side*.002)
  book.audit_timestamp=event.get('effective_submission_us',us)/1e6
  book.place(us//1000,ref,side,nearest_tick=True)
  if book.order is None:raise RuntimeError('New quantity rejected a formerly accepted entry: full tick replay required')
  assert book.order.price==price
 elif kind=='limit_touch_proxy_fill':
  if book.order:
   book.visit(event['price'],round(stamp*1000),True,advance_ladder=False)
  else:
   # Original observer logs immediate gap stops before its fill observation.
   assert book.journal and book.journal[-1]['opened_us']==us and book.journal[-1]['closed_us']==us, 'Unexpected unmatched fill event'
 elif kind in ('hard_stop','ladder_exit'):
  if book.position or book.order:book.visit(event['price'],round(stamp*1000),True,advance_ladder=False)
  assert book.position is None and book.journal[-1]['closed_us']==us and book.journal[-1]['reason']==kind
 elif kind=='poll_moves_stop':
  assert book.position
  book.update_ladder(event['price'])
  assert book.position.rung==event['rung'] and book.position.stop==event['stop'], 'Price-dependent stop path changed'
 elif kind=='partial_exit_requested':
  assert event['stage']==1 and book.position
  book.update_ladder(event.get('last_price',event.get('price')))
  assert book.position.partial_stage>=1
 elif kind=='dynamic_exit_requested':
  assert book.position
  eligible=book.position.partial_stage==1 and bool(book.position.partial_fills)
  x.check_trend(book,int(stamp))
  if eligible:assert book.position.partial_stage==2 and 2 in book.position.partial_queue, 'Closed15m confirmation changed'
 elif kind=='partial_exit':
  assert book.position
  if book.position.partial_queue:
   book.visit(event['trigger_print'],round(stamp*1000),True,advance_ladder=False)
  else:
   assert fraction<.25 and event['stage']==2 and not book.position.partial_fills, 'Unexpected missing partial request'
 elif kind=='partial_skipped_quantity_step':
  assert book.position and book.position.partial_queue
  step=book.sizing.btc_step if book.asset=='BTC' else r.model.RULES[book.asset][0]
  stage=event['stage'];assert math.floor(round(book.position.initial_quantity/step)*book.tranches[stage-1][1]+1e-12)==0
  book.position.partial_queue=[]
 else:raise RuntimeError('Unknown source financial event '+kind)

def assert_same(a,b):
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:assert_same(a[k],b[k])
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):assert_same(x,y)
 elif isinstance(a,float):assert abs(a-b)<1e-7
 else:assert a==b

def run(year,asset):
 src,data=paths(year);folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True)
 q=json.loads((src/asset/'DYNAMIC_result.json').read_text());oldmarks=np.load(src/asset/'DYNAMIC_equity.npy');start,end=[int(datetime.fromisoformat(s).timestamp()) for s in period(q)]
 assert q['no_OHLC_fallback'] and q['stats'].get('fees',0)==0 and q['stats'].get('rejected',0)==0
 assert len(oldmarks)==(end-start)//60
 leg=r.model.build(data/f'{asset}_15m.csv',(start-30*86400)*1000,end*1000)
 old=e.new_book(asset,'DYNAMIC',leg);new=e.new_book(asset,'DYNAMIC',leg);new.tranches=[(1.,.10),(0.,.25)]
 states={0:(snapshot(old),snapshot(new))};last=-1;events=q['events']
 for event in events:
  idx=(int(event['time_us'])//1000000-start)//60
  assert 0<=idx<len(oldmarks) and idx>=last, 'Non-monotonic source event minutes; full replay required'
  drive(old,event,.25);drive(new,event,.10);last=idx
  a,b=snapshot(old),snapshot(new)
  assert (a['quantity']>0)==(b['quantity']>0) and a['entry']==b['entry'] and a['side']==b['side'], 'Position path changed'
  states[idx]=(a,b)
 r.seconds.expire(old,end);r.seconds.expire(new,end)
 keys=('opened_us','closed_us','side','entry','exit','net','rung','quantity','final_exit_quantity','partial_net')
 assert len(old.journal)==len(q['trades'])
 for actual,expected in zip(old.journal,q['trades']):
  for k in keys:
   if isinstance(expected[k],(float,int)):assert abs(actual[k]-expected[k])<1e-7,(year,asset,k,actual[k],expected[k])
   else:assert actual[k]==expected[k]
  assert len(actual['partial_fills'])==len(expected['partial_fills'])
  for a,b in zip(actual['partial_fills'],expected['partial_fills']):
   for k in ('stage','time_us','quantity','execution_price','net_usdt'):assert abs(a[k]-b[k])<1e-7
 assert_same(p.state(old),q['state_at_end'])
 if old.position:
  opened=q['state_at_end']['position_opened_us']
  fills=[v for v in q['events'] if v['event']=='partial_exit' and v['time_us']>=opened]
  assert_same(old.position.partial_fills,fills)
  assert abs(old.position.partial_net-sum(v['net_usdt'] for v in fills))<1e-7
  opening=next(v for v in q['events'] if v['event']=='limit_touch_proxy_fill' and v['time_us']==opened)
  assert abs(old.position.initial_quantity-opening['quantity'])<1e-8
 assert bool(old.position)==bool(q['state_at_end']['position']) and bool(old.order)==bool(q['state_at_end']['pending_order'])
 assert bool(new.position)==bool(old.position) and bool(new.order)==bool(old.order)
 for field in ('long','short','submitted','expired'):assert old.stats[field]==q['stats'].get(field,0) and new.stats[field]==old.stats[field]
 newmarks=np.empty_like(oldmarks);indices=sorted(states)
 for j,i in enumerate(indices):
  stop=indices[j+1] if j+1<len(indices) else len(oldmarks);a,b=states[i];v=oldmarks[i:stop]
  if a['quantity']:
   implied_price=a['entry']+a['side']*(v-a['cash'])/a['quantity'];assert np.isfinite(implied_price).all() and (implied_price>0).all()
   newmarks[i:stop]=b['cash']+(b['quantity']/a['quantity'])*(v-a['cash'])
  else:
   assert np.allclose(v,a['cash'],rtol=0,atol=1e-7), 'Source minute-mark alignment invalid'
   newmarks[i:stop]=b['cash']
 assert np.isfinite(newmarks).all()
 equity=float(newmarks[-1]);result=dict(year=year,asset=asset,profile='DYNAMIC10',market='BINANCE_USDT_PERPETUAL_ONLY',period=period(q),starting_equity=500.,ending_equity=equity,return_pct=100*(equity/500-1),opens=new.stats['long']+new.stats['short'],trades=new.journal,events=new.events,stats=dict(new.stats),state_at_end=p.state(new),first_fraction=.10,second_fraction=.25,first_price_trigger_pct=1.,entry_exit_price_path_unchanged=True,old25_regression_passed=True,new_entry_acceptance_unchanged=True,source_result=str(src/asset/'DYNAMIC_result.json'),method='quantity-only replay of validated official-print financial events; original minute marks reused via exact cash/remaining-quantity relation; not a new full tick traversal',no_OHLC_extreme_assumption=True)
 if new.position:result['open_partial_state']={k:getattr(new.position,k) for k in ('initial_quantity','partial_net','partial_fills','partial_queue','partial_stage')}
 (folder/'DYNAMIC10_result.json').write_text(json.dumps(result,ensure_ascii=False)+'\n');np.save(folder/'DYNAMIC10_equity.npy',newmarks)
 (folder/'validation.json').write_text(json.dumps(dict(old25_regression_passed=True,full_end_state_regression_passed=True,open_partial_state_regression_passed=True,effective_submission_time_preserved=True,matched_closed=len(old.journal),entry_order_acceptance_unchanged=True,entry_exit_path_unchanged=True,mark_relation_verified=True,source=str(src),period=period(q)),ensure_ascii=False,indent=2))
 print(year,asset,'COMPLETE',result['return_pct'],flush=True)

if __name__=='__main__':
 failures=[]
 for year in range(2020,2027):
  for asset in ('BTC','ETH'):
   try:run(year,asset)
   except Exception as error:
    folder=OUT/str(year)/asset;folder.mkdir(parents=True,exist_ok=True);item=dict(year=year,asset=asset,error=repr(error),traceback=traceback.format_exc());(folder/'failure.json').write_text(json.dumps(item,ensure_ascii=False,indent=2));failures.append(item);print('FAILED',year,asset,repr(error),flush=True)
 print('FINISHED failures',len(failures),flush=True)
