"""Reuse only unchanged independent BTC C0/C1, with full source/native/signals proof."""
from pathlib import Path
import json,hashlib
import shared as s
import cost_engine as E
import replay as w
np=s.np;proof=[]
s.b.verify_parent()
for period in w.z.PERIODS:
 folder=s.OUT/'runs'/period/'BTC/baseline'
 if(folder/'status.json').exists() and json.loads((folder/'status.json').read_text()).get('status')!='STRICT_REFERENCE_REUSED_UNCHANGED_BTC':continue
 # Never modify a task being replayed or holding an execution checkpoint.
 if(folder/'whole/checkpoint.pkl.gz').exists():continue
 info=s.z.prepare(period,'BTC');hashes={n:hashlib.file_digest((info['data']/n).open('rb'),'sha256').hexdigest()for n in ['BTC_15m.csv','BTC_1m.npy']}
 for cfg in w.configurations('BTC','baseline'):
  op,ep=w.oldpath(period,'BTC',cfg['cost'],'B','STRICT');old=json.loads(op.read_text());prov=json.loads((op.parent/'input_provenance.json').read_text());assert (prov.get('derived_SHA256')or{Path(k).name:v for k,v in prov['derived_file_hashes'].items()})==hashes
  oldsignals=json.loads((op.parent/'signals.json').read_text());assert{int(k):v for k,v in oldsignals['core'].items()}==info['core']
  assert old['fee']==cfg['fee'] and old['starting_equity']==500. and old['source']=='BINANCE_USDT_PERPETUAL_ONLY'
  marks=np.load(ep);s.z.h.curve(old,marks);assert len(marks)==(info['end']-info['start'])//60
  assert abs(old['cash']-500-sum(x['delta']for x in old['cash_events']))<1e-7
  q=dict(old);q.update(configuration=cfg,key=cfg['key'],status='STRICT_REFERENCE_REUSED_UNCHANGED_BTC',scenario='STRICT',period=period,funding='NOT_INCLUDED',funding_total_USDT=0.,sizing_audit=[],BTC_baseline_reused=True,baseline_exact_trade_cash_equity_minutes=True)
  slip=cfg['slip'];slipcost=0.
  for t in s.z.h.rows(old):
   side=1 if t['side']=='LONG'else-1
   if t['status']=='CLOSED':slipcost+=t['exit']/(1-side*slip)*t['final_exit_quantity']*slip
   slipcost+=sum(f['trigger_print']*f['quantity']*slip for f in t.get('partial_fills',[]))
  q['slippage_cost_USDT']=slipcost
  for trade in q['trades']:trade.setdefault('origin','CORE')
  if q['state_at_end']['position']:
   order=q['state_at_end']['position']['order'];order.setdefault('origin','CORE');order.setdefault('signal_close_ms',order['time']-10000)
  if q['state_at_end']['pending_order']:
   order=q['state_at_end']['pending_order'];order.setdefault('origin','CORE');order.setdefault('signal_close_ms',order['time']-10000)
  for e in old['events']:
   if e['event']=='order_sent':q['sizing_audit'].append(dict(signal_close_ms=e.get('signal_close_ms',e['time_us']//1000-10000),origin='CORE',accepted=True,actual_quantity=e.get('quantity'),actual_notional=None))
  dest=folder/'results/STRICT';dest.mkdir(parents=True,exist_ok=True);s.dump(dest/(cfg['key']+'_result.json'),q);np.savez_compressed(dest/(cfg['key']+'_equity.npz'),marks=marks)
  proof.append(dict(period=period,cost=cfg['cost'],source_result=str(op),source_result_SHA256=hashlib.file_digest(op.open('rb'),'sha256').hexdigest(),source_equity_SHA256=hashlib.file_digest(ep.open('rb'),'sha256').hexdigest(),current_native_SHA256=hashes,complete_signals_exact=True,financial_fingerprint_unchanged=s.b.PARENT_FP,comparison='full trades/cash/end/minute arrays copied exactly; no new BTC replay claimed',only_C0_C1_touch=True))
 s.dump(folder/'status.json',dict(completed=True,fp=s.fp(),configs=w.configurations('BTC','baseline'),status='STRICT_REFERENCE_REUSED_UNCHANGED_BTC'))
s.dump(s.OUT/'BTC_reuse_proof.json',dict(reused=proof,other_costs_and_through_require_new_replay=True));print('REUSED',len(proof),'independent BTC baselines')
