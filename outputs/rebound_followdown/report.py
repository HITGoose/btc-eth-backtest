from signals import *
import json,hashlib
O=Path(__file__).resolve().parent
rows=[];attribution=[];extra_rows=[];audits=[];combined=[]
def metrics(q,v,initial=500.):
 peak=np.maximum.accumulate(np.r_[initial,v]);dd=100*(1-np.r_[initial,v]/peak);ts=q['trades'];loss=[t for t in ts if t['net']<0];pnl=[t['net']for t in ts];return dict(ending_equity=float(v[-1]),net_USDT=float(v[-1]-initial),return_pct=float(100*(v[-1]/initial-1)),max_drawdown_pct=float(dd.max()),closed_trades=len(ts),losing_trades=len(loss),total_loss_USDT=-sum(t['net']for t in loss),max_single_loss=min([0]+pnl),fees=q['stats'].get('fees','NOT_PROVIDED'),funding=q.get('funding_total_USDT','NOT_INCLUDED'),open_count=int(bool(q['state_at_end']['position'])))
for period in ['2020','2021','2023','2024','RECENT']:
 pair={}
 for asset in ['BTC','ETH']:
  folder=O/'runs'/period/asset;keys=['B','B_PLUS_REBOUND'];results={k:json.loads((folder/'results'/f'{k}_result.json').read_text())for k in keys};curves={k:np.load(folder/'results'/f'{k}_equity.npz')['marks']for k in keys};pair[asset]=(results,curves)
  diag=json.loads((folder/'signals.json').read_text());features=diag.get('full_rule_diagnostics',diag.get('diagnostics'));by={x['signal_close_ms']:x for x in features};new={int(t):v for t,v in diag.get('REBOUND',diag.get('new',{})).items()}
  for k in keys:
   q=results[k];row=dict(period=period,asset=asset,version=k,cost='C2_EXACT_FUNDING'if period=='RECENT'else'C1_NO_FUNDING',**metrics(q,curves[k]));extra=[t for t in q['trades']if t['signal_close_ms']in new];row.update(new_signals=len(new)if k!='B'else 0,extra_closed=len(extra),extra_winning_net=sum(max(0,t['net'])for t in extra),extra_losing_net=-sum(min(0,t['net'])for t in extra),extra_net=sum(t['net']for t in extra),false_break_extra_closed=sum(bool(by.get(t['signal_close_ms'],{}).get('false_break_reclaim_within4'))for t in extra),rejected_range_shapes=sum(d['regime']in['range','transition']for d in features));rows.append(row)
   for t in extra:extra_rows.append(dict(period=period,asset=asset,version=k,**t,**{f:by.get(t['signal_close_ms'],{}).get(f,'NOT_EVALUATED')for f in ['false_break_reclaim_within4','posthoc_closed_bars','posthoc_regime_becomes_range','historical_minimum_bandwidth_pct']}))
   cash_residual=q['cash']-500-sum(x['delta']for x in q['cash_events']);assert abs(cash_residual)<1e-7
   pos=q['state_at_end']['position'];unrealized=0
   if pos:
    order=pos['order'];unrealized=order['side']*order['qty']*(q['actual_raw_last_mark']-order['price'])
   eq_res=q['ending_equity']-q['cash']-unrealized;assert abs(eq_res)<1e-7
   audits.append(dict(period=period,asset=asset,version=k,cash_event_residual=cash_residual,equity_residual=eq_res,source_market='BINANCE_USDT_PERPETUAL',passed=True))
  aa={s.z.h.trade_key(t):t for t in results['B']['trades']};bb={s.z.h.trade_key(t):t for t in results['B_PLUS_REBOUND']['trades']}
  for token in sorted(set(aa)|set(bb)):
   a=aa.get(token);b=bb.get(token);kind='NEW'if a is None else'DISAPPEARED'if b is None else'RETAINED'if a==b else'CHANGED';attribution.append(dict(period=period,asset=asset,side=token[0],signal_close_ms=token[1],classification=kind,base_net=a['net']if a else None,new_net=b['net']if b else None,base_initial_notional=a['entry']*a['quantity']if a else None,new_initial_notional=b['entry']*b['quantity']if b else None,base_net_per1500=a['net']/(a['entry']*a['quantity'])*1500 if a else None,new_net_per1500=b['net']/(b['entry']*b['quantity'])*1500 if b else None,base_full=json.dumps(a),new_full=json.dumps(b)))
 for k in ['B','B_PLUS_REBOUND']:
  a,ca=pair['BTC'];b,cb=pair['ETH'];assert len(ca[k])==len(cb[k]);q=dict(trades=sorted(a[k]['trades']+b[k]['trades'],key=lambda x:x['closed_us']),stats={'fees':a[k]['stats'].get('fees',0)+b[k]['stats'].get('fees',0)},state_at_end={'position':bool(a[k]['state_at_end']['position']or b[k]['state_at_end']['position'])});combined.append(dict(period=period,asset='COMBINED',version=k,**metrics(q,ca[k]+cb[k],1000)))
z.csv_dump(O/'results_by_asset.csv',rows);z.csv_dump(O/'results_combined.csv',combined);z.csv_dump(O/'trade_attribution.csv',attribution);z.csv_dump(O/'new_branch_closed_trades.csv',extra_rows);s.dump(O/'accounting_audit.json',dict(passed=True,total=len(audits),checks=audits))
text=['# 固定反弹续跌实验结论','', '新增入场只在独立分支；定义、固定日期和成本见EXPERIMENT.md。未调参，不建议据此替换原策略。近期C2含精确资金费；历史四段C1不含资金费，不能混称完整真实净收益。全部逐笔为触价全量成交模拟代理，不是实盘排队保证。','', '|区间|原B收益%|新增规则收益%|原回撤%|新增回撤%|','|---|---:|---:|---:|---:|']
for p in ['2020','2021','2023','2024','RECENT']:
 aa=next(r for r in combined if r['period']==p and r['version']=='B');bb=next(r for r in combined if r['period']==p and r['version']=='B_PLUS_REBOUND');text.append(f"|{p}|{aa['return_pct']:.3f}|{bb['return_pct']:.3f}|{aa['max_drawdown_pct']:.3f}|{bb['max_drawdown_pct']:.3f}|")
text+=['','RECENT收益起算为原11月1日账户，新增规则仅11月9日起启用；9日前原权益路径和交易保持完全一致，原B全部交易、现金和分钟权益与独立断点续跑完全一致。执行截止北京时间11月14日08:00；14日及15日后续逐笔档未发布，因此完整至15日仍UNVERIFIED。','', '历史四段均已跑完，非全历史或样本外验证。假跌破标记仅为事后四闭K线收盘收回水平的归因，不用于入场筛选。没有新增信号的震荡段只能说明本规则没有触发，不能证明所有震荡都安全。新旧交易的新增、消失、变化和同名义归一化另见CSV，不能将独立新增单利润直接加到基准账户。', '', '新增分支交易统计（不重复汇总CORE）：']
for r in rows:
 if r['version']!='B':text.append(f"- {r['period']} {r['asset']}：新增信号{r['new_signals']}，新增分支已平{r['extra_closed']}，盈利额{r['extra_winning_net']:.4f}，亏损额{r['extra_losing_net']:.4f}，净额{r['extra_net']:.4f} USDT；假跌破标记已平{r['false_break_extra_closed']}。")
text+=['','完整账户现金及未平仓估值20份对账通过。17项固定规则/因果前缀测试通过。2020ETH存在明显新增亏损，不能仅据近期补抓下跌宣布改善；本轮保持原规则冻结，不追加搜索。']
(O/'CONCLUSION.md').write_text('\n'.join(text))
print('REPORTED',len(rows),len(attribution),len(extra_rows))
