from pathlib import Path
from dataclasses import replace
import tempfile,json
import numpy as np
import strategy as s
OUT=s.OUT;checks=[]
def test(name,fn):
 fn();checks.append(dict(name=name,passed=True));print('PASS',name,flush=True)
folder,data,start,end,first,sources=s.inputs('2024','ETH')
leg,old,ctx,base,policy,pair=s.p.prepare('ETH',data/'ETH_15m.csv',start,end)
prepared={t:s.prepare('ETH',data,start,end,t,leg,policy,pair) for t in (.25,.30,.35)}
def old_equal():assert prepared[.25][1]==old['ER']
test('0.25 exact full-chain signal regression',old_equal)
def nested():
 a,b,c=[set(prepared[t][1].items())for t in (.25,.30,.35)];assert a<=b<=c and len(c)>len(a)
test('ETH .30/.35 reach underlying candidate and overlay, strictly add signals',nested)
def globals_clean():assert s.r.regime.ENTRY.squeeze_threshold==.25 and policy.range_squeeze_pct==.25
test('no global or original policy contamination',globals_clean)
_,btcdata,bs,be,_,_=s.inputs('2024','BTC');bl,bo,bc,bb,bp,br=s.p.prepare('BTC',btcdata/'BTC_15m.csv',bs,be)
def btc_equal():
 for t in (.25,.30,.35):assert s.prepare('BTC',btcdata,bs,be,t,bl,bp,br)[1]==bo['ER']
test('BTC remains exact .25 for every variant',btc_equal)
def trend_rejection():
 diag=s.diagnose('ETH',data,leg,policy,pair);tested=0
 for threshold,(_,signals,contexts,_,_) in prepared.items():
  for stamp,features in diag.items():
   if features['ER_regime'] in ('up','down') and not features['trend_confirmation_pass']:
    assert signals.get(stamp)!=features['side'];tested+=1
 assert tested>0
 # Diagnostics did not consume retests or change later schedules.
 assert s.prepare('ETH',data,start,end,.35,leg,policy,pair)[1]==prepared[.35][1]
test('complete diagnostic rejects failed trend confirmation and is read-only',trend_rejection)
def prefix_causality():
 cutoff=start+125*86400
 raw=np.loadtxt(data/'ETH_15m.csv',delimiter=',',skiprows=1);raw=raw[raw[:,0]<cutoff*1000]
 with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
  p=Path(tmp)/'ETH_15m.csv';np.savetxt(p,raw,delimiter=',',fmt=['%d']+['%.17g']*5,header='timestamp,open,high,low,close,volume',comments='')
  for threshold in (.25,.30,.35):
   _,small,_,_,_=s.prepare('ETH',Path(tmp),start,cutoff,threshold)
   a={k:v for k,v in small.items() if start*1000<=k<cutoff*1000}
   b={k:v for k,v in prepared[threshold][1].items() if start*1000<=k<cutoff*1000}
   assert a==b,threshold
 # Final CSV bar is excluded as a signal by the inherited baseline; no unfinished-bar entry.
 for _,signals,_,_,_ in prepared.values():assert max(signals)<end*1000
test('future suffix and omitted unclosed bar cannot change prefix signals',prefix_causality)
(OUT/'entry_tests.json').write_text(json.dumps(dict(passed=True,checks=checks,ETH_signal_counts={str(k):len(v[1])for k,v in prepared.items()}),indent=2))
