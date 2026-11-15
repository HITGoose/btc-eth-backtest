from pathlib import Path
import csv,json,ast,datetime
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];BASE=R/'outputs/adaptive_density_control';tree=ast.parse((BASE/'report.py').read_text());ns=dict(np=np,json=json,csv=csv,comparison=[],matches=[]);exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['metrics','trade_key','open_key','reason','attribute','csvwrite']],type_ignores=[]),'<original matching functions>','exec'),ns)
original_reason=ns['reason']
def reason(q,stamp,side,accepted):
 if accepted.get(stamp)!=side:return 'MACRO_COOLDOWN'
 return original_reason(q,stamp,side,accepted)
ns['reason']=reason
GROUPS=['A','A_MACRO_60','A_FOMC_60'];FEES=['ZERO','ASSUMED_005_SIDE'];PERIODS=[str(y)for y in range(2020,2027)]
rows=[];trades=[];checks=[];follow=[];decomp=[];signalrows=[]
def occupancy(q,stamp):
 clock=(stamp+10000)*1000
 for t in q['trades']:
  if t['opened_us']<=clock<t['closed_us']:return 'BASE_OCCUPIED_POSITION',dict(signal_close_ms=t['signal_close_ms'],opened_us=t['opened_us'],closed_us=t['closed_us'],entry=t['entry'])
 st=q['state_at_end']
 if st['position']and st['position_opened_us']<=clock:return 'BASE_OCCUPIED_OPEN_POSITION',dict(opened_us=st['position_opened_us'],order=st['position']['order'])
 for e in q['events']:
  if e['event']!='order_sent'or not(e['time_us']<=clock<e['time_us']+3600000000):continue
  sig=int(e.get('signal_close_ms',e['time_us']//1000-10000))
  filled=any(f['event']=='limit_touch_proxy_fill'and e['time_us']<=f['time_us']<=clock and int(f.get('signal_close_ms',-1))==sig for f in q['events'])
  if not filled:return 'BASE_OCCUPIED_PENDING_ORDER',dict(signal_close_ms=sig,submitted_us=e['time_us'],expiry_us=e['time_us']+3600000000)
 return 'NO_DIRECT_OCCUPANCY_EVIDENCE',None
def validate(q,v):
 pos=q['state_at_end']['position'];entryfee=q['fee']*pos['order']['price']*pos['order']['qty']if pos else 0.;unreal=pos['order']['side']*pos['order']['qty']*(q['mark_price']-pos['order']['price'])if pos else 0.;res=q['cash']-500-sum(t['net']for t in q['trades'])+entryfee;er=q['ending_equity']-q['cash']-unreal;cr=q['cash']-500-sum(e['delta']for e in q['cash_events']);assert max(abs(res),abs(er),abs(cr),abs(v[-1]-q['ending_equity']))<1e-7
 return dict(cash_residual=res,equity_residual=er,cash_events_residual=cr)
for period in PERIODS:
 for fee in FEES:
  accounts={};maps={}
  for asset in ['BTC','ETH']:
   folder=O/'runs'/period/asset
   if not(folder/'status.json').exists():continue
   mm=json.loads((folder/'signals.json').read_text());maps[asset]={g:{int(t):v for t,v in a.items()}for g,a in mm['accepted'].items()}
   for group in GROUPS:
    path=folder/f'{fee}_{group}_result.json';q=json.loads(path.read_text());v=np.load(folder/f'{fee}_{group}_equity.npz')['marks'];checks.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**validate(q,v)));accounts[asset,group]=(q,v)
    rows.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**ns['metrics'](v,500,q['trades']),net_pnl_USDT=q['ending_equity']-500,realized_closed_net_USDT=sum(t['net']for t in q['trades']),open_count=int(bool(q['state_at_end']['position'])),execution=q['status'],baseline_reused=group=='A'))
    for t in q['trades']:trades.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**t))
    if group=='A':continue
    a=accounts[asset,'A'][0];ns['attribute']('ANNUAL',period,asset,fee,group,a,q,maps[asset]['A'],maps[asset][group]);ak={ns['trade_key'](t):t for t in a['trades']};vk={ns['trade_key'](t):t for t in q['trades']};new=[t for k,t in vk.items()if k not in ak];lost=[t for k,t in ak.items()if k not in vk];matched=sum(vk[k]['net']-t['net']for k,t in ak.items()if k in vk);newnet=sum(t['net']for t in new);lostnet=sum(t['net']for t in lost);open_delta=(q['ending_equity']-500-sum(t['net']for t in q['trades']))-(a['ending_equity']-500-sum(t['net']for t in a['trades']));delta=q['ending_equity']-a['ending_equity'];assert abs(delta-newnet+lostnet-matched-open_delta)<1e-7
    decomp.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,equity_difference_USDT=delta,new_closed_net_USDT=newnet,absent_A_closed_net_USDT=lostnet,matched_net_change_USDT=matched,open_contribution_change_USDT=open_delta,reconciliation_residual=delta-newnet+lostnet-matched-open_delta))
    for t in new:
     key=ns['trade_key'](t);cause,evidence=occupancy(a,t['signal_close_ms']);was_open=key==ns['open_key'](a)
     if was_open:cause='BASE_SAME_SIGNAL_OPEN_AT_END'
     assert maps[asset]['A'].get(t['signal_close_ms'])==(1 if t['side']=='LONG'else-1)
     follow.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,cause=cause,baseline_evidence=evidence,proved_freed_occupancy=cause.startswith('BASE_OCCUPIED'),baseline_same_signal_open_at_end=was_open,signal_was_already_in_original_A=True,**t))
   if fee=='ZERO':
    for g in GROUPS[1:]:signalrows.append(dict(period=period,asset=asset,group=g,A_complete_signals=len(maps[asset]['A']),accepted_signals=len(maps[asset][g]),macro_removed_complete_signals=len(maps[asset]['A'])-len(maps[asset][g])))
  for group in GROUPS:
   if('BTC',group)not in accounts or('ETH',group)not in accounts:continue
   a,av=accounts['BTC',group];b,bv=accounts['ETH',group];assert a['window']==b['window']and len(av)==len(bv);tt=a['trades']+b['trades'];rows.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,**ns['metrics'](av+bv,1000,tt),net_pnl_USDT=a['ending_equity']+b['ending_equity']-1000,realized_closed_net_USDT=sum(t['net']for t in tt),open_count=sum(int(bool(x['state_at_end']['position']))for x in [a,b]),execution='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS',baseline_reused=group=='A'))
# Add exact annual deltas for every asset and the combined wallet.
base={(r['period'],r['asset'],r['fee_scenario']):r for r in rows if r['group']=='A'}
for r in rows:
 a=base[r['period'],r['asset'],r['fee_scenario']];r.update(net_difference_vs_A_USDT=r['net_pnl_USDT']-a['net_pnl_USDT'],max_drawdown_difference_vs_A_pp=r['max_drawdown_pct']-a['max_drawdown_pct'],closed_count_difference_vs_A=r['closed_trades']-a['closed_trades'])
totals=[];summ=[]
for fee in FEES:
 for group in GROUPS:
  rr=[r for r in rows if r['asset']=='COMBINED'and r['fee_scenario']==fee and r['group']==group];tt=[t for t in trades if t['fee_scenario']==fee and t['group']==group];totals.append(dict(fee_scenario=fee,group=group,completed_intervals=len(rr),net_pnl_USDT=sum(r['net_pnl_USDT']for r in rr),net_difference_vs_A_USDT=sum(r['net_difference_vs_A_USDT']for r in rr),closed_trades=len(tt),win_rate_pct=100*sum(t['net']>0 for t in tt)/len(tt)if tt else None,worst_annual_max_drawdown_pct=max([r['max_drawdown_pct']for r in rr],default=None),years_net_improved=sum(r['net_difference_vs_A_USDT']>1e-8 for r in rr),years_drawdown_increased=sum(r['max_drawdown_difference_vs_A_pp']>1e-8 for r in rr),not_continuous_compounding=True))
  if group=='A':continue
  ff=[t for t in follow if t['fee_scenario']==fee and t['group']==group];proved=[t for t in ff if t['proved_freed_occupancy']];summ.append(dict(fee_scenario=fee,group=group,new_closed_records=len(ff),new_closed_net_USDT=sum(t['net']for t in ff),proved_freed_occupancy_trades=len(proved),proved_freed_occupancy_wins=sum(t['net']>0 for t in proved),proved_freed_occupancy_losses=sum(t['net']<0 for t in proved),proved_freed_occupancy_net_USDT=sum(t['net']for t in proved),not_proven_or_open_count=len(ff)-len(proved),not_additive_counterfactual=True))
for m in ns['matches']:
 m['execution_assumption']='SYNTHETIC_1M_OHLC'
 if m['category']=='NEW':
  f=next(t for t in follow if(t['period'],t['asset'],t['fee_scenario'],t['group'],t['side'],t['signal_close_ms'])==(m['period'],m['asset'],m['fee_scenario'],m['group'],m['side'],m['signal_close_ms']));m.update(new_trade_cause=f['cause'],proved_freed_occupancy=f['proved_freed_occupancy'])
done={(r['period'],r['asset'],r['fee_scenario'],r['group'])for r in checks};missing=[dict(period=p,asset=a,fee_scenario=f,group=g,status='NOT_COMPLETED')for p in PERIODS for a in ['BTC','ETH']for f in FEES for g in GROUPS if(p,a,f,g)not in done]
for n,rs in [('annual.csv',rows),('totals.csv',totals),('trades.csv',trades),('trade_matching.csv',ns['matches']),('signal_attribution.csv',ns['comparison']),('followup_trades.csv',follow),('followup_summary.csv',summ),('account_difference_reconciliation.csv',decomp),('cash_checks.csv',checks),('signal_counts.csv',signalrows),('incomplete.csv',missing)]:ns['csvwrite'](O/n,rs)
text='# 固定A叠加宏观冷却\n\n原A固定历史挤压0.25%、震荡当前带宽0.50%，原算式未改，无动态带宽，无V2。仅屏蔽完整A信号。已有挂单/持仓不撤销或强平。主执行沿前轮15m信号+1m OHLC假设路径，不是真实逐笔。\n\n2020从2月16日起，2021—2025全年，2026仅1—10月。北京时间年度边界、各币500独立重置，3x滚仓，资金费0，退出滑点0.02%。A经源代码、缓存、信号及账本指纹核对后复用；两个新组完整回放。\n\n宏观窗口按signal_close_ms落入[发布,发布+60分钟]，含两端。常规CPI08:30ET、FOMC14:00ET；紧急FOMC2020-03-03实际10:00EST=15:00UTC，2020-03-15实际17:00EDT=21:00UTC，非14:00。纽约时区自动处理DST。\n\n'
for fee in FEES:
 text+='## '+fee+'\n\n|年|组|净盈亏USDT|相对A差额|已平笔数|胜率%|最大回撤%|回撤差pp|\n|---|---|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:
  if r['fee_scenario']==fee and r['asset']=='COMBINED':text+=f"|{r['period']}|{r['group']}|{r['net_pnl_USDT']:.2f}|{r['net_difference_vs_A_USDT']:+.2f}|{r['closed_trades']}|{r['win_rate_pct'] or 0:.2f}|{r['max_drawdown_pct']:.2f}|{r['max_drawdown_difference_vs_A_pp']:+.2f}|\n"
 text+='\n|组|区间数|七期净额|相对A差额|已平笔数|胜率%|最差年度回撤%|收益改善区间|回撤增大区间|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in totals:
  if r['fee_scenario']==fee and r['completed_intervals']:text+=f"|{r['group']}|{r['completed_intervals']}/7|{r['net_pnl_USDT']:.2f}|{r['net_difference_vs_A_USDT']:+.2f}|{r['closed_trades']}|{r['win_rate_pct'] or 0:.2f}|{r['worst_annual_max_drawdown_pct']:.2f}|{r['years_net_improved']}|{r['years_drawdown_increased']}|\n"
text+='\n## 仓位释放后的接续交易\n\nNEW按资产/方向/signal_close_ms匹配已有A账本；没有新增入场指标或信号。只对A在原定提交时点有实际持仓/挂单证据的NEW认定为已证实占仓释放，其余保持未证实或A期末原未平。\n\n|费用|组|NEW已平数/净额|证实占仓释放笔数|赢/亏|证实接续净额USDT|\n|---|---|---:|---:|---:|---:|\n'
for r in summ:text+=f"|{r['fee_scenario']}|{r['group']}|{r['new_closed_records']} / {r['new_closed_net_USDT']:.2f}|{r['proved_freed_occupancy_trades']}|{r['proved_freed_occupancy_wins']} / {r['proved_freed_occupancy_losses']}|{r['proved_freed_occupancy_net_USDT']:.2f}|\n"
text+='\n接续单盈亏只是归因，不是可直接相加的账户改善。account_difference_reconciliation.csv核对：期末权益差=新增已平净额−原缺失已平净额+匹配单净额变化+期末未平贡献变化。没有把独立NEW单利润直接加回A。总净额含期末未平估值，已平净额另列；最大回撤按分钟权益，七期合计仅相加独立年度USDT，不拼接跨年复利或虚构跨年回撤。\n\n窗口依据反复观察的历史选定，不称新样本外，不据少数年度直接宣布实盘替换。手续费0.05%为每边假设，资金费0，触价全量与OHLC顺序均为模拟代理。2025未加载冲突逐笔档案，不声称修复或验证了官方逐笔。\n'
text+=f'\n已对账账户{len(checks)}/84（含28个复用A），未完成{len(missing)}。原main与策略未改，独立分支codex/a-macro-cooldown-20261115。\n';(O/'CONCLUSION.md').write_text(text)
print(json.dumps(dict(accounts=len(checks),incomplete=len(missing),combined_rows=sum(r['asset']=='COMBINED'for r in rows),matching=len(ns['matches']))))
