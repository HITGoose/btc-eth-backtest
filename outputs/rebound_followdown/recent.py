from signals import *
import funded_replay as w
import json,hashlib,traceback
O=Path(__file__).resolve().parent;C=ROOT/'outputs/nov15_continuation';FROM=1794153600;END=1794614400

def run(asset):
 info=z.prepare('NOV',asset);start=info['start'];folder=O/'runs/RECENT'/asset;folder.mkdir(parents=True,exist_ok=True)
 leg,core,new,diag,policy,pair=build(asset,C/'data',start,END);new={t:v for t,v in new.items()if t>=FROM*1000};union=dict(core);union.update(new);assert all(union[t]==v for t,v in core.items());assert {t:v for t,v in union.items()if t<FROM*1000}=={t:v for t,v in core.items()if t<FROM*1000}
 w.E.FEED=json.loads((C/'data'/f'{asset}_funding.json').read_text())['events'];maps={'B':core,'B_PLUS_REBOUND':union};books={k:w.E.book(asset,.0005,.0002,leg,core,False,1.,'F_TOUCH')for k in maps}
 d=s.b.d;d.DATA=C/'data';d.START=start;d.END=END;d.FIRST1=info['first'];d.BASE='https://data.binance.vision/data/futures/um';native=s.b.p.Canonical(asset)
 fp=hashlib.sha256((O/'signals.py').read_bytes()+(O/'recent.py').read_bytes()+w.fund_fp().encode()).hexdigest();ctx=dict(info,asset=asset,period='RECENT',start=start,end=END,leg=leg,native=native,funding_SHA256=hashlib.sha256((C/'data'/f'{asset}_funding.json').read_bytes()).hexdigest(),fingerprint=s.o.digest(dict(code=fp,maps=maps,source_context='NOV1_CONTINUOUS_PATH_NO_NEW_SIGNAL_BEFORE_NOV9')));s.dump(folder/'signals.json',dict(core=core,new=new,diagnostics=diag))
 cache=w.raw_cache(asset,native,folder);ix=(FROM-start)//60
 books,marks=w.segment(folder/'whole',ctx,start,END,books,maps,{k:'STRICT'for k in books},cache,None,True)
 for key,x in books.items():
  mark=w.E.Market(native,cache,x,True)[END-60][3];cfg=dict(key=key,cost='C2',group=key,fill='F_TOUCH',fee=.0005,slip=.0002,funding=True);w.output(ctx,folder/'results','STRICT',cfg,x,marks[key],mark,'funded')
  if key=='B':
   old=json.loads((C/'runs'/asset/'results/C2_B_F_TOUCH_result.json').read_text());assert x.journal==old['trades'];assert abs(x.cash-old['cash'])<1e-8;eq=np.load(C/'runs'/asset/'results/C2_B_F_TOUCH_equity.npz')['marks'];assert np.array_equal(eq,marks[key])
 assert np.array_equal(marks['B'][:ix],marks['B_PLUS_REBOUND'][:ix]);assert [x for x in books['B'].journal if x['opened_us']<FROM*1000000]==[x for x in books['B_PLUS_REBOUND'].journal if x['opened_us']<FROM*1000000]
 s.dump(folder/'status.json',dict(completed=True,fingerprint=fp,original_B_exact_trade_cash_minute_equity_regression=True,pre_Nov9_equity_path_identical=True,new_signals=len(new)))
if __name__=='__main__':
 import sys
 a=sys.argv[1]
 try:run(a)
 except Exception as e:s.dump(O/'runs/RECENT'/a/'failure.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
