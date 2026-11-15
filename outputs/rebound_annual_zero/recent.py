from pathlib import Path
import sys,json,hashlib,traceback,copy,importlib.util
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'outputs/rebound_followdown'));from signals import *
import replay as w
CFG=json.loads((O/'recent_config.json').read_text());START=CFG['start_ms']//1000;NINE=CFG['enable_rebound_ms']//1000;CUT=CFG['raw_execution_end_ms']//1000;END=CFG['bar_execution_end_ms']//1000
ORIGINAL_FP=s.fp
s.fp=lambda:hashlib.sha256(ORIGINAL_FP().encode()+Path(__file__).read_bytes()+(O/'recent_config.json').read_bytes()).hexdigest()
# Only the frozen synthetic price path adapter is reused for the labeled gap segment.
sp=importlib.util.spec_from_file_location('frozen_nov15_bar_adapter',R/'outputs/nov15_15m_simulation/run.py');bar=importlib.util.module_from_spec(sp);sp.loader.exec_module(bar)
# Importing funded_replay via that frozen module installs a funding check hook.
# Restore the exact nonfunded check; no funding events/feeds enter this experiment.
s.b.e.x.check_trend=bar.w.E.original_check

def save(folder,ctx,asset,key,book,marks,market,label):
 cfg=dict(key=key,group=key,cost='ZERO_FEE_ZERO_FUNDING',fee=0.,slip=.0002,funding=False,fill='F_TOUCH');mark=market[CUT-60][3]if label=='RAW'else market[END-60][3];w.output(ctx,folder,'STRICT',cfg,book,marks,mark,'experiment');p=folder/f'{key}_result.json';q=json.loads(p.read_text());q.update(funding='EXPLICITLY_ZERO_BY_USER',status='COMPLETE_RAW_TRADE_SIMULATION'if label=='RAW'else'COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS',no_OHLC_fallback=label=='RAW',raw_execution_end_ms=CUT*1000,synthetic_execution_start_ms=None if label=='RAW'else CUT*1000);s.dump(p,q)

def run(asset):
 folder=O/'recent'/asset;folder.mkdir(parents=True,exist_ok=True);data=O/'recent_data';info=z.prepare('NOV',asset);leg,core,new,diag,policy,pair=build(asset,data,START,END);new={t:v for t,v in new.items()if t>=NINE*1000};union=dict(core);union.update(new);maps={'CONTROL':core,'REBOUND':union};books={k:w.E.book(asset,0.,.0002,leg,core,False,1.,'F_TOUCH')for k in maps}
 d=s.b.d;d.DATA=data;d.START=START;d.END=CUT;d.FIRST1=info['first'];d.BASE='https://data.binance.vision/data/futures/um';native=s.b.p.Canonical(asset);ctx=dict(info,asset=asset,period='RECENT_ZERO',start=START,end=CUT,leg=leg,native=native,fingerprint=s.o.digest(dict(code=s.fp(),maps=maps,config=CFG,asset=asset)));cache=w.raw_cache(asset,native,folder)
 s.dump(folder/'signals.json',dict(core=core,new_rebound=new,no_new_before_Nov9=True))
 books,prefix=w.segment(folder/'pre9',ctx,START,NINE,books,maps,{k:'STRICT'for k in maps},cache,None,False)
 assert s.o.full_state(books['CONTROL'])==s.o.full_state(books['REBOUND']);assert np.array_equal(prefix['CONTROL'],prefix['REBOUND']);s.dump(folder/'pre9_state_comparison.json',dict(passed=True,full_state_equal=True,full_state_SHA256=s.o.digest(s.o.full_state(books['CONTROL'])),cash=books['CONTROL'].cash,summary=s.o.brief(books['CONTROL'])))
 books,suffix=w.segment(folder/'raw',ctx,NINE,CUT,books,maps,{k:'STRICT'for k in maps},cache,None,True);full={k:np.r_[prefix[k],suffix[k]]for k in maps}
 for key,x in books.items():save(folder/'raw_results',ctx,asset,key,x,full[key],w.E.Market(native,cache,x,True),'RAW')
 ref=s.OUT/'runs/NOV'/asset/'baseline/results/STRICT/C0_B_F_TOUCH_result.json';old=json.loads(ref.read_text());q=json.loads((folder/'raw_results/CONTROL_result.json').read_text());oldv=np.load(ref.with_name('C0_B_F_TOUCH_equity.npz'))['marks'];assert np.array_equal(full['CONTROL'][:len(oldv)],oldv);assert q['trades'][:len(old['trades'])]==old['trades'];s.dump(folder/'baseline_comparison.json',dict(passed=True,original_zero_fee_full_prior_prefix_exact=True,reference=str(ref.relative_to(R))))
 # Extend only the unavailable raw tail under the two predeclared OHLC assumptions.
 raw=np.loadtxt(data/f'{asset}_15m.csv',delimiter=',',skiprows=1)
 if END>CUT:
  for path in ['OHLC','OLHC']:
   clones={k:s.o.clone(x,leg)for k,x in books.items()};n=bar.Native(raw,path);n.end=END;cache2=bar.Cache(n);ctx2=dict(ctx,end=END,native=n,fingerprint=s.o.digest(dict(base=ctx['fingerprint'],path=path)));clones,tail=w.segment(folder/path,ctx2,CUT,END,clones,maps,{k:'SYNTHETIC_BAR_PATH'for k in maps},cache2,None,True)
   for key,x in clones.items():save(folder/path/'results',ctx2,asset,key,x,np.r_[full[key],tail[key]],w.E.Market(n,cache2,x,True),'BAR')
 s.dump(folder/'status.json',dict(completed=True,fingerprint=s.fp(),raw_execution_end_ms=CUT*1000,bar_execution_end_ms=END*1000,pre9_state_identical=True,new_signals=sum(t<END*1000 for t in new)))
if __name__=='__main__':
 a=sys.argv[1]
 try:run(a)
 except Exception as e:s.dump(O/'recent'/a/'failure.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
