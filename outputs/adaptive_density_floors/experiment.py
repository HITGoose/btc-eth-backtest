from pathlib import Path
import sys,inspect,json,hashlib,datetime,re,html,csv,ast
from zoneinfo import ZoneInfo
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;BASE=R/'outputs/adaptive_density_control'
sys.path.insert(0,str(BASE));import worker as w
sig=w.sig;s=w.s;E=w.E;np=w.np
GROUPS=['A','B','D','E1','E2_030','E2_035','E3_030','E3_035']
def dump(p,x):s.dump(p,x)
def calendar():
 D=R/'outputs/macro_event_attribution';out=[];excluded=[]
 for x in json.loads((D/'release_sources.json').read_text()):
  if x['kind']not in ['CPI','FOMC']:continue
  raw_bytes=(D/x['stored']).read_bytes()
  try:raw=raw_bytes.decode('utf-8-sig')
  except UnicodeDecodeError:raw=raw_bytes.decode('cp1252')
  text=re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',raw)))
  if x['kind']=='FOMC':
   valid=bool(re.search(r'For release at 2:00 p\.m\.',text,re.I)) and 'funds rate' in text.lower()
   clock='14:00'
  else:
   valid=bool(re.search(r'8:30\s*a\.?m',text,re.I)) and 'embargoed' in text.lower();clock='08:30'
  if not valid:excluded.append(dict(**x,exclusion='NOT_REQUESTED_RELEASE_TIME_OR_NOT_RATE_DECISION'));continue
  t=datetime.datetime.fromisoformat(x['date']+'T'+clock).replace(tzinfo=ZoneInfo('America/New_York'));ms=int(t.timestamp()*1000)
  out.append(dict(kind=x['kind'],date=x['date'],release_ET=t.isoformat(),release_UTC=t.astimezone(datetime.timezone.utc).isoformat(),release_ms=ms,url=x['url'],raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),stored=x['stored']))
 dump(O/'calendar.json',dict(events=sorted(out,key=lambda x:x['release_ms']),excluded=excluded,timezone='America/New_York',window='inclusive signal_close_ms in [T,T+3600000]',selection_bias='Post-hoc chosen window; not new out of sample'))
 return out
EXTRA={'E1':dict(family='E',parameters=[.25,.50],cap=None),'E2_030':dict(family='E',parameters=[.25,.50],cap=.30),'E2_035':dict(family='E',parameters=[.25,.50],cap=.35)}
source=inspect.getsource(sig.make)
source=source.replace("elif family=='B':", "elif family in ['B','E']:")
needle='  hist=np.isfinite(metric)'
assert source.count(needle)==1
source=source.replace(needle,"  if family=='E':\n   ht=np.maximum(ht,.25)\n   if spec['cap']is not None:ht=np.minimum(ht,spec['cap'])\n"+needle)
ns=dict(sig.__dict__);ns['SPECS']=dict(sig.SPECS,**EXTRA);exec(compile(source,'<isolated E squeeze threshold variants>','exec'),ns);make=ns['make']
def signals(asset,data,start,end,events):
 q=make(asset,data,start,end,['A','B25','E1','E2_030','E2_035']);m=q['maps'];maps={'A':m['A'],'B':m['B25'],'D':sig.mix(m['A'],m['B25']),**{k:m[k]for k in EXTRA}}
 def cooled(t):return any(x['release_ms']<=t<=x['release_ms']+3600000 for x in events)
 for cap in ['030','035']:maps['E3_'+cap]={t:v for t,v in maps['E2_'+cap].items()if not cooled(t)}
 return q,maps
class Native:
 def __init__(self,asset,data,first,end):
  self.rows=np.load(data/f'{asset}_1m.npy',mmap_mode='r');self.first=first;self.end=end;self.market=self
 def __getitem__(self,minute):
  i=(minute-self.first)//60
  if not(0<=i<len(self.rows)):raise RuntimeError('Missing cached minute '+str(minute))
  return self.rows[i]
class Cache:
 def __init__(self,n):self.native=n;self.cache={};self.sources={}
 def load(self,minute):
  day=minute//86400*86400
  if day not in self.cache:
   n=self.native;lo=max(day,n.first);hi=min(day+86400,n.end);minutes=np.arange(lo,hi,60,dtype=np.int64);ix=(minutes-n.first)//60;b=n.rows[ix];times=(minutes[:,None]+np.array([0.,20.,40.,59.])).reshape(-1);prices=b[:,[0,1,2,3]].reshape(-1)
   # Synthetic OHLC minute prints, not observed trade timestamps or 5-second prices.
   self.cache={day:np.column_stack([times,np.arange(len(times)),prices])}
  return self.cache[day]
def fingerprint():return hashlib.sha256(Path(__file__).read_bytes()+(O/'EXPERIMENT.md').read_bytes()+(BASE/'FREEZE.json').read_bytes()).hexdigest()
def run(period,asset):
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True);fp=fingerprint()
 if(folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fingerprint']==fp;return
 _,data,start,end,first,sources=s.z.inputs(period,asset);events=json.loads((O/'calendar.json').read_text())['events'];q,maps=signals(asset,data,start,end,events);leg=q['leg'];core=maps['A'];dump(folder/'signals.json',dict(accepted=maps,thresholds=q['thresholds']))
 for name,di in q['diagnostics'].items():s.z.csv_dump(folder/(name+'_conditions.csv'),di)
 # Verify unchanged baseline signals against the actual previously accepted maps.
 stage='train'if period in ['2020','2021','2022']else'final';old=json.loads((BASE/'runs'/stage/period/asset/'signals.json').read_text())['accepted'];oldkey='ZERO_A';assert {int(k):v for k,v in old[oldkey].items()}==maps['A']
 bkey='ZERO_B25'if stage=='train'else'ZERO_B';assert {int(k):v for k,v in old[bkey].items()}==maps['B']
 dump(folder/'signal_check.json',dict(A_original_signals_equal=True,B_original_signals_equal=True,no_V2=True,pause_transition=True,removed_from_A={k:sum(maps[k].get(t)!=v for t,v in core.items())for k in GROUPS},data=[dict(path=str(data/f'{asset}_{suffix}'),sha256=sig.digest_file(data/f'{asset}_{suffix}'))for suffix in ['15m.csv','1m.npy']],execution='SYNTHETIC_1M_OHLC',warning='E1/E2 floor squeeze only; dynamic current range-width can still remove A; no union added'))
 native=Native(asset,data,first,end);cache=Cache(native)
 for label,fee in [('ZERO',0.),('ASSUMED_005_SIDE',.0005)]:
  for group in GROUPS:
   key=label+'_'+group;path=folder/(key+'_result.json')
   if path.exists():assert json.loads(path.read_text())['fingerprint']==fp;continue
   x=E.book(asset,fee,leg,core,group=='D');market=E.Market(native,cache,x,True);E.activate(x);g=E.generator(x)(asset,leg=leg,signals=maps[group],market=market,start=start*1000,end=end*1000,starting_cash=500.,leverage=3.,poll_seconds=5,poll_phase=2,print_progress=False)
   print('START',period,asset,key,flush=True)
   for t in range(start,end,60):assert next(g)==t
   try:next(g);raise RuntimeError('overshot')
   except StopIteration as st:out=st.value
   marks=np.asarray(out['marks']);E.cash_check(x);mark=float(native[end-60][3]);assert abs(marks[-1]-x.equity(mark))<1e-7
   state=s.b.p.state(x)
   if x.position:state['position']['order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   if x.order:state['pending_order'].update(signal_close_ms=x.order_info['signal_close_ms'],origin=x.order_info['origin'])
   result=dict(asset=asset,period=period,key=key,fingerprint=fp,configuration=dict(group=group,fee=fee,funding=0,slip=.0002,V2=False,pause_transition=True),starting_equity=500.,ending_equity=x.equity(mark),cash=x.cash,fee=fee,V2=False,trades=x.journal,events=x.events,sizing_audit=x.sizing_audit,cash_events=x.cash_events,state_at_end=state,mark_price=mark,status='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS',not_observed_tick_path=True,source='BINANCE_USDT_PERPETUAL',window=[start*1000,end*1000],raw_anomaly_2025='NOT_APPLICABLE_KLINE_EXECUTION'if period=='2025'else None)
   dump(path,result);np.savez_compressed(folder/(key+'_equity.npz'),marks=marks);print('COMPLETE',period,asset,key,result['ending_equity'],len(x.journal),flush=True)
 dump(folder/'status.json',dict(fingerprint=fp,complete=True))
if __name__=='__main__':
 if sys.argv[1]=='calendar':calendar()
 else:run(*sys.argv[1:3])
