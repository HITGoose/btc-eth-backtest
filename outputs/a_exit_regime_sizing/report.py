from pathlib import Path
import csv,json,ast
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];T=ast.parse((R/'outputs/adaptive_density_control/report.py').read_text());ns=dict(np=np,json=json,csv=csv,comparison=[],matches=[]);exec(compile(ast.Module(body=[n for n in T.body if isinstance(n,ast.FunctionDef)and n.name in ['metrics','csvwrite','trade_key','open_key','reason','attribute']],type_ignores=[]),'<original report functions>','exec'),ns)
GROUPS=['A_BASE','A_EXIT_UNCAPPED','A_EXIT_TRAIL8','A_REGIME_SIZE'];FEES=['ZERO','ASSUMED_005_SIDE','MAKER_002_SIDE'];PERIODS=[str(y)for y in range(2020,2027)];inv=json.loads((O/'input_inventory.json').read_text());rows=[];trades=[];checks=[];risk=[];signalchecks=[]
def gross(q,v,info):
 qty=np.zeros(len(v));start=info['start'];end=info['end'];end_us=end*1000000;items=[(t['opened_us'],t['closed_us'],t['quantity'])for t in q['trades']];p=q['state_at_end']
 if p['position']:items.append((p['position_opened_us'],end_us,p['position']['order']['qty']))
 for a,b,size in items:qty[max(0,int(a//60000000-start//60)):min(len(qty),int(b//60000000-start//60))]=size
 raw=np.load(Path(info['data'])/(q['asset']+'_1m.npy'),mmap_mode='r');lo=(start-info['minute_first'])//60;return qty*raw[lo:lo+len(qty),3]
def account(q,v):
 p=q['state_at_end']['position'];ef=q['fee']*p['order']['price']*p['order']['qty']if p else 0.;un=p['order']['side']*p['order']['qty']*(q['mark_price']-p['order']['price'])if p else 0.;a=q['cash']-500-sum(t['net']for t in q['trades'])+ef;b=q['ending_equity']-q['cash']-un;c=q['cash']-500-sum(t['delta']for t in q['cash_events']);assert max(abs(a),abs(b),abs(c),abs(v[-1]-q['ending_equity']))<1e-7;return dict(cash_residual=a,equity_residual=b,cash_events_residual=c)
for period in PERIODS:
 for fee in FEES:
  acc={};maps={}
  for asset in ['BTC','ETH']:
   folder=O/'runs'/period/asset
   if not(folder/'status.json').exists():continue
   core={int(t):s for t,s in json.loads((folder/'signals.json').read_text())['A'].items()};maps[asset]=core
   for group in GROUPS:
    path=folder/f'{fee}_{group}_result.json';q=json.loads(path.read_text());v=np.load(folder/f'{fee}_{group}_equity.npz')['marks'];checks.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**account(q,v)));gg=gross(q,v,inv[period+'_'+asset]);acc[asset,group]=(q,v,gg)
    for t in q['trades']:assert core.get(t['signal_close_ms'])==(1 if t['side']=='LONG'else-1)
    rows.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,exit_policy=q['configuration']['exit_policy'],**ns['metrics'](v,500,q['trades']),net_pnl_USDT=q['ending_equity']-500,cash_USDT=q['cash'],closed_net_USDT=sum(t['net']for t in q['trades']),end_unrealized_USDT=q['ending_equity']-q['cash'],open_count=int(bool(q['state_at_end']['position'])),actual_replayed_this_round=q['actual_replayed_this_round'],source=q['status']))
    for t in q['trades']:trades.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**t))
    audits=q['sizing_audit'];requested=[a.get('requested_weight',1.)for a in audits if a.get('accepted')];risk.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**q['exposure'],mean_submitted_weight=float(np.mean(requested))if requested else None,min_notional_rejects=q.get('stats',{}).get('rejected',0)))
    if group!='A_BASE':ns['attribute']('ANNUAL',period,asset,fee,group,acc[asset,'A_BASE'][0],q,core,core)
   if fee=='ZERO':signalchecks.append(dict(period=period,asset=asset,signals=len(core),all_groups_identical_complete_signals=True,filled_signals_all_in_core=True))
  for group in GROUPS:
   if('BTC',group)not in acc or('ETH',group)not in acc:continue
   a,av,ag=acc['BTC',group];b,bv,bg=acc['ETH',group];assert a['window']==b['window']and len(av)==len(bv);v=av+bv;gg=ag+bg;tt=a['trades']+b['trades'];rows.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,exit_policy=a['configuration']['exit_policy'],**ns['metrics'](v,1000,tt),net_pnl_USDT=a['ending_equity']+b['ending_equity']-1000,cash_USDT=a['cash']+b['cash'],closed_net_USDT=sum(t['net']for t in tt),end_unrealized_USDT=a['ending_equity']+b['ending_equity']-a['cash']-b['cash'],open_count=sum(int(bool(q['state_at_end']['position']))for q in [a,b]),source='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS'))
   held=gg>0;lev=np.divide(gg,v,out=np.full(len(v),np.nan),where=v>0);risk.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,duration_weighted_entry_notional_USDT=a['exposure']['duration_weighted_entry_notional_USDT']+b['exposure']['duration_weighted_entry_notional_USDT'],minute_end_avg_gross_notional_USDT=float(np.mean(gg)),minute_end_avg_gross_equity_leverage=float(np.nanmean(lev)),minute_end_avg_leverage_when_held=float(np.mean(lev[held]))if held.any()else 0.,max_minute_end_gross_equity_leverage=float(np.nanmax(lev))))
base={(r['period'],r['asset'],r['fee_scenario']):r for r in rows if r['group']=='A_BASE'};rb={(r['period'],r['asset'],r['fee_scenario']):r for r in risk if r['group']=='A_BASE'}
for r in rows:
 b=base[r['period'],r['asset'],r['fee_scenario']];r.update(net_difference_vs_A_BASE_USDT=r['net_pnl_USDT']-b['net_pnl_USDT'],max_drawdown_difference_vs_A_BASE_pp=r['max_drawdown_pct']-b['max_drawdown_pct'],closed_count_difference_vs_A_BASE=r['closed_trades']-b['closed_trades'])
for r in risk:
 b=rb[r['period'],r['asset'],r['fee_scenario']]
 for k in ['minute_end_avg_gross_equity_leverage','duration_weighted_entry_notional_USDT']:
  r[k+'_ratio_vs_A_BASE']=r[k]/b[k]if b[k]else None
sums=[]
for fee in FEES:
 for group in GROUPS:
  rr=[r for r in rows if r['fee_scenario']==fee and r['group']==group and r['asset']=='COMBINED'];tt=[r for r in trades if r['fee_scenario']==fee and r['group']==group];sums.append(dict(fee_scenario=fee,group=group,completed_intervals=len(rr),net_pnl_USDT=sum(r['net_pnl_USDT']for r in rr),closed_net_USDT=sum(r['closed_net_USDT']for r in rr),end_unrealized_USDT=sum(r['end_unrealized_USDT']for r in rr),net_difference_vs_A_BASE_USDT=sum(r['net_difference_vs_A_BASE_USDT']for r in rr),closed_trades=len(tt),win_rate_pct=100*sum(t['net']>0 for t in tt)/len(tt)if tt else None,worst_annual_max_drawdown_pct=max([r['max_drawdown_pct']for r in rr],default=None),years_net_improved=sum(r['net_difference_vs_A_BASE_USDT']>1e-8 for r in rr),years_drawdown_increased=sum(r['max_drawdown_difference_vs_A_BASE_pp']>1e-8 for r in rr),not_continuous_compounding=True))
done={(r['period'],r['asset'],r['fee_scenario'],r['group'])for r in checks};missing=[dict(period=p,asset=a,fee_scenario=f,group=g,status='NOT_COMPLETED')for p in PERIODS for a in ['BTC','ETH']for f in FEES for g in GROUPS if(p,a,f,g)not in done]
for row in ns['matches']:row.update(execution_assumption='SYNTHETIC_1M_OHLC',baseline_group='A_BASE')
for name,rs in [('annual.csv',rows),('totals.csv',sums),('trades.csv',trades),('exposure.csv',risk),('cash_checks.csv',checks),('signal_checks.csv',signalchecks),('trade_matching.csv',ns['matches']),('signal_attribution.csv',ns['comparison']),('incomplete.csv',missing)]:ns['csvwrite'](O/name,rs)
text='# 固定A入场：出场与顺势仓位实验\n\n本轮A_BASE是5档锁利封顶fixed。此前报告A已经是uncapped，不能混用；本轮uncapped部分账本仅在来源/信号/数据/费用一致时复用。固定A历史0.25%、震荡当前0.50%、原ER/六线/MACD/支撑阻力/过渡期均不改，不叠加宏观过滤、V2或动态带宽。\n\n5档表示止损最多锁利5%，不是涨到5%立即全平。trail_from_8pct表示有利幅度达到8%后解除封顶、继续无上限，不是8档上限。仓位组使用fixed出场，信号时顺120hER方向乘1.3，其他乘0.7，不能预先称为等风险。\n\n原3x、各币500独立年度重置、零资金费、0.02%退出滑点，15m信号+1m OHLC假设打印，5秒相位2轮询。2020仅02-16起、2021—2025全年、2026仅1—10月。不是实际逐笔或新样本外。\n\n'
for fee in FEES:
 text+='## '+fee+'\n\n|年|组|净盈亏USDT|相对A_BASE|已平笔数|胜率%|最大回撤%|回撤差pp|\n|---|---|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:
  if r['asset']=='COMBINED'and r['fee_scenario']==fee:text+=f"|{r['period']}|{r['group']}|{r['net_pnl_USDT']:.2f}|{r['net_difference_vs_A_BASE_USDT']:+.2f}|{r['closed_trades']}|{r['win_rate_pct'] or 0:.2f}|{r['max_drawdown_pct']:.2f}|{r['max_drawdown_difference_vs_A_BASE_pp']:+.2f}|\n"
 text+='\n|组|完成区间|七期合计|相对A_BASE|已平笔数|胜率%|最差年度回撤%|跑赢区间|回撤增大区间|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in sums:
  if r['fee_scenario']==fee and r['completed_intervals']:text+=f"|{r['group']}|{r['completed_intervals']}/7|{r['net_pnl_USDT']:.2f}|{r['net_difference_vs_A_BASE_USDT']:+.2f}|{r['closed_trades']}|{r['win_rate_pct'] or 0:.2f}|{r['worst_annual_max_drawdown_pct']:.2f}|{r['years_net_improved']}|{r['years_drawdown_increased']}|\n"
text+='\n## 仓位权重的实际风险\n\n平均风险没有用未来全年数据强行归一化。以下相对A_BASE的分钟末平均组合gross/equity杠杆比值同时反映持仓时间和仓位；不是单看1.3/0.7的算术中点。时间加权初始名义、持仓时杠杆及分币数据见exposure.csv。\n\n|年|费用|仓位组平均组合杠杆|A_BASE|比值|\n|---|---|---:|---:|---:|\n'
for r in risk:
 if r['asset']=='COMBINED'and r['group']=='A_REGIME_SIZE':
  b=rb[r['period'],r['asset'],r['fee_scenario']];text+=f"|{r['period']}|{r['fee_scenario']}|{r['minute_end_avg_gross_equity_leverage']:.4f}|{b['minute_end_avg_gross_equity_leverage']:.4f}|{r['minute_end_avg_gross_equity_leverage_ratio_vs_A_BASE']:.4f}|\n"
text+='\nMAKER_002_SIDE统一把每边费率设0.02%，只是用户指定的低费率假设；没有核实用户真实费率。限价不保证Maker，止损退出也不保证Maker，因此不能当作真实实盘成本。ZERO/0.05%/0.02%均完整账户路径，不是期末简单加回费用。\n\n净盈亏为期末权益变化，包含未平浮盈亏，未预扣未来平仓费；annual.csv另列cash_USDT、closed_net_USDT、end_unrealized_USDT、open_count。所有信号完全不变，但出场占仓、余额变化和最小名义限制会改变实际交易笔数；不能把这些当成主动删除入场信号。完整成交与差异见trades.csv及trade_matching.csv，后者沿旧字段名A_net，实际A为本轮A_BASE。所有年度独立，合计仅相加USDT，回撤取最差年度，不造跨年复利回撤。\n'
text+=f'\n已完成对账{len(checks)}/168；未完成{len(missing)}。新回放140账户，复用uncapped28账户。\n';(O/'CONCLUSION.md').write_text(text);print(json.dumps(dict(accounts=len(checks),incomplete=len(missing),combined_rows=sum(r['asset']=='COMBINED'for r in rows))))
