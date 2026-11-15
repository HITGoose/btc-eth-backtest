from pathlib import Path
import sys,json,gzip,pickle,hashlib,traceback
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/extra_sizing_cost_stress'));import funded_replay as w
s=w.s;z=w.z;np=w.np

def run(asset):
 old=z.prepare('NOV',asset);start=old['end'];end=1794614400;folder=O/'runs'/asset;folder.mkdir(parents=True,exist_ok=True)
 cp=w.OUT/'runs/NOV'/asset/'funded/whole/checkpoint.pkl.gz'
 with gzip.open(cp,'rb')as f:q=pickle.load(f)
 assert q['fp']==w.fund_fp() and q['next']==start and q['end']==start
 for k,x in q['books'].items():
  if k.startswith('C2_') and k.endswith('F_TOUCH'):
   ref=json.loads((w.OUT/'runs/NOV'/asset/'funded/results/STRICT'/f'{k}_result.json').read_text());assert x.cash==ref['cash'] and x.journal==ref['trades']
 leg,_,_,_,policy,pair=w.b.p.prepare(asset,O/'data'/f'{asset}_15m.csv',old['start'],end)
 core=z.s.prepare(asset,O/'data',old['start'],end,.25,leg,policy,pair)[1];wide=z.s.prepare(asset,O/'data',old['start'],end,.30,leg,policy,pair)[1]
 assert {t:v for t,v in core.items()if t<start*1000}==old['core'];assert {t:v for t,v in wide.items()if t<start*1000}==old['wide']
 if asset=='ETH':
  bleg,_,_,_,bp,br=w.b.p.prepare('BTC',O/'data/BTC_15m.csv',old['start'],end);btc=z.s.prepare('BTC',O/'data',old['start'],end,.25,bleg,bp,br)[1]
 else:btc=core
 feed=json.loads((O/'data'/f'{asset}_funding.json').read_text())['events'];books={};maps={};cfgs=[];proof=[]
 for group in(['B']if asset=='BTC'else['B','I100','I50','I25']):
  key='C2_'+group+'_F_TOUCH';x=q['books'][key];n=len(x.funding_feed);assert feed[:n]==x.funding_feed;x.funding_feed=feed;x.leg=leg;assert x.core==old['core'];x.core=core;books[key]=x;parent,ratio=s.GROUPS[group];maps[key]=core if asset=='BTC'else z.classify(core,wide,btc,parent)[0];cfgs.append(dict(key=key,cost='C2',group=group,fill='F_TOUCH',fee=.0005,slip=.0002,funding=True));proof.append(dict(key=key,cash=x.cash,closed_trades=len(x.journal),state=w.b.p.state(x),old_funding_cursor=x.funding_cursor,old_funding_records=n))
 w.b.d.DATA=O/'data';w.b.d.START=old['start'];w.b.d.END=end;w.b.d.FIRST1=old['first'];w.b.d.BASE='https://data.binance.vision/data/futures/um'
 native=w.b.p.Canonical(asset);ctx=dict(old,asset=asset,period='NOV_CONTINUED',native=native,start=old['start'],end=end,leg=leg,funding_SHA256=hashlib.sha256((O/'data'/f'{asset}_funding.json').read_bytes()).hexdigest(),fingerprint=s.o.digest(dict(native=[hashlib.sha256((O/'data'/f'{asset}_15m.csv').read_bytes()).hexdigest(),hashlib.sha256((O/'data'/f'{asset}_1m.npy').read_bytes()).hexdigest()],maps=maps,parent_cp_SHA256=hashlib.sha256(cp.read_bytes()).hexdigest(),runner_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())))
 s.dump(folder/'continuity_proof.json',dict(parent_checkpoint=str(cp.relative_to(R)),parent_checkpoint_SHA256=hashlib.sha256(cp.read_bytes()).hexdigest(),parent_financial_fingerprint=q['fp'],parent_end_UTC='2026-11-13T00:00:00Z',retained_from_original_Nov1=True,not_reset_on_Nov9=True,full_signal_prefix_equal=True,accounts=proof))
 cache=w.raw_cache(asset,native,folder);books,marks=w.segment(folder/'extension',ctx,start,end,books,maps,{k:'STRICT'for k in books},cache,None,True)
 for cfg in cfgs:
  k=cfg['key'];mark=w.E.Market(native,cache,books[k],True)[end-60][3];full=np.r_[q['marks'][k],marks[k]];w.output(ctx,folder/'results','STRICT',cfg,books[k],full,mark,'funded')
 s.dump(folder/'signals.json',dict(core=core,wide=wide,accepted=maps));s.dump(folder/'status.json',dict(completed=True,through_UTC='2026-11-14T00:00:00Z',through_Beijing='2026-11-14T08:00:00+08:00',not_Nov15_verified=True))
if __name__=='__main__':
 a=sys.argv[1]
 try:run(a)
 except Exception as e:s.dump(O/'runs'/a/'failure.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
