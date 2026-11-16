"""Existing source functions only; baseline signals always compared with archived CORE."""
import common as c
from pathlib import Path
from types import SimpleNamespace as NS
import ast
v=c.v;s=c.s;np=c.np
adaptive=c.module('retest_original_adaptive',c.HERE/'history/adaptive_density_control/signals.py')
rebound=c.module('retest_original_rebound',c.HERE/'history/rebound_followdown/signals.py')
def function(path,name,ns):
 tree=ast.parse(Path(path).read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name==name);exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns);return ns[name]
weights=function(c.HERE/'history/a_exit_regime_sizing/runner.py','weights',dict(sig=NS(r=s.r,PAIR=adaptive.PAIR)))

def prepare(asset,data,m,keys,frozen=None):
 from catalog import SPECS
 leg,maps,contexts,base,policy,pair=s.b.p.prepare(asset,data/f'{asset}_15m.csv',m['start'],m['end']);core={t:x for t,x in maps['ER'].items()if m['start']*1000<=t<m['end']*1000}
 import json
 expected={int(k):x for k,x in json.loads((c.ROOT/m['reference']/'core_signals.json').read_text())['core'].items()};oldend=m.get('original_end',m['end']);assert {t:x for t,x in core.items()if t<oldend*1000}==expected
 raw=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)];assert len(raw)==len(leg.width)
 features=v.indicators(leg,data/f'{asset}_15m.csv');out={};params={};btc=None;adaptive_maps={}
 wanted=[SPECS[k]['historical']for k in keys if SPECS[k]['kind']=='adaptive']
 if'ADAPT_CORE_LIGHT'in keys:wanted.append(SPECS[frozen['D_source']]['historical'])
 if wanted:adaptive_maps=adaptive.make(asset,data,m['start'],m['end'],list(dict.fromkeys(wanted)))['maps']
 for key in keys:
  cfg=SPECS[key];kind=cfg['kind'];sig=core
  if kind=='adaptive':sig=adaptive_maps[cfg['historical']]
  elif kind=='union':sig=adaptive.mix(core,adaptive_maps[SPECS[frozen['D_source']]['historical']])
  elif kind=='density'and asset=='ETH':
   sig=s.z.s.prepare(asset,data,m['start'],m['end'],cfg['threshold'],leg,policy,pair)[1]
   if cfg.get('btc_confirm'):
    if btc is None:
     from inputs import prepare as inputs
     bd,bm=inputs(m['year'],'BTC');bl,bmap,*_=s.b.p.prepare('BTC',bd/'BTC_15m.csv',bm['start'],bm['end']);btc=bmap['ER']
    sig={t:x for t,x in sig.items()if core.get(t)==x or btc.get(t)==x}
  elif kind=='rebound':
   _,orig,new,*_=rebound.build(asset,data,m['start'],m['end']);assert orig==core;sig=dict(core);sig.update(new)
  out[key]=sig
  if key=='REGIME_SIZE':params['regime_weights'],_=weights(dict(raw=raw,leg=leg),core)
 return leg,core,features,out,params
