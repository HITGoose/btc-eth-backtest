"""2025-only conditional data experiment, frozen financial engine and explicit checkpoints."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
import argparse,json,hashlib,gzip,pickle,copy,traceback,sys
import numpy as np
import bridge as b
import adapter as a
import observer as o
OUT=b.OUT;GROUPS=list(b.z.GROUPS);COSTS=b.z.COSTS

def runtime_fingerprint():
 return hashlib.sha256(b''.join((OUT/name).read_bytes()for name in ['bridge.py','adapter.py','observer.py','run.py','whitelist_manifest.json'])+b.PARENT_FP.encode()).hexdigest()
def validate_checkpoint(saved,source_fp,data_fp,start,end,keys):
 assert saved['runtime_fingerprint']==source_fp and saved['data_fingerprint']==data_fp
 assert saved['start']==start and saved['end']==end and saved['keys']==keys
 assert start<=saved['next_time']<=end and(saved['next_time']-start)%60==0

def immutable_book(book):
 return o.canonical(dict(asset=book.asset,fee=book.fee,profile=book.profile,sizing=book.sizing,exit_policy=book.exit_policy,priority=book.priority,core_SHA256=o.digest(book.core)))

def cp_load(path):
 with gzip.open(path,'rb')as f:return pickle.load(f)
def save_checkpoint(path,books,marks,**metadata):
 for book in books.values():book.leg=None
 try:
  with gzip.open(path.with_suffix('.tmp'),'wb',compresslevel=1)as f:pickle.dump(dict(books=books,marks=marks,**metadata),f,protocol=5)
  path.with_suffix('.tmp').replace(path)
 finally:
  for book in books.values():book.leg=CONTEXT['leg']

def cash_check(book):
 pos=book.position;part=getattr(pos,'partial_net',0.)if pos else 0.;entryfee=book.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.
 assert abs(book.cash-500-sum(x['net']for x in book.journal)-part+entryfee)<1e-7
 assert abs(book.cash-500-sum(x['delta']for x in book.cash_events))<1e-7
 fills=book.stats['long']+book.stats['short'];assert fills==len(book.journal)+bool(pos)
 assert book.stats['submitted']==fills+book.stats['expired']+book.stats['priority_cancelled']+bool(book.order)
 book.invariant()

def segment(name,start,end,books,signals,scenarios,cache,views,poll_seeds=None,final=False):
 folder=OUT/'segments'/name;folder.mkdir(parents=True,exist_ok=True);cp=folder/'checkpoint.pkl.gz';fingerprint=runtime_fingerprint();resume=start;previous={k:np.array([],dtype=float)for k in books};access={};poll_seeds={}if poll_seeds is None else poll_seeds
 if cp.exists():
  saved=cp_load(cp);validate_checkpoint(saved,fingerprint,CONTEXT['data_fingerprint'],start,end,list(books))
  assert saved['immutable_books']=={k:immutable_book(v)for k,v in books.items()}
  for key,book in saved['books'].items():assert immutable_book(book)==saved['immutable_books'][key];cash_check(book)
  books=saved['books'];previous=saved['marks'];resume=saved['next_time'];poll_seeds=saved['last_polls'];access=saved['access']
  for book in books.values():book.leg=CONTEXT['leg']
  print('RESUME',name,b.r.local_s(resume),flush=True)
 if resume==end:return dict(books=books,marks=previous,last_polls=poll_seeds,access=access)
 markets={};gens={};result={}
 for key,book in books.items():
  market=a.Market(CONTEXT['native'],a.ScenarioCache(cache,views,scenarios[key]),book,True);market.last_poll=copy.deepcopy(poll_seeds.get(key));markets[key]=market
  if key in access:market.mark_access_days=set(access[key]['marks']);market.event_access_days=set(access[key]['events'])
  gens[key]=b.pe.generator(book)('ETH',leg=CONTEXT['leg'],signals=signals[key],market=market,start=resume*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
 print('SEGMENT',name,b.r.local_s(resume),b.r.local_s(end),'books',len(books),flush=True)
 for minute in range(resume,end,60):
  for key,g in gens.items():b.r.model.FEE=books[key].fee;assert next(g)==minute
  boundary=(minute+60)%86400==0 or minute+60==end
  if boundary:
   marks={k:np.r_[previous[k],np.asarray(g.gi_frame.f_locals['marks'])]for k,g in gens.items()};last={k:markets[k].last_poll for k in books};access={k:dict(marks=sorted(markets[k].mark_access_days),events=sorted(markets[k].event_access_days))for k in books}
   for book in books.values():cash_check(book)
   save_checkpoint(cp,books,marks,runtime_fingerprint=fingerprint,start=start,end=end,keys=list(books),next_time=minute+60,last_polls=last,access=access,data_fingerprint=CONTEXT['data_fingerprint'],immutable_books={k:immutable_book(v)for k,v in books.items()})
   b.dump(folder/'progress.json',dict(next_time=b.r.local_s(minute+60),books=len(books),cash={k:v.cash for k,v in books.items()},strict_raw_days=len(cache.sources)))
   print('PROGRESS',name,b.r.local_s(minute+60),len(cache.sources),flush=True)
 # At an intermediate minute boundary, iterator-local temporaries are reset by
 # the next original loop iteration. Do not execute the terminal mark getter:
 # it is reporting-only, and would misleadingly load the bad day for flat B.
 marks={k:np.r_[previous[k],np.asarray(g.gi_frame.f_locals['marks'])]for k,g in gens.items()}
 if final:
  for key,g in gens.items():
   b.r.model.FEE=books[key].fee
   try:next(g);raise RuntimeError('annual calendar overshot')
   except StopIteration as stop:assert not stop.value['approximated_minutes']
 else:
  for g in gens.values():g.close() # preserves every position/order; never liquidates
 last={k:markets[k].last_poll for k in books};access={k:dict(marks=sorted(markets[k].mark_access_days),events=sorted(markets[k].event_access_days))for k in books}
 return dict(books=books,marks=marks,last_polls=last,access=access)

def migrate_group(group,info,fees):
 folder=b.PARENT/'runs/2025/ETH'/group;source=folder/'checkpoint.pkl.gz';saved=cp_load(source)
 assert saved['code_fingerprint']==b.PARENT_FP and saved['groups']==[group]
 assert saved['next_time']==AUG1,'Unexpected parent cutoff; must reassess migration'
 provenance=json.loads((folder/'input_provenance.json').read_text());assert provenance['derived_SHA256']==CONTEXT['native_hashes']
 parent_signals=json.loads((folder/'signals.json').read_text());assert {int(k):v for k,v in parent_signals['core'].items()}==info['core']and{int(k):v for k,v in parent_signals['wide'].items()}==info['wide']
 books={};marks={};checks=[]
 for cost,fee in fees.items():
  key=cost+'_'+group;book=saved['books'][key]
  assert book.leg is None and book.asset=='ETH'and book.fee==fee and book.core==info['core']and book.priority==b.z.GROUPS[group]['priority']
  assert book.sizing==b.r.model.Sizing(3.,.0001,False)and book.exit_policy==b.r.ENTRY.exit_policy and book.profile=='DYNAMIC'
  assert len(saved['marks'][key])==(AUG1-info['start'])//60
  cash_check(book);o.instrument(book,WINDOW);book.leg=info['leg'];books[key]=book;marks[key]=saved['marks'][key]
  checks.append(dict(key=key,cash=book.cash,source_future_state_SHA256=o.digest(o.full_state(book)),prefix_marks_SHA256=hashlib.sha256(marks[key].tobytes()).hexdigest(),native_and_complete_signals_exact=True,fee_sizing_exit_profile_exact=True))
 manifest=dict(group=group,parent_commit=b.BASE_COMMIT,source_checkpoint=str(source),source_checkpoint_SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),source_financial_fingerprint=saved['code_fingerprint'],new_runtime_fingerprint=runtime_fingerprint(),compatibility='All original financial Python hashes match; adapter delegates unchanged strict cache before anomaly UTC day; independent books and prefix ledgers/marks migrated with exact native/signal/fee/schema/cash validation. Not a fingerprint bypass.',cutoff=b.r.local_s(AUG1),checks=checks)
 b.dump(OUT/f'compatibility_{group}.json',manifest);return books,marks

def prepare_context():
 global CONTEXT,AUG1,WINDOW
 info=b.z.prepare('2025','ETH');btc=b.z.prepare('2025','BTC');AUG1=int(datetime(2025,8,1,tzinfo=b.r.TZ).timestamp())
 audit=json.loads((OUT/'whitelist_manifest.json').read_text());WINDOW=(audit['fork_second']*1000000,audit['merge_second']*1000000)
 b.d.BASE='https://data.binance.vision/data/futures/um';b.d.DATA=info['data'];b.d.START=info['start'];b.d.END=info['end'];b.d.FIRST1=info['first']
 native=b.p.Canonical('ETH');hashes={name:hashlib.sha256((info['data']/name).read_bytes()).hexdigest()for name in['ETH_15m.csv','ETH_1m.npy']}
 CONTEXT=dict(info,btc=btc,native=native,native_hashes=hashes)
 signals={};classified=[]
 for group in GROUPS:
  signals[group],rows=b.z.classify(info['core'],info['wide'],btc['core'],group);classified.extend(dict(group=group,**x)for x in rows if info['start']*1000<=x['signal_close_ms']<info['end']*1000)
 b.csv_dump(OUT/'signal_classification.csv.gz',classified);b.dump(OUT/'signals.json',dict(core=info['core'],wide=info['wide'],BTC=btc['core'],accepted=signals))
 assert COSTS=={'ZERO':0.,'ASSUMED_005_SIDE':.0005}
 assert info['start']==int(datetime(2025,1,1,tzinfo=b.r.TZ).timestamp())and info['end']==int(datetime(2026,1,1,tzinfo=b.r.TZ).timestamp())
 assert btc['start']==info['start']and btc['end']==info['end']
 old_ETH=json.loads((b.PARENT/'runs/2025/ETH/B/input_provenance.json').read_text());assert old_ETH['derived_SHA256']==hashes
 btc_hashes={name:hashlib.sha256((btc['data']/name).read_bytes()).hexdigest()for name in['BTC_15m.csv','BTC_1m.npy']}
 assert btc_hashes==json.loads((b.PARENT/'runs/2025/BTC/B/input_provenance.json').read_text())['derived_SHA256']
 CONTEXT['data_fingerprint']=o.digest(dict(ETH_native=hashes,BTC_native=btc_hashes,ETH_core=o.digest(info['core']),ETH_wide=o.digest(info['wide']),BTC_complete=o.digest(btc['core']),accepted={k:o.digest(v)for k,v in signals.items()},policy=asdict(info['policy']),ER=info['pair'],fees=COSTS,groups=b.z.GROUPS))
 views=a.Views();views.equivalence_proof();folder=OUT/'strict_prices';folder.mkdir(exist_ok=True);cache=b.e.RawCache('ETH',native,folder)
 if(folder/'raw_sources.json').exists():cache.sources=json.loads((folder/'raw_sources.json').read_text())
 if(folder/'candle_tick_disagreements.json').exists():cache.disagreements=json.loads((folder/'candle_tick_disagreements.json').read_text())
 b.dump(OUT/'configuration.json',dict(source_commit=b.BASE_COMMIT,branch='codex/eth-2025-anomaly-sensitivity-20261114',runtime_fingerprint=runtime_fingerprint(),original_financial_fingerprint=b.PARENT_FP,groups=b.z.GROUPS,fees=COSTS,source='BINANCE_USDT_PERPETUAL_ONLY',period=[b.r.local_s(info['start']),b.r.local_s(info['end'])],initial_each_asset=500,leverage=3,slippage=.0002,poll_seconds=5,poll_phase=2,funding='NOT_INCLUDED',scenarios=b.SCENARIOS,bit_meaning='IDs ascending6299136398/399/400: 0 retains earlier record,1 later; never select best outcome',native_hashes=hashes,policy=asdict(info['policy']),ER=info['pair'],old_seven_intervals_untouched=True))
 return info,signals,views,cache

def run():
 assert json.loads((OUT/'parent_tests.json').read_text())['passed']
 assert json.loads((OUT/'tests.json').read_text())['passed']
 info,maps,views,cache=prepare_context();start=info['start'];end=info['end'];first=views.manifest['fork_second'];merge=views.manifest['merge_second']
 bootstrap={cost+'_B':o.instrument(b.pe.book('ETH',fee,info['leg'],info['core'],False),WINDOW)for cost,fee in COSTS.items()}
 initial=segment('B_Jan_to_Aug',start,AUG1,bootstrap,{k:maps['B']for k in bootstrap},{k:'S_ALL'for k in bootstrap},cache,views)
 books=dict(initial['books']);year_prefix=dict(initial['marks']);polls=dict(initial['last_polls'])
 for group in GROUPS:
  if group=='B':continue
  migrated,marks=migrate_group(group,info,COSTS);books.update(migrated);year_prefix.update(marks);polls.update({k:None for k in migrated})
 common=segment('common_Aug_to_fork',AUG1,first,books,{k:maps[k.rsplit('_',1)[-1]]for k in books},{k:'S_ALL'for k in books},cache,views,poll_seeds=polls)
 common_year={k:np.r_[year_prefix[k],common['marks'][k]]for k in books}
 fork_books={};fork_polls={};fork_signals={};fork_scenarios={}
 for scenario in b.SCENARIOS:
  for key,book in common['books'].items():
   ident=scenario+'|'+key;fork_books[ident]=o.clone(book,info['leg']);fork_polls[ident]=copy.deepcopy(common['last_polls'][key]);fork_signals[ident]=maps[key.rsplit('_',1)[-1]];fork_scenarios[ident]=scenario
 forks=segment('nine_scenario_window',first,merge,fork_books,fork_signals,fork_scenarios,cache,views,poll_seeds=fork_polls)
 own_prefix={};membership={};representatives={};signatures={};pool_records=[];trace_folder=OUT/'anomaly_traces';trace_folder.mkdir(exist_ok=True)
 for ident,book in forks['books'].items():
  scenario,key=ident.split('|');group=key.rsplit('_',1)[-1];own_prefix[ident]=np.r_[common_year[key],forks['marks'][ident]]
  values=dict(book=o.full_state(book),latest_poll=forks['last_polls'][ident],latest_real_quote_before_merge=views.latest(scenario,merge-0.000001),immutable_signal_SHA256=o.digest(maps[group]),runtime_fingerprint=runtime_fingerprint())
  data=o.encoded(values);candidate=(key,hashlib.sha256(data).hexdigest())
  if candidate in signatures:
   pool,expected=signatures[candidate];assert data==expected,'Never pool on hash alone'
  else:
   pool=key+'__P'+str(len(representatives));signatures[candidate]=(pool,data);representatives[pool]=ident
  membership[ident]=pool
  prefix=own_prefix[ident];peaks=np.maximum.accumulate(np.r_[500.,prefix]);dd=float(np.max(100*(1-np.r_[500.,prefix]/peaks)))
  record=dict(scenario=scenario,key=key,pool=pool,full_book_SHA256=o.digest(values['book']),complete_future_state_SHA256=hashlib.sha256(data).hexdigest(),prefix_marks_SHA256=hashlib.sha256(prefix.tobytes()).hexdigest(),prefix_peak=float(peaks[-1]),prefix_max_drawdown_pct=dd,prefix_end_equity=float(prefix[-1]),cash=book.cash,latest_poll=values['latest_poll'],latest_real_quote=values['latest_real_quote_before_merge'],pool_condition='exact complete original book including all journal/event/cash history plus polling state; equity prefixes may differ and remain separate')
  pool_records.append(record)
  with gzip.open(trace_folder/(scenario+'_'+key+'.json.gz'),'wt',encoding='utf-8')as f:json.dump(book._sensitivity_trace,f,ensure_ascii=False)
 b.dump(OUT/'pooling.json',dict(merge_time=b.r.local_s(merge),groups_before=len(fork_books),groups_after=len(representatives),membership=membership,representatives=representatives,records=pool_records,original_history_never_replaced=True,equity_prefixes_saved_separately=True))
 suffix_books={pool:forks['books'][ident]for pool,ident in representatives.items()};suffix_signals={pool:maps[ident.split('|')[1].rsplit('_',1)[-1]]for pool,ident in representatives.items()};suffix_scenarios={pool:ident.split('|')[0]for pool,ident in representatives.items()};suffix_polls={pool:forks['last_polls'][ident]for pool,ident in representatives.items()}
 suffix=segment('year_end_suffix',merge,end,suffix_books,suffix_signals,suffix_scenarios,cache,views,poll_seeds=suffix_polls,final=True)
 for ident,pool in membership.items():
  scenario,key=ident.split('|');book=suffix['books'][pool];b.r.model.FEE=book.fee;cash_check(book);market=a.Market(CONTEXT['native'],a.ScenarioCache(cache,views,scenario),book,True);mark=market[end-60][3];pos=book.position
  part=getattr(pos,'partial_net',0.)if pos else 0.;entryfee=book.fee*pos.order.price*getattr(pos,'initial_quantity',pos.order.qty)if pos else 0.;state=b.p.state(book)
  if pos:state['position']['order'].update(signal_close_ms=book.order_info['signal_close_ms'],origin=book.order_info['origin'])
  if book.order:state['pending_order'].update(signal_close_ms=book.order_info['signal_close_ms'],origin=book.order_info['origin'])
  q=dict(asset='ETH',period='2025',scenario=scenario,key=key,status='COMPLETED_WITH_DATA_ANOMALY',window=[b.r.local_s(start),b.r.local_s(end)],fee=book.fee,starting_equity=500.,ending_equity=book.equity(mark),cash=book.cash,trades=book.journal,events=book.events,place_attempts=book.place_attempts,cash_events=book.cash_events,stats=dict(book.stats),opens=book.stats['long']+book.stats['short'],state_at_end=state,actual_raw_last_mark=mark,open_contribution=book.equity(mark)-book.cash+part-entryfee,no_OHLC_fallback=True,source='BINANCE_USDT_PERPETUAL_ONLY_CONDITIONAL_ANOMALY_VIEW',replacement_at_end=book.replacement,pool=pool,trace_file=str((trace_folder/(scenario+'_'+key+'.json.gz')).relative_to(OUT)),view=views.get(scenario)['metadata'])
  if pos:q['open_partial_state']={k:getattr(pos,k,None)for k in('initial_quantity','partial_net','partial_fills','partial_queue','partial_stage')}
  marks=np.r_[own_prefix[ident],suffix['marks'][pool]];assert len(marks)==(end-start)//60 and abs(marks[-1]-q['ending_equity'])<1e-7
  assert abs(q['ending_equity']-500-sum(t['net']for t in q['trades'])-q['open_contribution'])<1e-7
  if key.endswith('_B'):
   old=json.loads((b.PARENT/'runs/2025/ETH/B'/f'{key}_result.json').read_text());assert abs(q['cash']-old['cash'])<1e-7 and abs(q['ending_equity']-old['ending_equity'])<1e-7
   assert len(q['trades'])==len(old['trades'])
   for new,ref in zip(q['trades'],old['trades']):
    for field in ref:assert new[field]==ref[field],('B regression',scenario,key,field)
   assert np.array_equal(marks,np.load(b.PARENT/'runs/2025/ETH/B'/f'{key}_equity.npy'))
   q['B_old_complete_trades_cash_equity_and_minute_marks_exact']=True
  folder=OUT/'results'/scenario;folder.mkdir(parents=True,exist_ok=True);b.dump(folder/f'{key}_result.json',q);np.save(folder/f'{key}_equity.npy',marks)
  accesses=dict(bootstrap_B=initial['access'].get(key)if key.endswith('_B')else None,common=common['access'][key],scenario_window=forks['access'][ident],suffix=suffix['access'][pool]);b.dump(folder/f'{key}_access.json',accesses)
  print('RESULT',scenario,key,q['ending_equity'],flush=True)
 b.dump(OUT/'status.json',dict(completed=True,status='COMPLETED_WITH_DATA_ANOMALY',runtime_fingerprint=runtime_fingerprint(),scenarios=b.SCENARIOS,keys=list(common['books']),total_ETH_results=len(membership),original_strict_2025_DGHI='UNVERIFIED',old_other_years_untouched=True))

CONTEXT={};AUG1=None;WINDOW=None
if __name__=='__main__':
 try:run()
 except Exception as error:b.dump(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),runtime_fingerprint=runtime_fingerprint()));raise
