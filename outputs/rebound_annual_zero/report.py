from pathlib import Path
import sys,json,csv,datetime,hashlib
import numpy as np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent
GROUPS={'A':('CONTROL','CONTROL'),'B':('REBOUND','CONTROL'),'C':('CONTROL','REBOUND'),'D':('REBOUND','REBOUND')}
annual=[];byasset=[];extra=[];trades=[];matching=[];failures=[];audits=[];recentrows=[];recenttrades=[]
def write(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 if not keys:keys=['status']
 with(O/name).open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows([{k:json.dumps(v,ensure_ascii=False)if isinstance(v,(list,dict))else v for k,v in r.items()}for r in rows])
def time_s(t):return datetime.datetime.fromtimestamp(t/1e6,datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='milliseconds')
def key(t):return(t['side'],int(t['signal_close_ms']))
def loss_metrics(ts):
 vals=[t['net']for t in ts];return dict(closed_trades=len(ts),total_loss_USDT=-sum(min(0,v)for v in vals),max_single_loss_USDT=-min([0.]+vals),winning_trades=sum(v>0 for v in vals),losing_trades=sum(v<0 for v in vals))
def curve_metrics(v,initial):
 p=np.maximum.accumulate(np.r_[initial,v]);return dict(ending_equity_USDT=float(v[-1]),net_USDT=float(v[-1]-initial),return_pct=float(100*(v[-1]/initial-1)),max_drawdown_pct=float(np.max(100*(1-np.r_[initial,v]/p))))
def load(folder,version):
 p=folder/f'{version}_result.json';q=json.loads(p.read_text());v=np.load(folder/f'{version}_equity.npz')['marks'];assert q['fee']==0.;assert q['configuration']['slip']==.0002;cashres=q['cash']-500-sum(t['net']for t in q['trades'])-(q.get('open_partial_state',{}).get('partial_net')or 0.);assert abs(cashres)<1e-7,(p,cashres)
 assert abs(q['cash']-500-sum(c['delta']for c in q['cash_events']))<1e-7
 pos=q['state_at_end']['position'];mtm=pos['order']['side']*pos['order']['qty']*(q['actual_raw_last_mark']-pos['order']['price'])if pos else 0.;assert abs(q['ending_equity']-q['cash']-mtm)<1e-7
 audits.append(dict(file=str(p.relative_to(R)),cash_closed_partial_residual=cashres,equity_residual=q['ending_equity']-q['cash']-mtm,passed=True));return q,v
def absence_reason(q,trade):
 stamp=trade['signal_close_ms'];clock=(stamp+10000)*1000;signal_us=stamp*1000
 for pos in q['trades']:
  if pos['opened_us']<=clock<pos['closed_us'] or pos['opened_us']<=signal_us<pos['closed_us']:return 'BLOCKED_POSITION'
 state=q['state_at_end']
 if state['position'] and state['position_opened_us']<=clock:return 'BLOCKED_POSITION'
 attempts=[a for a in q.get('sizing_audit',[])if a.get('signal_close_ms')==stamp]
 if attempts and not attempts[-1]['accepted']:return 'FUNDS_OR_MIN_NOTIONAL'
 fills={x['signal_close_ms']:x for x in q['trades']}
 for event in q['events']:
  if event['event']!='order_sent' or not event['time_us']<=clock<event['time_us']+3600000000:continue
  prior=event.get('signal_close_ms',event['time_us']//1000-10000);fill=fills.get(prior)
  if not fill or fill['opened_us']>clock:return 'BLOCKED_PENDING_ORDER'
 return 'NOT_EVALUATED'

def account(period,asset,pair):
 controls=pair['CONTROL'][0];q=pair['REBOUND'][0];new=[t for t in q['trades']if t['origin']=='EXTRA'];newopen=int(bool(q['state_at_end']['position'])and q['state_at_end']['position']['order'].get('origin')=='EXTRA');base={key(t):t for t in controls['trades']};var={key(t):t for t in q['trades']};pos=q['state_at_end']['position']
 if pos:present_open=(('LONG'if pos['order']['side']==1 else'SHORT'),int(pos['order'].get('signal_close_ms',pos['order']['time']-10000)))
 else:present_open=None
 gone=[t for k,t in base.items()if k not in var and k!=present_open];lostwins=[t for t in gone if t['net']>0]
 extra.append(dict(period=period,asset=asset,new_branch_filled=len(new)+newopen,new_branch_closed=len(new),new_branch_open=newopen,new_branch_wins=sum(t['net']>0 for t in new),new_branch_losses=sum(t['net']<0 for t in new),new_branch_closed_net_USDT=sum(t['net']for t in new),account_equity_difference_USDT=q['ending_equity']-controls['ending_equity'],account_return_difference_pp=100*(q['ending_equity']-controls['ending_equity'])/500,original_winning_trades_disappeared=len(lostwins),original_winning_net_lost_USDT=sum(t['net']for t in lostwins),original_losing_trades_disappeared=sum(t['net']<0 for t in gone),original_loss_avoided_USDT=-sum(min(0,t['net'])for t in gone),not_additive_counterfactual=True,verified_occupancy_displaced_winners=sum(absence_reason(q,t).startswith('BLOCKED_')for t in lostwins),verified_occupancy_displaced_profit_USDT=sum(t['net']for t in lostwins if absence_reason(q,t).startswith('BLOCKED_')),other_disappeared_winners=sum(not absence_reason(q,t).startswith('BLOCKED_')for t in lostwins)))
 for token in sorted(set(base)|set(var)):
  a=base.get(token);b=var.get(token);cat='NEW'if a is None else'ORIGINAL_CLOSED_NOW_OPEN'if b is None and token==present_open else'DISAPPEARED'if b is None else'RETAINED'if a==b else'CHANGED';matching.append(dict(period=period,asset=asset,side=token[0],signal_close_ms=token[1],classification=cat,baseline_net_USDT=a['net']if a else None,new_account_net_USDT=b['net']if b else None,original_profitable_disappeared=bool(a and a['net']>0 and cat=='DISAPPEARED'),absence_reason=absence_reason(q,a)if cat=='DISAPPEARED'else None))
for period in ['2020','2021','2022','2023','2024','2025','2026']:
 accounts={};status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'else'COMPLETE'
 for asset in ['BTC','ETH']:
  folder=O/'runs'/period/asset;done=folder/'status.json'
  if not done.exists():
   f=folder/'failure.json';failures.append(dict(period=period,asset=asset,status='FAILED'if f.exists()else'NOT_COMPLETED',reason=json.loads(f.read_text())['error']if f.exists()else'pending'));continue
  accounts[asset]={v:load(folder/'results',v)for v in ['CONTROL','REBOUND']};account(period,asset,accounts[asset])
  for version,(q,v)in accounts[asset].items():
   byasset.append(dict(period=period,asset=asset,version=version,status=q['status'],**curve_metrics(v,500.),**loss_metrics(q['trades']),open_count=int(bool(q['state_at_end']['position'])),window_start=q['window'][0],window_end=q['window'][1]))
   for t in q['trades']:trades.append(dict(period=period,asset=asset,version=version,**t,signal_Beijing=time_s(t['signal_close_ms']*1000),opened_Beijing=time_s(t['opened_us']),closed_Beijing=time_s(t['closed_us'])))
 for g,(btc,eth)in GROUPS.items():
  if len(accounts)<2:annual.append(dict(period=period,group=g,status='UNVERIFIED_INCOMPLETE_ASSET',return_pct=None,max_drawdown_pct=None,closed_trades=None,total_loss_USDT=None,max_single_loss_USDT=None));continue
  qb,vb=accounts['BTC'][btc];qe,ve=accounts['ETH'][eth];assert qb['window']==qe['window']and len(vb)==len(ve)
  annual.append(dict(period=period,group=g,BTC_variant=btc,ETH_variant=eth,status=status,**curve_metrics(vb+ve,1000.),**loss_metrics(qb['trades']+qe['trades']),open_count=int(bool(qb['state_at_end']['position']))+int(bool(qe['state_at_end']['position'])),window_start=qb['window'][0],window_end=qb['window'][1]))
# Separate recent full raw section and labeled bar sensitivity, retaining the Nov1 cash path.
config=O/'recent_config.json'
if config.exists():
 cfg=json.loads(config.read_text());nine=cfg['enable_rebound_ms']//1000;start=cfg['start_ms']//1000;ix=(nine-start)//60
 for stage in ['RAW','OHLC','OLHC']:
  accounts={}
  for asset in ['BTC','ETH']:
   folder=O/'recent'/asset/('raw_results'if stage=='RAW'else stage+'/results')
   if not (folder/'REBOUND_result.json').exists():continue
   accounts[asset]={v:load(folder,v)for v in ['CONTROL','REBOUND']}
   for version,(q,v)in accounts[asset].items():
    initial=float(v[ix-1]);ts=[t for t in q['trades']if t['closed_us']>=nine*1000000];recentrows.append(dict(stage=stage,asset=asset,version=version,status=q['status'],Nov9_initial_equity_USDT=initial,**curve_metrics(v[ix:],initial),**loss_metrics(ts)))
    for t in q['trades']:
     if t['closed_us']<nine*1000000:continue
     observed=t['closed_us']<cfg['raw_execution_end_ms']*1000;recenttrades.append(dict(stage=stage,asset=asset,version=version,execution='RAW_TRADE_SIMULATION'if observed else'SYNTHETIC_15M_PATH',**t,signal_Beijing=time_s(t['signal_close_ms']*1000),opened_Beijing=time_s(t['opened_us']),closed_Beijing=time_s(t['closed_us']),timestamp_is_assumed=not observed))
  if len(accounts)==2:
   for g,(b,e)in GROUPS.items():
    qb,vb=accounts['BTC'][b];qe,ve=accounts['ETH'][e];v=vb+ve;initial=float(v[ix-1]);ts=[t for t in qb['trades']+qe['trades']if t['closed_us']>=nine*1000000];recentrows.append(dict(stage=stage,asset='COMBINED',version=g,status='COMPLETE_RAW_TRADE_SIMULATION'if stage=='RAW'else'COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS',Nov9_initial_equity_USDT=initial,**curve_metrics(v[ix:],initial),**loss_metrics(ts)))
write('annual.csv',annual);write('asset_annual.csv',byasset);write('new_branch_annual.csv',extra);write('trades.csv',trades);write('trade_matching.csv',matching);write('recent.csv',recentrows);write('recent_trades.csv',recenttrades);safety=dict(passed=True,accounts=len(audits),checks=audits);(O/'accounting_checks.json').write_text(json.dumps(safety,indent=2));(O/'failures.json').write_text(json.dumps(failures,indent=2))
text=['# 反弹续跌年度零费用对照','', '基准4fbc499370454246ee92ac110d8b590328b0719e；原signals.py规则不变。手续费0、资金费0为用户指定口径，退出不利滑点0.02%，不是完整实盘净收益。每年度每币500；近期单独保持Nov1账户路径，不与年度拼接。','', '本轮A=两币原版；B=仅BTC加分支；C=仅ETH加分支；D=两币加分支。与旧实验组名不同。实际只回放每币两条独立账户，四组按同一时间轴组合，不新增本金。','', '|区间|本轮组|收益%|最大回撤%|已平仓|总亏损USDT|最大单亏USDT|状态|','|---|---|---:|---:|---:|---:|---:|---|']
for r in annual:
 if r['return_pct']is None:text.append(f"|{r['period']}|{r['group']}|未验证|未验证|未验证|未验证|未验证|{r['status']}|");continue
 text.append(f"|{r['period']}|{r['group']}|{r['return_pct']:.3f}|{r['max_drawdown_pct']:.3f}|{r['closed_trades']}|{r['total_loss_USDT']:.3f}|{r['max_single_loss_USDT']:.3f}|{r['status']}|")
text+=['','2020仅2月16日至年底，2026仅1—10月，具体UTC/北京边界见每账户config。最大回撤按分钟合并权益，不是两币回撤简单平均。总亏损和最大单亏按已平仓完整交易净额；年末浮动估值计入权益，不假设年末全平。2025仅S_ALL已授权异常视图，不能称全历史严格验证，也不将旧九情景一致套用到本策略。','', '## 新增分支与机会挤占','', '|区间|币|新增已成交/已平|赢/亏|新增已平净额|完整账户权益差额|原盈利单消失笔数/金额|','|---|---|---|---|---:|---:|---|']
for r in extra:text.append(f"|{r['period']}|{r['asset']}|{r['new_branch_filled']}/{r['new_branch_closed']}|{r['new_branch_wins']}/{r['new_branch_losses']}|{r['new_branch_closed_net_USDT']:.3f}|{r['account_equity_difference_USDT']:.3f}|{r['original_winning_trades_disappeared']}/{r['original_winning_net_lost_USDT']:.3f}|")
text+=['','新增分支净额只统计该账户已平EXTRA交易；完整账户差额含资金余额变化、原信号挤占、仓位/退出变化及年末浮动，不能把两者相加。原盈利单消失金额是原账户实际利润的事后机会归因，不是可直接相加的损失。trades.csv保留两路径逐笔，trade_matching.csv按方向+signal_close_ms匹配，不强行配对。','', '## 近期独立区间','']
if config.exists():
 cfg=json.loads(config.read_text());text+=['真实逐笔执行截止北京'+time_s(cfg['raw_execution_end_ms']*1000)+'；后续闭15m假设路径截止北京'+time_s(cfg['bar_execution_end_ms']*1000)+'。原始逐笔与合成路径单列；15m内OHLC/OLHC先后与插值时间不是实际观察，也不是严格收益上下界。','', '|口径|本轮组|9日起收益%|期末权益|最大回撤%|','|---|---|---:|---:|---:|']
 for r in recentrows:
  if r['asset']=='COMBINED':text.append(f"|{r['stage']}|{r['version']}|{r['return_pct']:.3f}|{r['ending_equity_USDT']:.3f}|{r['max_drawdown_pct']:.3f}|")
 text+=['','recent_trades.csv记录两币每笔开空和退出时间、成交价、净额及是否依赖假设。9日前完整账户状态相同证明见recent/*/pre9_state_comparison.json；原零费基准前缀比较见baseline_comparison.json。近期新增已平利润和同一时刻完整账户差额应分开理解。']
text+=['','## 直接判断','']
complete=[p for p in ['2020','2021','2022','2023','2024','2025','2026']if all(any(r['period']==p and r['group']==g and r['return_pct']is not None for r in annual)for g in GROUPS)]
if len(complete)==7:
 for g,label in [('B','仅BTC'),('C','仅ETH'),('D','两币同时')]:
  comp=[]
  for p in complete:
   a=next(x for x in annual if x['period']==p and x['group']=='A');v=next(x for x in annual if x['period']==p and x['group']==g);comp.append((p,v['return_pct']-a['return_pct'],v['max_drawdown_pct']-a['max_drawdown_pct'],v['total_loss_USDT']-a['total_loss_USDT']))
  up=sum(x[1]>1e-8 for x in comp);dd=sum(x[2]>1e-8 for x in comp);ls=sum(x[3]>1e-8 for x in comp);worst=min(comp,key=lambda x:x[1]);text.append(f'- {label}：7区间中{up}个收益提高，{dd}个回撤扩大，{ls}个总亏损增加；最差相对收益差为{worst[0]}年的{worst[1]:.3f}个百分点。'+'是否值得需同时看上述收益、实际亏损及回撤代价，不能仅据新增单利润判定。')
 text.append('- 是否两币同时更好，须对照上表每年完整账户，不能把新增单利润相加或按年份选择组。没有跨年连续账户，所以不报告伪连续复利“总收益”。')
else:text.append('年度仍有未完成或失败区间，不给伪完整结论；已完成结果保留，失败明细见failures.json。')
if failures:
 text+=['','## 未完成/失败','']+[f"- {r['period']} {r['asset']}：{r['status']}，{r['reason']}"for r in failures]
text+=['','复跑命令（Python3.12，仓库根目录）：','```bash','python outputs/rebound_annual_zero/supervisor.py','python outputs/rebound_annual_zero/recent_prepare.py','python outputs/rebound_annual_zero/recent.py BTC','python outputs/rebound_annual_zero/recent.py ETH','python outputs/rebound_annual_zero/report.py','```','', '原代码及main不改；本轮不追加参数搜索、收费部署或大包。']
(O/'CONCLUSION.md').write_text('\n'.join(text));print('REPORT',len(complete),'complete periods',len(audits),'accounts',len(failures),'incomplete')
