"""14 isolated year/asset tasks, two books each. No full baseline replay."""
from pathlib import Path
import os,sys,json,hashlib,time,contextlib,shutil,argparse,traceback
import variant_engine as v
import data as D
w=v.w;s=v.s;np=v.np
HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get('BTC_OUTPUT_ROOT',v.ROOT/'colab_results/er_v2_two_variants')).resolve()
VERSIONS=['ER_V2_FAIL_EXIT','ER_V2_VOL_SIZE']
def dump(p,q):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(q,ensure_ascii=False,default=lambda x:x.item(),indent=2))
def fingerprint():return hashlib.sha256(b''.join((HERE/n).read_bytes()for n in ['variant_engine.py','portable.py','data.py','run.py','input_manifest.json'])+v.BASE_FINANCIAL_FP.encode()).hexdigest()
def backup(folder):
 root=os.environ.get('BTC_DRIVE_RESULTS')
 if not root:return
 target=Path(root)/folder.relative_to(OUT);target.mkdir(parents=True,exist_ok=True)
 for p in folder.rglob('*'):
  if not p.is_file()or 'temporary'in p.parts or p.suffix in ['.tmp','.part','.zip']:continue
  dest=target/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists()and dest.stat().st_size==p.stat().st_size and dest.stat().st_mtime>=p.stat().st_mtime:continue
  tmp=dest.with_suffix(dest.suffix+'.copying');shutil.copy2(p,tmp);tmp.replace(dest)

def run(year,asset,hours=None,resume_probe=False):
 start_clock=time.monotonic();cpu_clock=time.process_time();timing={};folder=OUT/('smoke'if hours else'runs')/str(year)/asset;folder.mkdir(parents=True,exist_ok=True);fp=fingerprint()
 if(folder/'status.json').exists()and not resume_probe:assert json.loads((folder/'status.json').read_text())['fingerprint']==fp;return 'SKIPPED'
 with(folder/'execution.log').open('a',buffering=1)as log,contextlib.redirect_stdout(log):
  phase=time.monotonic();data,m=D.native(year,asset);timing['native_cache_or_download_seconds']=time.monotonic()-phase;start,end=m['start'],m['end']
  ref=v.ROOT/m['reference'];frozen=json.loads((ref/'core_signals.json').read_text());frozen={int(k):x for k,x in frozen['core'].items()}
  phase=time.monotonic();leg,maps,contexts,base,policy,pair=s.b.p.prepare(asset,data/f'{asset}_15m.csv',start,end)
  if hours:
   start=min(frozen)//1000-900;end=min(end,start+round(hours*3600))
  core={t:x for t,x in maps['ER'].items()if start*1000<=t<end*1000};expected={t:x for t,x in frozen.items()if start*1000<=t<end*1000};assert core==expected,'original CORE signal mismatch'
  assert policy.pause_transition and s.r.ENTRY.exit_policy=='uncapped'
  features=v.indicators(leg,data/f'{asset}_15m.csv');timing['signals_and_indicators_seconds']=time.monotonic()-phase;d=s.b.d;d.BASE='https://data.binance.vision/data/futures/um';d.DATA=data;d.START=start;d.END=end;d.FIRST1=m['first1'];native=s.b.p.Canonical(asset)
  books={k:v.make(asset,leg,core,features,k)for k in VERSIONS};cache=w.raw_cache(asset,native,folder);scene='STRICT'
  if str(year)=='2025'and asset=='ETH':cache=s.a.ScenarioCache(cache,D.anomaly(),'S_ALL');scene='S_ALL';cache.__class__.sources=property(lambda self:self.strict.sources)
  ctx=dict(asset=asset,period=str(year),leg=leg,native=native,start=start,end=end,fingerprint=s.o.digest(dict(code=fp,inputs=m,core=core,end=end,versions=VERSIONS)))
  s.fp=lambda:fp
  old_dump=s.dump
  def checkpoint_dump(p,q):
   old_dump(p,q)
   if p.name=='progress.json':backup(folder)
  s.dump=checkpoint_dump
  original_market=w.E.Market;w.E.Market=v.Market
  dump(folder/'config.json',dict(fingerprint=fp,input=m,fee=0,funding=0,slippage=.0002,versions=VERSIONS,original_ER_V2_MRO=[c.__name__ for c in v.VariantBook.__mro__],start=start,end=end,signal_count=len(core),signals_exact=True,scenario=scene))
  phase=time.monotonic()
  try:books,marks=w.segment(folder/'whole',ctx,start,end,books,{k:core for k in books},{k:scene for k in books},cache,None,True)
  finally:s.dump=old_dump;w.E.Market=original_market
  timing['raw_replay_wall_seconds']=time.monotonic()-phase
  for k,x in books.items():
   mark=v.Market(native,cache,x,True)[end-60][3];cfg=dict(key=k,cost='ZERO_FUNDING_ZERO',group=k,fill='F_TOUCH',fee=0.,slip=.0002,funding=False)
   w.output(ctx,folder/'results',scene,cfg,x,marks[k],mark,'experiment');v.E.cash_check(x)
  dump(folder/'status.json',dict(complete=True,fingerprint=fp,elapsed_seconds=time.monotonic()-start_clock,cpu_seconds=time.process_time()-cpu_clock,timing=timing,status='COMPLETED_WITH_DATA_ANOMALY'if scene=='S_ALL'else'COMPLETE',scope='SHORT_SANITY_NOT_ANNUAL'if hours else'ANNUAL'))
 backup(folder);return 'COMPLETE'
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year');a.add_argument('asset',choices=['BTC','ETH']);a.add_argument('--hours',type=float);a.add_argument('--resume-probe',action='store_true');args=a.parse_args()
 if args.resume_probe and not args.hours:raise ValueError('resume probe is smoke-only')
 try:print(args.year,args.asset,run(args.year,args.asset,args.hours,args.resume_probe),flush=True)
 except Exception as e:
  folder=OUT/('smoke'if args.hours else'runs')/args.year/args.asset;dump(folder/'failure.json',dict(error=repr(e),traceback=traceback.format_exc()));backup(folder);raise
