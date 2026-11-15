from pathlib import Path
import sys,json,gzip,pickle,hashlib,datetime,traceback
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/rebound_followdown'));from signals import *
import funded_replay as w
C=R/'outputs/nov15_continuation';P=R/'outputs/rebound_followdown';CONFIG=json.loads((O/'config.json').read_text());START=CONFIG['start_continuation_ms']//1000;END=CONFIG['end_ms']//1000
class Native:
 def __init__(self,raw,path):self.bars=raw;self.path=path;self.first=int(raw[0,0]//1000);self.end=END;self.market=self
 def points(self,bar):
  row=self.bars[(bar*1000-int(self.bars[0,0]))//900000];o,h,l,c=row[1:5];return [o,h,l,c]if self.path=='OHLC'else[o,l,h,c]
 def price(self,t):
  bar=int(t//900*900);off=t-bar;v=self.points(bar);return float(np.interp(off,[0,300,600,899],v))
 def __getitem__(self,minute):
  v=np.array([self.price(t)for t in range(minute,minute+60)]);return [v[0],v.max(),v.min(),v[-1],0.]
class Cache:
 def __init__(self,native):self.native=native;self.cache={};self.sources={}
 def load(self,minute):
  day=minute//86400*86400
  if day not in self.cache:
   lo=max(day,self.native.first);hi=min(day+86400,self.native.end);times=np.arange(lo,hi,dtype=float);prices=np.empty(len(times))
   for bar in range(lo//900*900,hi,900):
    a=max(bar,lo);b=min(bar+900,hi);prices[a-lo:b-lo]=np.interp(np.arange(a-bar,b-bar),[0,300,600,899],self.native.points(bar))
   self.cache={day:np.column_stack([times,times,prices])}
  return self.cache[day]
def run(asset):
 info=z.prepare('NOV',asset);initial=info['start'];leg,_,_,_,policy,pair=s.b.p.prepare(asset,O/'data'/f'{asset}_15m.csv',initial,END);core=z.s.prepare(asset,O/'data',initial,END,.25,leg,policy,pair)[1];wide=z.s.prepare(asset,O/'data',initial,END,.30,leg,policy,pair)[1]
 if asset=='ETH':
  bl,_,_,_,bp,br=s.b.p.prepare('BTC',O/'data/BTC_15m.csv',initial,END);btc=z.s.prepare('BTC',O/'data',initial,END,.25,bl,bp,br)[1]
 else:btc=core
 pleg,pcore,new,diag,_,_=build(asset,O/'data',initial,END);new={t:v for t,v in new.items()if t>=1794153600000};union=dict(core);union.update(new)
 bcp=C/'runs'/asset/'extension/checkpoint.pkl.gz';pcp=P/'runs/RECENT'/asset/'whole/checkpoint.pkl.gz'
 with gzip.open(bcp,'rb')as f:base=pickle.load(f)
 with gzip.open(pcp,'rb')as f:exp=pickle.load(f)
 assert base['next']==exp['next']==START
 raw=np.loadtxt(O/'data'/f'{asset}_15m.csv',delimiter=',',skiprows=1);fund=json.loads((O/'data'/f'{asset}_funding.json').read_text())['events']
 for path in ['OHLC','OLHC']:
  folder=O/'runs'/asset/path;folder.mkdir(parents=True,exist_ok=True);books={};maps={};prefix={};proof=[]
  for group in (['B','B_PLUS_REBOUND']if asset=='BTC'else['B','I100','I50','I25','B_PLUS_REBOUND']):
   source=exp if group=='B_PLUS_REBOUND'else base;oldkey='B_PLUS_REBOUND'if group=='B_PLUS_REBOUND'else f'C2_{group}_F_TOUCH';x=s.o.clone(source['books'][oldkey],leg)
   # Only immutable indicator/funding lookup is extended. No financial state reset.
   assert {t:v for t,v in x.core.items()if initial*1000<=t<START*1000}=={t:v for t,v in core.items()if initial*1000<=t<START*1000}
   n=len(x.funding_feed);assert fund[:n]==x.funding_feed;x.funding_feed=fund;x.core=core;x.leg=leg;books[group]=x;prefix[group]=source['marks'][oldkey] if group=='B_PLUS_REBOUND' else np.load(C/'runs'/asset/'results'/f'{oldkey}_equity.npz')['marks']
   maps[group]=union if group=='B_PLUS_REBOUND'else core if asset=='BTC'or group=='B'else z.classify(core,wide,btc,'I')[0];proof.append(dict(group=group,cash=x.cash,parent=str((pcp if group=='B_PLUS_REBOUND'else bcp).relative_to(R)),parent_SHA256=hashlib.sha256((pcp if group=='B_PLUS_REBOUND'else bcp).read_bytes()).hexdigest(),parent_complete_state_SHA256=s.o.digest(s.o.full_state(x)),closed_trades=len(x.journal)))
  native=Native(raw,path);cache=Cache(native);ctx=dict(info,asset=asset,period='NOV15_BAR_SIM',start=initial,end=END,leg=leg,native=native,funding_SHA256=hashlib.sha256((O/'data'/f'{asset}_funding.json').read_bytes()).hexdigest(),fingerprint=s.o.digest(dict(code=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),config=CONFIG,path=path,maps=maps,proof=proof)))
  s.dump(folder/'continuity.json',dict(parent_verified_prefix_through_Beijing='2026-11-14T08:00:00+08:00',accounts=proof));books,marks=w.segment(folder/'extension',ctx,START,END,books,maps,{k:'SIMULATED_15M_PATH'for k in books},cache,None,True)
  for group,x in books.items():
   cfg=dict(key=group,group=group,cost='C2_FUNDING_EXACT_EXECUTION_APPROXIMATE',fee=.0005,slip=.0002,fill='F_TOUCH_SYNTHETIC_PATH');mark=native[END-60][3];w.output(ctx,folder/'results','SIMULATED_15M_PATH',cfg,x,np.r_[prefix[group],marks[group]],mark,'funded')
   p=folder/'results'/f'{group}_result.json';q=json.loads(p.read_text());q.update(status='COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS',no_OHLC_fallback=False,observed_raw_execution_end_ms=START*1000,synthetic_execution_start_ms=START*1000,synthetic_extrema_path=path,synthetic_times_not_observed=True,simulated_phase2_not_actual_latest_trade_poll=True,not_strict_best_worst_bounds=True);s.dump(p,q)
  s.dump(folder/'status.json',dict(completed=True,status='COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS',path=path))
 s.dump(O/f'{asset}_signals.json',dict(core=core,wide=wide,new_rebound=new,new_diagnostics=diag))
if __name__=='__main__':
 a=sys.argv[1]
 try:run(a)
 except Exception as e:s.dump(O/f'{a}_failure.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
