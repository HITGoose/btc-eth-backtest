"""One year/asset task; all requested independent books share loaded raw tape."""
import common as c
import suite_engine as e
from catalog import SPECS,canonical
import argparse,json,contextlib,traceback,time,shutil
from inputs import prepare
sig=c.module('retest_signals_module',c.HERE/'signals.py')
def run(year,asset,requested,hours=None):
 keys=list(dict.fromkeys(canonical(k,asset)for k in requested));keys=[k for k in keys if hours or not c.existing(k,year,asset)]
 if not keys:return 'REUSED_OR_COMPLETE'
 if any(SPECS[k]['kind']=='import'for k in keys)and year!=2026 and not hours:raise RuntimeError('IMPORT_REQUIRED: completed corrected FAIL_EXIT/VOL_SIZE; do not recalculate')
 freezes={}
 for name in ['fixed_low','adaptive_B','adaptive_C','adaptive_D']:
  p=c.OUT/f'freeze_{name}.json'
  if p.exists():freezes.update(json.loads(p.read_text()))
 for k in keys:
  if k=='FIXED_LOW':assert freezes.get('L_fixed')is not None,'Calibration requires imported training VOL_SIZE'
  if k=='ADAPT_CORE_LIGHT':assert freezes.get('D_source'),'Both B/C training freezes required'
 f=c.OUT/('smoke_tasks'if hours else'tasks')/str(year)/asset/('-'.join(keys));f.mkdir(parents=True,exist_ok=True)
 with(f/'execution.log').open('a',buffering=1)as log,contextlib.redirect_stdout(log):
  data,m=prepare(year,asset);start,end=m['start'],m['end'];leg,core,features,maps,parameters=sig.prepare(asset,data,m,keys,freezes)
  if hours:start=min(core)//1000-900;end=start+int(hours*3600);maps={k:{t:x for t,x in v.items()if start*1000<=t<end*1000}for k,v in maps.items()}
  d=c.s.b.d;d.DATA=data;d.BASE='https://data.binance.vision/data/futures/um';d.START=start;d.END=end;d.FIRST1=m['first1'];native=c.s.b.p.Canonical(asset)
  old_sources=json.loads((c.ROOT/m['reference']/'raw_sources.json').read_text());acquire=c.s.b.d.acquire
  def pinned_acquire(url,path):
   meta=acquire(url,path)
   if '/daily/trades/'in url:
    day=path.stem[-10:];expected=old_sources.get(day)
    if expected:assert meta['sha256']==expected['sha256'],('Official raw archive differs from reused baseline; keep result UNVERIFIED',asset,day)
   return meta
  c.s.b.d.acquire=pinned_acquire
  books={k:e.make(asset,leg,core,features,k,SPECS[k],parameters,freezes)for k in keys};cache=c.w.raw_cache(asset,native,f);scene='STRICT'
  if year==2025 and asset=='ETH':cache=c.s.a.ScenarioCache(cache,c.D.anomaly(),'S_ALL');scene='S_ALL';cache.__class__.sources=property(lambda self:self.strict.sources)
  fp=c.fingerprint();c.s.fp=lambda:fp;c.s.pe.generator=e.generator;c.v.E.cash_check=e.cash_check;c.v.E.Market=c.v.Market
  used_freeze={}
  if 'FIXED_LOW'in keys:used_freeze['L_fixed']=freezes['L_fixed']
  if 'ADAPT_CORE_LIGHT'in keys:used_freeze['D_source']=freezes['D_source']
  ctx=dict(asset=asset,period=str(year),leg=leg,native=native,start=start,end=end,fingerprint=c.s.o.digest(dict(code=fp,inputs=m,maps=maps,config={k:SPECS[k]for k in keys},freeze=used_freeze,start=start,end=end)))
  olddump=c.s.dump
  def saved(p,q):
   olddump(p,q)
   if p.name=='progress.json':c.backup(f)
  c.s.dump=saved
  try:books,marks=c.w.segment(f/'whole',ctx,start,end,books,maps,{k:scene for k in keys},cache,None,True)
  finally:c.s.dump=olddump
  for key,x in books.items():
   dest=c.OUT/'smoke'/key/str(year)/asset if hours else c.folder(key,year,asset);mark=c.v.Market(native,cache,x,True)[end-60][3];cfg=dict(key=key,cost='ZERO_FUNDING_ZERO',group=key,fill='F_TOUCH',fee=0.,slip=.0002,funding=False)
   c.w.output(ctx,dest,scene,cfg,x,marks[key],mark,'experiment');shutil.copy2(dest/(key+'_result.json'),dest/'result.json');shutil.copy2(dest/(key+'_equity.npz'),dest/'equity.npz')
   q=json.loads((dest/'result.json').read_text());c.dump(dest/'signals.json',dict(actual=maps[key],core=core))
   q.update(retest_start=start,retest_end=end,retest_configuration=SPECS[key],retest_fingerprint=fp,signal_count=len(maps[key]));c.dump(dest/'result.json',q);e.cash_check(x)
   c.dump(dest/'config.json',dict(fingerprint=fp,inputs=m,core_count=len(core),signals_count=len(maps[key]),configuration=SPECS[key],freeze=used_freeze,V2=True,fee=0,funding=0,slip=.0002))
   c.dump(dest/'status.json',dict(complete=True,fingerprint=fp,source='NEW_SHORT_ONLY'if hours else'NEW_RAW_REPLAY',result_SHA256=c.digest(dest/'result.json'),equity_SHA256=c.digest(dest/'equity.npz')));c.backup(dest)
 return 'COMPLETE'
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('year',type=int);a.add_argument('asset',choices=['BTC','ETH']);a.add_argument('keys',nargs='+');a.add_argument('--hours',type=float);q=a.parse_args()
 try:print(q.year,q.asset,run(q.year,q.asset,q.keys,q.hours),flush=True)
 except Exception as err:
  f=c.OUT/'errors'/str(q.year)/q.asset;f.mkdir(parents=True,exist_ok=True);c.dump(f/('-'.join(q.keys)+'.json'),dict(error=repr(err),traceback=traceback.format_exc()));c.backup(f);raise
