from pathlib import Path
import sys,json,csv,ast,datetime
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];BASE=R/'outputs/adaptive_density_control';tree=ast.parse((BASE/'report.py').read_text());wanted=['metrics','trade_key','open_key','reason','attribute','csvwrite'];ns=dict(np=np,json=json,csv=csv,comparison=[],matches=[]);exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in wanted],type_ignores=[]),'<original matching functions>','exec'),ns)
original_reason=ns['reason']
def classified_reason(q,stamp,side,accepted):
 group=q['configuration']['group']
 if group.startswith('E3_')and accepted.get(stamp)!=side and maps[q['asset']]['E2_'+group.split('_')[1]].get(stamp)==side:return 'MACRO_COOLDOWN'
 return original_reason(q,stamp,side,accepted)
ns['reason']=classified_reason
rows=[];trades=[];missing=[];checks=[];removed=[]
groups=['A','B','D','E1','E2_030','E2_035','E3_030','E3_035'];fees=['ZERO','ASSUMED_005_SIDE'];periods=[str(y)for y in range(2020,2027)]
for period in periods:
 for fee in fees:
  acc={};maps={}
  for asset in ['BTC','ETH']:
   folder=O/'runs'/period/asset
   if not(folder/'signals.json').exists()or not(folder/'status.json').exists():continue
   mm=json.loads((folder/'signals.json').read_text())['accepted'];maps[asset]={k:{int(t):v for t,v in a.items()}for k,a in mm.items()}
   for group in groups:
    path=folder/f'{fee}_{group}_result.json'
    if not path.exists():missing.append(dict(period=period,asset=asset,fee=fee,group=group,status='NOT_COMPLETED'));continue
    q=json.loads(path.read_text());curve=np.load(folder/f'{fee}_{group}_equity.npz')['marks'];acc[asset,group]=(q,curve);p=q['state_at_end']['position'];ef=q['fee']*p['order']['price']*p['order']['qty']if p else 0.;unreal=p['order']['side']*p['order']['qty']*(q['mark_price']-p['order']['price'])if p else 0.;a=q['cash']-500-sum(t['net']for t in q['trades'])+ef;b=q['ending_equity']-q['cash']-unreal;assert abs(a)<1e-7 and abs(b)<1e-7;checks.append(dict(period=period,asset=asset,fee=fee,group=group,cash_residual=a,equity_residual=b))
    rows.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**ns['metrics'](curve,500,q['trades']),net_pnl_USDT=q['ending_equity']-500,realized_closed_net_USDT=sum(t['net']for t in q['trades']),open_count=int(bool(p)),execution=q['status']))
    for t in q['trades']:trades.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**t))
    if group!='A'and(asset,'A')in acc:
     ns['attribute']('ANNUAL_1M_OHLC',period,asset,fee,group,acc[asset,'A'][0],q,maps[asset]['A'],maps[asset][group])
   if(folder/'signal_check.json').exists():removed.append(dict(period=period,asset=asset,**json.loads((folder/'signal_check.json').read_text())['removed_from_A']))
  for group in groups:
   if('BTC',group)not in acc or('ETH',group)not in acc:continue
   a,av=acc['BTC',group];b,bv=acc['ETH',group];assert len(av)==len(bv);tt=a['trades']+b['trades'];rows.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,**ns['metrics'](av+bv,1000,tt),net_pnl_USDT=a['ending_equity']+b['ending_equity']-1000,realized_closed_net_USDT=sum(t['net']for t in tt),open_count=sum(int(bool(q['state_at_end']['position']))for q in [a,b]),execution='COMPLETED_WITH_1M_OHLC_ASSUMPTIONS'))
totals=[]
for fee in fees:
 for group in groups:
  rr=[r for r in rows if r['asset']=='COMBINED'and r['fee_scenario']==fee and r['group']==group]
  tt=[t for t in trades if t['fee_scenario']==fee and t['group']==group]
  totals.append(dict(fee_scenario=fee,group=group,completed_intervals=len(rr),net_pnl_USDT=sum(r['net_pnl_USDT']for r in rr),return_on_sum_reset_capital_pct=sum(r['net_pnl_USDT']for r in rr)/(len(rr)*1000)*100 if rr else None,closed_trades=len(tt),win_rate_pct=100*sum(t['net']>0 for t in tt)/len(tt)if tt else None,worst_annual_max_drawdown_pct=max([r['max_drawdown_pct']for r in rr],default=None),not_continuous_compounding=True))
done_keys={(str(x['period']),x['asset'],x['fee'],x['group'])for x in checks}
missing=[dict(period=p,asset=a,fee=f,group=g,status='NOT_COMPLETED')for p in periods for a in ['BTC','ETH']for f in fees for g in groups if(p,a,f,g)not in done_keys]
for name,rs in [('annual.csv',rows),('totals.csv',totals),('trades.csv',trades),('trade_matching.csv',ns['matches']),('signal_attribution.csv',ns['comparison']),('removed_signals.csv',removed),('cash_checks.csv',checks),('incomplete.csv',missing)]:ns['csvwrite'](O/name,rs)
text='# 动态挤压阈值保底/钳位/宏观冷却：K线对照\n\n'
text+='本次为1m OHLC假设打印路径上的完整账户回放，不是真实逐笔、实盘成交或严格最坏/最好情况。所有A/B/D与新组同口径重跑；旧RAW结果不充当此表基准。\n\nE1/E2只修改历史挤压阈值，当前震荡带宽仍动态，因此不保证保留全部A信号；E3还主动过滤宏观窗口。E2分别测试0.30/0.35，E3分别套用，无额外搜索。\n\n2020从2月16日起，2026仅1—10月；2021—2025全年。年度各币500独立起算、3x滚仓，资金费0、退出滑点0.02%，无V2/反弹续跌、pause_transition=True。\n\n'
for fee in fees:
 text+='## '+fee+'\n\n|年|组|净盈亏USDT|已平笔数|胜率%|最大回撤%|\n|---|---|---:|---:|---:|---:|\n'
 for r in rows:
  if r['asset']=='COMBINED'and r['fee_scenario']==fee:text+=f"|{r['period']}|{r['group']}|{r['net_pnl_USDT']:.2f}|{r['closed_trades']}|{r['win_rate_pct'] or 0:.2f}|{r['max_drawdown_pct']:.2f}|\n"
 text+='\n|组|完成区间|独立年度损益合计|交易数|胜率%|最差年度回撤%|\n|---|---:|---:|---:|---:|---:|\n'
 for r in totals:
  if r['fee_scenario']==fee and r['completed_intervals']:text+=f"|{r['group']}|{r['completed_intervals']}/7|{r['net_pnl_USDT']:.2f}|{r['closed_trades']}|{r['win_rate_pct'] or 0:.2f}|{r['worst_annual_max_drawdown_pct']:.2f}|\n"
text+='\n总计不是跨年复利，回撤没有将年度重置拼接。net_pnl包含期末未平仓估值；realized_closed_net另列。费用为假设费率，未含资金费。宏观窗口已被事后查看选择，本轮非新样本外。ADAPTIVE_SIGNAL_REMOVED是信号过滤，不等于占仓；新增盈利不能简单加回旧账户。\n\n'
text+=f"已对账账户{len(checks)}，未完成账户{len(missing)}；未完成不填零。逐笔与A配对格式沿用原report.py函数，见trade_matching.csv。\n"
(O/'CONCLUSION.md').write_text(text)
print(json.dumps(dict(accounts=len(checks),combined_rows=sum(r['asset']=='COMBINED'for r in rows),matching_rows=len(ns['matches']),incomplete=len(missing))))
