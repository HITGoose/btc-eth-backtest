"""Original MA_DIRECTION classifier, applied to existing intervention masks."""
import common as c
from pathlib import Path
from types import SimpleNamespace as NS,FunctionType
from dataclasses import replace
import ast,json
s=c.s;np=c.np
adaptive=c.module('ma_original_adaptive',c.HERE/'history/adaptive_density_control/signals.py')
rebound=c.module('ma_original_rebound',c.HERE/'history/rebound_followdown/signals.py')
def ma_schedule(asset,leg,file,entry=None,**kw):
 original=s.r.ma_schedules;entry=entry or adaptive.SETTINGS
 fn=FunctionType(original.__code__,dict(original.__globals__,ENTRY=entry),original.__name__,original.__defaults__,original.__closure__);fn.__kwdefaults__=dict(original.__kwdefaults__ or{})
 return fn(asset,leg,price_file=file,include_gate_confirmation=True,regime_thresholds=adaptive.PAIR,use_entry_crosses=False)
adaptive.schedule=ma_schedule

def threshold(asset,data,start,end,value,leg=None,policy=None,pair=None):
 if leg is None:leg,_,_,_,policy,pair=s.b.p.prepare(asset,data/f'{asset}_15m.csv',start,end)
 value=value if asset=='ETH'else .25;policy=replace(policy,range_squeeze_pct=value);sched,ctx=ma_schedule(asset,leg,data/f'{asset}_15m.csv',replace(adaptive.SETTINGS,squeeze_threshold=value));out=s.r.stacked_signals(sched['baseline'],ctx,policy)
 return leg,out,ctx,policy,pair

def cloned_schedule(value):
 def call(asset,leg,*,price_file,**kw):return ma_schedule(asset,leg,price_file,replace(adaptive.SETTINGS,squeeze_threshold=value))
 return call
proxy=NS(s=NS(prepare=threshold,clone_schedule=cloned_schedule,Probe=s.z.s.Probe))
MA_REBOUND=FunctionType(rebound.build.__code__,dict(rebound.build.__globals__,z=proxy),rebound.build.__name__,rebound.build.__defaults__,rebound.build.__closure__)
# Preserve the historical 120h ER weighting rule only as sizing, never admission.
tree=ast.parse((c.HERE/'history/a_exit_regime_sizing/runner.py').read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name=='weights');ns=dict(sig=NS(r=s.r,PAIR=adaptive.PAIR));exec(compile(ast.Module(body=[node],type_ignores=[]),'historical weights','exec'),ns);weights=ns['weights']

def prepare(asset,data,m,keys,frozen=None):
 from catalog import SPECS
 year=int(m['year']);leg,maps,contexts,base,policy,pair=s.b.p.prepare(asset,data/f'{asset}_15m.csv',m['start'],m['end']);core={t:x for t,x in maps['MA'].items()if m['start']*1000<=t<m['end']*1000}
 evidence=c.HERE/f'reused/REF/{year}/{asset}/signals.json'if year<2026 else c.ROOT/f'outputs/baseline_registry/runs/2026/{asset}/signals.json'
 expected={int(t):d for t,d in json.loads(evidence.read_text())['MA_DIRECTION_REFERENCE'].items()};oldend=m.get('original_end',m['end']);assert {t:x for t,x in core.items()if t<oldend*1000}==expected
 raw=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)];features=c.v.indicators(leg,data/f'{asset}_15m.csv');out={};params={};btc=None
 wanted=[SPECS[k]['historical']for k in keys if SPECS[k]['kind']=='adaptive']
 if'ADAPT_CORE_LIGHT'in keys:wanted.append(SPECS[frozen['D_source']]['historical'])
 adaptive_maps=adaptive.make(asset,data,m['start'],m['end'],list(dict.fromkeys(wanted)))['maps']if wanted else{}
 for key in keys:
  cfg=SPECS[key];kind=cfg['kind'];sig=core
  if kind=='adaptive':sig=adaptive_maps[cfg['historical']]
  elif kind=='union':sig=adaptive.mix(core,adaptive_maps[SPECS[frozen['D_source']]['historical']])
  elif kind=='density'and asset=='ETH':
   sig=threshold(asset,data,m['start'],m['end'],cfg['threshold'],leg,policy,pair)[1]
   if cfg.get('btc_confirm'):
    if btc is None:
     from inputs import prepare as inputs
     bd,bm=inputs(year,'BTC');_,bmaps,*_=s.b.p.prepare('BTC',bd/'BTC_15m.csv',bm['start'],bm['end']);btc=bmaps['MA']
    sig={t:x for t,x in sig.items()if core.get(t)==x or btc.get(t)==x}
  elif kind=='rebound':
   _,orig,new,*_=MA_REBOUND(asset,data,m['start'],m['end']);assert orig==core;sig=dict(core);sig.update(new)
  out[key]=sig
  if key=='REGIME_SIZE':params['regime_weights'],_=weights(dict(raw=raw,leg=leg),core)
 return leg,core,features,out,params
