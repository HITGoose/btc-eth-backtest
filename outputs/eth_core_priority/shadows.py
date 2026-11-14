"""Independent continuation of actual EXTRA position immediately before forced exit.
No new orders; original V2 and original stops; never alters actual accounts.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,sys,json,gzip,pickle,traceback,copy
import numpy as np
import strategy as z
import priority_engine as pe
h=z.module('priority_shadow_metrics',z.OUT/'analysis_helpers.py');OUT=z.OUT

def run(period,group,cost):
 locate=z.module('priority_collect_locator',OUT/'collect.py').locate
 folder=locate(period,'ETH',cost,group);snapfile=folder/f'{cost}_{group}_shadow_snapshots.pkl.gz'
 target=OUT/'shadows'/period/cost/group;target.mkdir(parents=True,exist_ok=True)
 if(target/'status.json').exists()and h.read(target/'status.json').get('complete'):return
 with gzip.open(snapfile,'rb')as f:snaps=pickle.load(f)
 q=h.read(folder/f'{cost}_{group}_result.json');actual={x['signal_close_ms']:x for x in q['trades']if x['reason']=='core_priority_exit'}
 assert len(snaps)==len(actual)
 if not snaps:z.dump(target/'result.json',[]);z.dump(target/'status.json',dict(complete=True,count=0));return
 info=z.prepare(period,'ETH');start=info['start'];end=info['end'];leg=info['leg'];z.d.DATA=info['data'];z.d.START=start;z.d.END=end;z.d.FIRST1=info['first'];z.d.BASE='https://data.binance.vision/data/futures/um';native=z.p.Canonical('ETH');cache=z.e.RawCache('ETH',native,target)
 # Resume finished individual shadows; snapshots are trusted project-generated.
 rows=h.read(target/'result.json')if(target/'result.json').exists()else[];done={x['signal_close_ms']for x in rows}
 for snap in snaps:
  stamp=snap['order_info']['signal_close_ms']
  if stamp in done:continue
  b=pe.book('ETH',snap['fee'],leg,{},False);b.cash=snap['cash'];b.position=copy.deepcopy(snap['position']);b.order_info=dict(snap['order_info']);b.tranches=list(snap['tranches']);z.r.model.FEE=b.fee
  market=pe.Market(native,cache,b,True);first=(snap['exit_us']//60000000)*60
  for minute in range(first,end,60):
   b.observing_event=False
   if minute>first:z.v.check(b,minute)
   for time,price,poll in market.events(minute,2,poll_seconds=5):
    at_us=round(time*1e6)
    if at_us<snap['exit_us']:continue
    if poll and at_us<=snap['exit_us']:continue
    if not poll and b.current_raw_id<=snap['exit_raw_id']:continue
    b.audit_timestamp=time;b.observing_event=True
    if poll:b.update_ladder(price)
    else:b.visit(price,round(time*1000),True,advance_ladder=False)
    if not b.position:break
   if not b.position:break
  a=actual[stamp];initial=a['entry']*a['quantity']
  if b.position:
   mark=market[end-60][3];net=getattr(b.position,'partial_net',0)-b.fee*a['entry']*a['quantity']+b.position.marked(mark);status='OPEN_MTM_AT_PERIOD_END';close_us=None
  else:
   net=b.journal[-1]['net'];status='CLOSED';close_us=b.journal[-1]['closed_us']
  delta=a['net']-net
  rows.append(dict(period=period,cost=cost,group=group,signal_close_ms=stamp,side=a['side'],origin='EXTRA',forced_exit_us=snap['exit_us'],forced_exit_raw_id=snap['exit_raw_id'],active_actual_full_trade_net=a['net'],shadow_status=status,shadow_exit_us=close_us,shadow_full_trade_contribution=net,actual_minus_shadow=delta,estimated_foregone_profit=max(0.,-delta),estimated_avoided_loss=max(0.,delta),actual_minus_shadow_per_1000=delta/initial*1000,scope='independent continuation same initial quantity/position state; no replacement CORE and no future entries; NOT additive to actual account PnL'))
  z.dump(target/'result.json',rows);print('SHADOW',period,cost,group,stamp,delta,flush=True)
 z.dump(target/'status.json',dict(complete=True,count=len(rows)))

def collect():
 rows=[];fail=[]
 for file in(OUT/'shadows').glob('*/*/*/result.json'):rows+=h.read(file)
 for file in(OUT/'shadows').glob('*/*/*/failure.json'):fail.append(dict(path=str(file),**h.read(file)))
 z.csv_dump(OUT/'shadow_results.csv',rows);z.dump(OUT/'shadow_failures.json',fail)
 lines=['# 独立影子延续诊断','','在每次实际主动退出前复制EXTRA的原持仓、止损、已减仓和当前现金状态，从退出成交事件之后的新trade ID继续，保留原V2与轮询，不加入CORE或任何后续新入场。期末仍未退出用同区间最后真实成交估值。','这些差额不能直接加到实际账户收益：影子不占用实际账户，不执行后续CORE，不模拟整条可执行替代资金路径。','','|组|费用|主动退出样本|估计失去收益USDT|估计避免损失USDT|实际减影子合计USDT|','|---|---|---:|---:|---:|---:|']
 for g in('H','I'):
  for c in z.COSTS:
   use=[x for x in rows if x['group']==g and x['cost']==c]
   lines.append(f"|{g}|{c}|{len(use)}|{sum(x['estimated_foregone_profit']for x in use):.2f}|{sum(x['estimated_avoided_loss']for x in use):.2f}|{sum(x['actual_minus_shadow']for x in use):+.2f}|")
 lines+=['','失败记录：'+json.dumps(fail,ensure_ascii=False)]
 (OUT/'shadow_summary.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--period');parser.add_argument('--group');parser.add_argument('--cost');args=parser.parse_args()
 if args.period:
  try:run(args.period,args.group,args.cost)
  except Exception as error:
   f=OUT/'shadows'/args.period/args.cost/args.group;f.mkdir(parents=True,exist_ok=True);z.dump(f/'failure.json',dict(error=repr(error),traceback=traceback.format_exc()));raise
 else:
  locate=z.module('priority_collect_locator',OUT/'collect.py').locate
  import subprocess
  jobs=[]
  for period in z.PERIODS:
   for g in('H','I'):
    for cost in z.COSTS:
     try:locate(period,'ETH',cost,g)
     except FileNotFoundError:continue
     jobs.append((period,g,cost))
  def job(item):
   period,g,cost=item;folder=OUT/'shadows'/period/cost/g;folder.mkdir(parents=True,exist_ok=True)
   with(folder/'run.log').open('w')as log:result=subprocess.run([sys.executable,str(OUT/'shadows.py'),'--period',period,'--group',g,'--cost',cost],stdout=log,stderr=subprocess.STDOUT)
   return result.returncode
  with ThreadPoolExecutor(max_workers=3)as pool:codes=list(pool.map(job,jobs))
  collect();print('SHADOWS',len(jobs),'tasks',sum(c!=0 for c in codes),'failures')
