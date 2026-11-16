from pathlib import Path
import sys,json,hashlib,traceback,datetime
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/rebound_followdown'));from signals import *
import replay as w
ORIGINAL_FP=s.fp;ORIGINAL_SEGMENT_FP=s.fp()
FROZEN_SIGNAL_SHA=hashlib.sha256((R/'outputs/rebound_followdown/signals.py').read_bytes()).hexdigest()
def fp():return hashlib.sha256(ORIGINAL_FP().encode()+Path(__file__).read_bytes()+FROZEN_SIGNAL_SHA.encode()+(O/'EXPERIMENT.md').read_bytes()).hexdigest()
s.fp=fp

def reference(period,asset):
 scene='S_ALL'if period=='2025'and asset=='ETH'else'STRICT';p=s.OUT/'runs'/period/asset/'baseline/results'/scene/'C0_B_F_TOUCH_result.json';return p,p.with_name('C0_B_F_TOUCH_equity.npz')
def run(period,asset):
 folder=O/'runs'/period/asset;folder.mkdir(parents=True,exist_ok=True)
 if(folder/'status.json').exists():assert json.loads((folder/'status.json').read_text())['fingerprint']==fp();return
 info=z.prepare(period,asset);start,end=info['start'],info['end'];leg,core,new,diag,policy,pair=build(asset,info['data'],start,end);expected={t:v for t,v in info['core'].items()if start*1000<=t<end*1000};assert core==expected
 union=dict(core);union.update(new);assert not(set(core)&set(new));assert all(union[t]==v for t,v in core.items());s.dump(folder/'signals.json',dict(core=core,new_rebound=new,signal_source_SHA256=FROZEN_SIGNAL_SHA,no_Nov9_gate_in_annual=True))
 # Keep only compact admission diagnostics; post-hoc reclaim labels do not feed orders.
 z.csv_dump(folder/'new_signal_diagnostics.csv',[d for d in diag if d['new_signal']])
 d=s.b.d;d.BASE='https://data.binance.vision/data/futures/um';d.DATA=info['data'];d.START=start;d.END=end;d.FIRST1=info['first'];native=s.b.p.Canonical(asset);hashes={n:hashlib.file_digest((info['data']/n).open('rb'),'sha256').hexdigest()for n in [asset+'_15m.csv',asset+'_1m.npy']}
 ctx=dict(info,asset=asset,period=period,start=start,end=end,leg=leg,native=native,fingerprint=s.o.digest(dict(code=fp(),core=core,new=new,native=hashes,zero_fee=True,zero_funding=True)))
 s.dump(folder/'config.json',dict(period=period,asset=asset,start_UTC=datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),end_UTC=datetime.datetime.fromtimestamp(end,datetime.timezone.utc).isoformat(),start_Beijing=s.r.local_s(start),end_Beijing=s.r.local_s(end),initial_equity=500,fee=0,funding=0,exit_slippage=.0002,core_priority=False,extra_ratio=1,fill='F_TOUCH',signal_source_SHA256=FROZEN_SIGNAL_SHA,financial_fingerprint=ORIGINAL_SEGMENT_FP,runner_fingerprint=fp(),data_SHA256=hashes))
 maps={'CONTROL':core,'REBOUND':union};books={k:w.E.book(asset,0.,.0002,leg,core,False,1.,'F_TOUCH')for k in maps};strict=w.raw_cache(asset,native,folder);cache=strict
 if period=='2025'and asset=='ETH':
  views=s.a.Views();cache=s.a.ScenarioCache(strict,views,'S_ALL');s.dump(folder/'S_ALL_evidence.json',dict(status='COMPLETED_WITH_DATA_ANOMALY',scope='ONLY_PREVIOUSLY_AUTHORIZED_FILE_SHA',metadata=views.get('S_ALL')['metadata'],nine_scenarios_not_repeated=True))
 print('START',period,asset,'core',len(core),'new',len(new),flush=True)
 books,marks=w.segment(folder/'whole',ctx,start,end,books,maps,{k:'S_ALL'if period=='2025'and asset=='ETH'else'STRICT'for k in books},cache,None,True)
 for key,x in books.items():
  mark=w.E.Market(native,cache,x,True)[end-60][3];cfg=dict(key=key,cost='ZERO_FEE_ZERO_FUNDING',group=key,fill='F_TOUCH',fee=0.,slip=.0002,funding=False);w.output(ctx,folder/'results','S_ALL'if period=='2025'and asset=='ETH'else'STRICT',cfg,x,marks[key],mark,'experiment')
  p=folder/'results'/f'{key}_result.json';q=json.loads(p.read_text());q.update(status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'and asset=='ETH'else'COMPLETE',group_name_scope='THIS_ROUND_CONTROL_OR_REBOUND_PER_ASSET',funding='EXPLICITLY_ZERO_BY_USER',fee=0.);s.dump(p,q)
 ref,eq=reference(period,asset);old=json.loads(ref.read_text());actual=json.loads((folder/'results/CONTROL_result.json').read_text());assert old['fee']==0 and old['configuration']['slip']==.0002 and not old['configuration']['funding'];assert old['trades']==actual['trades'],('baseline trade difference',period,asset);assert old['cash']==actual['cash']and old['ending_equity']==actual['ending_equity'];assert np.array_equal(np.load(eq)['marks'],marks['CONTROL']),('baseline minute equity difference',period,asset)
 s.dump(folder/'baseline_comparison.json',dict(passed=True,trade_cash_equity_minute_exact=True,reference=str(ref.relative_to(R)),reference_SHA256=hashlib.sha256(ref.read_bytes()).hexdigest(),reference_financial_fingerprint=ORIGINAL_SEGMENT_FP,current_financial_unchanged=True))
 s.dump(folder/'status.json',dict(completed=True,fingerprint=fp(),status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'and asset=='ETH'else'COMPLETE',new_signals=len(new)))
if __name__=='__main__':
 period,asset=sys.argv[1:3]
 try:run(period,asset)
 except Exception as e:s.dump(O/'runs'/period/asset/'failure.json',dict(error=repr(e),traceback=traceback.format_exc(),fingerprint=fp()));raise
