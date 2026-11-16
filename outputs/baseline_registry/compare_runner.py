"""Only recover the original MA-direction rule on the frozen ER_V2 raw engine."""
from pathlib import Path
import sys,json,hashlib,inspect,os,shutil,traceback,fcntl,datetime
from urllib.request import Request,urlopen
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'outputs/extra_sizing_cost_stress'));import replay as w
s=w.s;np=w.np;pe=s.pe
source=inspect.getsource(pe.Book);assert source.count('class Book(w.Dynamic):')==1
namespace=dict(pe.__dict__);exec(compile(source.replace('class Book(w.Dynamic):','class MAControl(w.Control):'),'<same request/observer methods; original non-V2 CONTROL>', 'exec'),namespace)
MAControl=namespace['MAControl'];MAControl.__module__=__name__
def fp():return hashlib.sha256(Path(__file__).read_bytes()+s.fp().encode()+(R/'outputs/attribution_2026/paired_replay.py').read_bytes()+(R/'outputs/retry_nov9_nov12/replay_comparison.py').read_bytes()).hexdigest()
def dump(p,v):s.dump(p,v)
ORIGINAL_ACQUIRE=s.b.d.acquire
INVENTORY={p.name:p for p in R.glob('outputs/**/temporary/*-trades-*.zip')}
def acquire(url,path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with(O/'download.lock').open('w')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  cached=INVENTORY.get(path.name)
  if not path.exists()and cached and cached.exists():os.link(cached,path)
  with urlopen(Request(url,method='HEAD'),timeout=30)as response:
   size=int(response.headers.get('Content-Length')or 0);status=response.status
  free=shutil.disk_usage(O).free;need=max(0,size-(path.stat().st_size if path.exists()else 0))+32*1024*1024
  with(O/'data_queries.jsonl').open('a')as f:f.write(json.dumps(dict(at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),url=url,status=status,content_length=size,free_disk_bytes=free,need_with_checkpoint_margin=need,reused_cache=bool(cached and cached.exists())))+'\n')
  if not size:raise RuntimeError('UNVERIFIED_ARCHIVE_SIZE: '+url)
  if free<need:raise RuntimeError('INSUFFICIENT_DISK_FOR_RAW_ARCHIVE: '+json.dumps(dict(url=url,archive_bytes=size,free_bytes=free,required_bytes=need)))
  return ORIGINAL_ACQUIRE(url,path)
s.b.d.acquire=acquire

def run(period,asset):
 f=O/'runs'/period/asset;f.mkdir(parents=True,exist_ok=True);done=f/'status.json'
 if done.exists():assert json.loads(done.read_text())['code_fingerprint']==fp();return
 info=s.z.prepare(period,asset);data=info['data'];start,end=info['start'],info['end'];first=info['first']
 leg,maps,ctx,base,policy,pair=s.b.p.prepare(asset,data/f'{asset}_15m.csv',start,end)
 core={t:v for t,v in info['core'].items()if start*1000<=t<end*1000};assert core=={t:v for t,v in maps['ER'].items()if start*1000<=t<end*1000}
 ma={t:v for t,v in maps['MA'].items()if start*1000<=t<end*1000};prior=json.loads((R/f'outputs/rebound_annual_zero/runs/{period}/{asset}/signals.json').read_text());assert core=={int(k):v for k,v in prior['core'].items()}
 hashes={n:hashlib.file_digest((data/n).open('rb'),'sha256').hexdigest()for n in [asset+'_15m.csv',asset+'_1m.npy']};refcfg=json.loads((R/f'outputs/rebound_annual_zero/runs/{period}/{asset}/config.json').read_text());assert hashes==refcfg['data_SHA256']
 dump(f/'signals.json',dict(ER_V2_REFERENCE=core,MA_DIRECTION_REFERENCE=ma));dump(f/'config.json',dict(code_fingerprint=fp(),source='BINANCE_USDT_PERPETUAL',data=str(data),data_SHA256=hashes,start=start,end=end,minute_first=first,initial_cash=500,fee=0,funding=0,slippage=.0002,leverage=3,exit_policy='uncapped',V2=False,rule='existing p.prepare MA -> existing r.ma_schedules; unchanged original six SMA/EMA20/60/120',scenario='S_ALL'if period=='2025'and asset=='ETH'else'STRICT'))
 d=s.b.d;d.BASE='https://data.binance.vision/data/futures/um';d.DATA=data;d.START=start;d.END=end;d.FIRST1=first;native=s.b.p.Canonical(asset)
 x=w.E.book(asset,0.,.0002,leg,ma,False,1.,'F_TOUCH');x.__class__=MAControl;x.profile='CONTROL';assert isinstance(x,s.z.w.Control)and not isinstance(x,s.z.w.Dynamic);assert x.exit_policy=='uncapped'
 cache=w.raw_cache(asset,native,f);scene='STRICT'
 if period=='2025'and asset=='ETH':
  views=s.a.Views();cache=s.a.ScenarioCache(cache,views,'S_ALL');scene='S_ALL';dump(f/'S_ALL_evidence.json',dict(status='COMPLETED_WITH_DATA_ANOMALY',metadata=views.get('S_ALL')['metadata']))
 context=dict(info,asset=asset,period=period,leg=leg,native=native,fingerprint=s.o.digest(dict(code=fp(),data=hashes,signals=ma)))
 print('START',period,asset,'MA_DIRECTION_REFERENCE','signals',len(ma),flush=True)
 books,marks=w.segment(f/'whole',context,start,end,{'MA_DIRECTION_REFERENCE':x},{'MA_DIRECTION_REFERENCE':ma},{'MA_DIRECTION_REFERENCE':scene},cache,None,True)
 x=books['MA_DIRECTION_REFERENCE'];last=w.E.Market(native,cache,x,True)[end-60][3];cfg=dict(key='MA_DIRECTION_REFERENCE',cost='ZERO_FUNDING_ZERO',group='MA_DIRECTION_REFERENCE',fill='F_TOUCH',fee=0.,slip=.0002,funding=False)
 w.output(context,f/'results',scene,cfg,x,marks['MA_DIRECTION_REFERENCE'],last,'experiment');assert not any(e['event'].startswith('partial_')for e in x.events)
 dump(done,dict(complete=True,code_fingerprint=fp(),status='COMPLETED_WITH_DATA_ANOMALY'if scene=='S_ALL'else'COMPLETE'));print('COMPLETE',period,asset,x.equity(last),len(x.journal),flush=True)
if __name__=='__main__':
 p,a=sys.argv[1:3]
 try:run(p,a)
 except Exception as ex:
  f=O/'runs'/p/a;f.mkdir(parents=True,exist_ok=True);dump(f/'failure.json',dict(error=repr(ex),traceback=traceback.format_exc(),code_fingerprint=fp()));raise
