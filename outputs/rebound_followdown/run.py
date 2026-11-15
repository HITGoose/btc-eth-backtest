from signals import *
from counts import WINDOWS
from datetime import datetime,timezone
import replay as w
import hashlib,traceback
O=Path(__file__).resolve().parent
ORIGINAL_FP=s.fp

def fp():return hashlib.sha256(ORIGINAL_FP().encode()+(O/'signals.py').read_bytes()+(O/'run.py').read_bytes()+(O/'EXPERIMENT.md').read_bytes()).hexdigest()
s.fp=fp

def run(year,asset):
 row=next(x for x in WINDOWS if x[0]==year);start,end=[int(datetime.fromisoformat(v).replace(tzinfo=timezone.utc).timestamp())for v in row[1:]];folder=O/'runs'/year/asset;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fingerprint']==fp();return
 info=z.prepare(year,asset);leg,core,new,diag,policy,pair=build(asset,info['data'],start,end);union=dict(core);union.update(new);assert all(union[t]==v for t,v in core.items())
 s.dump(folder/'signals.json',dict(CORE=core,REBOUND=new,full_rule_diagnostics=diag))
 d=s.b.d;d.BASE='https://data.binance.vision/data/futures/um';d.DATA=info['data'];d.START=start;d.END=end;d.FIRST1=info['first'];native=s.b.p.Canonical(asset)
 ctx=dict(info,asset=asset,period=year+'_STRESS',start=start,end=end,leg=leg,native=native,fingerprint=s.o.digest(dict(code=fp(),core=core,new=new,window=[start,end],native=[hashlib.sha256((info['data']/f'{asset}_15m.csv').read_bytes()).hexdigest(),hashlib.sha256((info['data']/f'{asset}_1m.npy').read_bytes()).hexdigest()])))
 maps={'B':core,'B_PLUS_REBOUND':union};books={k:w.E.book(asset,.0005,.0002,leg,core,False,1.,'F_TOUCH')for k in maps};cache=w.raw_cache(asset,native,folder)
 books,marks=w.segment(folder/'whole',ctx,start,end,books,maps,{k:'STRICT'for k in books},cache,None,True)
 for key,x in books.items():
  mark=w.E.Market(native,cache,x,True)[end-60][3];cfg=dict(key=key,cost='C1_NO_FUNDING',group=key,fill='F_TOUCH',fee=.0005,slip=.0002,funding=False);w.output(ctx,folder/'results','STRICT',cfg,x,marks[key],mark,'experiment')
  out=folder/'results'/f'{key}_result.json';q=json.loads(out.read_text());q['experimental_rule']='REBOUND_FOLLOWDOWN'if key!='B'else'ORIGINAL_B';q['funding']='NOT_INCLUDED';q['independent_window_initial_cash']=500;s.dump(out,q)
 s.dump(folder/'status.json',dict(completed=True,fingerprint=fp(),new_signals=len(new),funding='NOT_INCLUDED'))
if __name__=='__main__':
 import sys,json
 year,asset=sys.argv[1:3]
 try:run(year,asset)
 except Exception as e:s.dump(O/'runs'/year/asset/'failure.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
