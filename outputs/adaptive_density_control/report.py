from pathlib import Path
import csv,json,datetime,hashlib
import numpy as np
import worker as w
O=w.O;s=w.s
PERIODS=['2020','2021','2022','2023','2024','2025','2026'];FEES=['ZERO','ASSUMED_005_SIDE'];GROUPS=['A','B','C','D'];rows=[];trades=[];audit=[];comparison=[];matches=[];recentrows=[];recenttrades=[]
def csvwrite(path,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r))or['status']
 with path.open('w',encoding='utf-8-sig',newline='')as f:t=csv.DictWriter(f,fieldnames=keys);t.writeheader();t.writerows([{k:json.dumps(v,ensure_ascii=False)if isinstance(v,(dict,list))else v for k,v in r.items()}for r in rs])
def metrics(v,initial,ts):
 peak=np.maximum.accumulate(np.r_[initial,v]);nets=[t['net']for t in ts];return dict(ending_equity_USDT=float(v[-1]),return_pct=float(100*(v[-1]/initial-1)),max_drawdown_pct=float(np.max(100*(1-np.r_[initial,v]/peak))),closed_trades=len(ts),win_rate_pct=100*sum(x>0 for x in nets)/len(nets)if nets else None,total_loss_USDT=-sum(min(0,x)for x in nets),max_single_loss_USDT=-min([0.]+nets))
def paths(period,asset,fee,group,frozen):
 if period in w.TRAIN and fee=='ZERO'and group in ['A','B','C']:
  name='A'if group=='A'else frozen[group];folder=O/'runs/train'/period/asset;key='ZERO_'+name
 else:
  stage='train_final'if period in w.TRAIN else'final';folder=O/'runs'/stage/period/asset;key=fee+'_'+group
 return folder,folder/'results'/f'{key}_result.json',key
def load(path):
 q=json.loads(path.read_text());v=np.load(path.with_name(path.name.replace('_result.json','_equity.npz')))['marks'];pos=q['state_at_end']['position'];fee=q['fee']*pos['order']['price']*pos['order']['qty']if pos else 0.;unrealized=pos['order']['side']*pos['order']['qty']*(q['mark_price']-pos['order']['price'])if pos else 0.;cash=q['cash'];closed=sum(t['net']for t in q['trades']);r1=cash-500-closed+fee;r2=q['ending_equity']-cash-unrealized
 assert abs(r1)<1e-7 and abs(r2)<1e-7 and abs(cash-500-sum(t['delta']for t in q['cash_events']))<1e-7;assert q['V2']is False and not any('partial'in e['event']for e in q['events']);assert abs(v[-1]-q['ending_equity'])<1e-7
 audit.append(dict(path=str(path.relative_to(w.R)),cash=cash,closed_net=closed,open_entry_fee=fee,unrealized=unrealized,ending_equity=q['ending_equity'],cash_residual=r1,equity_residual=r2,no_V2=True,passed=True));return q,v
def local_us(t):return datetime.datetime.fromtimestamp(t/1e6,datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='milliseconds')if t is not None else None
def trade_key(t):return(t['side'],int(t['signal_close_ms']))
def open_key(q):
 p=q['state_at_end']['position']
 return(('LONG'if p['order']['side']==1 else'SHORT'),int(p['order'].get('signal_close_ms',p['order']['time']-10000)))if p else None
def reason(q,stamp,side,accepted):
 if accepted.get(stamp)!=side:return 'ADAPTIVE_SIGNAL_REMOVED'
 sent=[e for e in q['events']if e['event']=='order_sent'and e.get('signal_close_ms',e['time_us']//1000-10000)==stamp]
 if sent:return 'ORDER_SUBMITTED_NOT_FILLED'
 sizing=[e for e in q['sizing_audit']if e['signal_close_ms']==stamp]
 if sizing and not sizing[-1]['accepted']:return 'FUNDS_OR_MIN_NOTIONAL'
 clock=(stamp+10000)*1000;signal=stamp*1000
 for t in q['trades']:
  if t['opened_us']<=clock<t['closed_us']or t['opened_us']<=signal<t['closed_us']:return 'OCCUPIED_POSITION'
 p=q['state_at_end'];
 if p['position']and p['position_opened_us']<=clock:return 'OCCUPIED_POSITION'
 fills={int(t['signal_close_ms']):t for t in q['trades']}
 for e in q['events']:
  if e['event']=='order_sent'and e['time_us']<=clock<e['time_us']+3600000000:
   t=fills.get(int(e.get('signal_close_ms',e['time_us']//1000-10000)))
   if t is None or t['opened_us']>clock:return 'OCCUPIED_PENDING_ORDER'
 return 'NOT_EVALUATED'
def attribute(scope,period,asset,fee,group,base,var,amap,vmap):
 cutoff=1794153600000 if scope.startswith('RECENT_')else 0
 aa={trade_key(t):t for t in base['trades']if t['signal_close_ms']>=cutoff};vv={trade_key(t):t for t in var['trades']if t['signal_close_ms']>=cutoff};amap={t:v for t,v in amap.items()if t>=cutoff};vmap={t:v for t,v in vmap.items()if t>=cutoff};op=open_key(var);new=[t for k,t in vv.items()if k not in aa];removed={(t,side)for t,side in amap.items()if vmap.get(t)!=side};lost=[t for k,t in aa.items()if t['net']>0 and k not in vv and k!=op];occ=[];filtered=0
 for t in lost:
  why=reason(var,t['signal_close_ms'],1 if t['side']=='LONG'else-1,vmap)
  if why.startswith('OCCUPIED'):occ.append(t)
  if why=='ADAPTIVE_SIGNAL_REMOVED':filtered+=1
 comparison.append(dict(scope=scope,period=period,asset=asset,fee_scenario=fee,group=group,ending_equity_difference_USDT=var['ending_equity']-base['ending_equity'],account_path_start='Nov1'if cutoff else'ANNUAL_RESET',attributed_signals_start_ms=cutoff or None,post9_net_change_difference_USDT=(var['ending_equity']-var['pre9_equity'])-(base['ending_equity']-base['pre9_equity'])if cutoff else None,new_closed_trades=len(new),new_closed_net_USDT=sum(t['net']for t in new),original_profitable_trades_absent=len(lost),original_profit_absent_USDT=sum(t['net']for t in lost),profitable_absent_due_signal_filter=filtered,profitable_absent_with_occupancy=len(occ),profit_absent_with_occupancy_USDT=sum(t['net']for t in occ),all_original_complete_signals_removed=len(removed),priority_exits=sum(t['reason']=='core_priority_exit'for t in var['trades']),not_additive_counterfactual=True))
 if group=='D':assert not removed,'D must retain all A CORE signals/directions'
 for k in sorted(set(aa)|set(vv)):
  a=aa.get(k);b=vv.get(k);status='NEW'if a is None else'ORIGINAL_CLOSED_NOW_OPEN'if b is None and k==op else'ABSENT'if b is None else'RETAINED'if a==b else'CHANGED';matches.append(dict(scope=scope,period=period,asset=asset,fee_scenario=fee,group=group,side=k[0],signal_close_ms=k[1],category=status,A_net=a['net']if a else None,variant_net=b['net']if b else None,absent_reason=reason(var,k[1],1 if k[0]=='LONG'else-1,vmap)if status=='ABSENT'else None,signal_in_A=amap.get(k[1])==(1 if k[0]=='LONG'else-1)))
def accepted_for(folder,key):return {int(k):v for k,v in json.loads((folder/'signals.json').read_text())['accepted'][key].items()}
frozen=json.loads((O/'FREEZE.json').read_text());fail=[]
for period in PERIODS:
 for fee in FEES:
  accounts={};signalsets={}
  for asset in ['BTC','ETH']:
   for group in GROUPS:
    folder,path,key=paths(period,asset,fee,group,frozen)
    if not path.exists()or not(folder/'status.json').exists():fail.append(dict(period=period,asset=asset,fee=fee,group=group,status='UNVERIFIED_INCOMPLETE'));continue
    q,v=load(path);accounts[asset,group]=(q,v);signalsets[asset,group]=accepted_for(folder,key);m=metrics(v,500.,q['trades']);rows.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,status=q['status'],**m,open_count=int(bool(q['state_at_end']['position'])),window_start=q['window'][0],window_end=q['window'][1]))
    for t in q['trades']:trades.append(dict(period=period,asset=asset,fee_scenario=fee,group=group,**t,signal_Beijing=local_us(t['signal_close_ms']*1000),opened_Beijing=local_us(t['opened_us']),closed_Beijing=local_us(t['closed_us'])))
   if(asset,'A')in accounts:
    for group in ['B','C','D']:
     if(asset,group)in accounts:attribute('ANNUAL',period,asset,fee,group,accounts[asset,'A'][0],accounts[asset,group][0],signalsets[asset,'A'],signalsets[asset,group])
  for group in GROUPS:
   if('BTC',group)not in accounts or('ETH',group)not in accounts:continue
   a,av=accounts['BTC',group];b,bv=accounts['ETH',group];assert a['window']==b['window']and len(av)==len(bv);rows.append(dict(period=period,asset='COMBINED',fee_scenario=fee,group=group,status='COMPLETED_WITH_DATA_ANOMALY'if period=='2025'else'COMPLETE',**metrics(av+bv,1000.,a['trades']+b['trades']),open_count=int(bool(a['state_at_end']['position']))+int(bool(b['state_at_end']['position'])),window_start=a['window'][0],window_end=a['window'][1]))
# Recent maintains each version's own Nov1→Nov9 state; no reset to a common balance.
rcfg=json.loads((w.R/'outputs/rebound_annual_zero/recent_config.json').read_text());ix=(rcfg['enable_rebound_ms']-rcfg['start_ms'])//60000
whyrows=[]
for scene in ['RAW','OHLC','OLHC']:
 for fee in FEES:
  accounts={};maps={}
  for asset in ['BTC','ETH']:
   folder=O/'recent'/asset;sigfile=folder/('signals_RAW.json'if scene=='RAW'else'signals_BAR.json')
   if not sigfile.exists():continue
   sigs=json.loads(sigfile.read_text());conds={}
   for n in set(['A',frozen['B'],frozen['C'],frozen['D_source']]):
    p=folder/(n+'_conditions_'+('RAW'if scene=='RAW'else'BAR')+'.csv')
    if p.exists():conds[n]={int(r['signal_close_ms']):r for r in csv.DictReader(p.open(encoding='utf-8-sig'))}
   for group in GROUPS:
    key=fee+'_'+group;path=folder/scene/'results'/(key+'_result.json')
    if not path.exists():continue
    q,v=load(path);accounts[asset,group]=(q,v);maps[asset,group]={int(k):x for k,x in sigs['accepted'][key].items()};initial=float(v[ix-1]);ts=[t for t in q['trades']if t['closed_us']>=rcfg['enable_rebound_ms']*1000];recentrows.append(dict(scene=scene,asset=asset,fee_scenario=fee,group=group,status=q['status'],Nov9_initial_equity=initial,**metrics(v[ix:],initial,ts),Nov1_to_end_return_pct=100*(v[-1]/500-1),Nov9_net_USDT=float(v[-1]-initial)))
    for t in ts:
     observed=t['closed_us']<rcfg['raw_execution_end_ms']*1000;recenttrades.append(dict(scene=scene,asset=asset,fee_scenario=fee,group=group,execution='RAW_TRADE_SIMULATION'if observed else'MIXED_RAW_ENTRY_BAR_EXIT'if t['opened_us']<rcfg['raw_execution_end_ms']*1000 else'SYNTHETIC_15M_PATH',**t,signal_Beijing=local_us(t['signal_close_ms']*1000),opened_Beijing=local_us(t['opened_us']),closed_Beijing=local_us(t['closed_us'])))
     if asset=='ETH'and t['side']=='SHORT':
      name='A'if group=='A'or(group=='D'and sigs['A'].get(str(t['signal_close_ms']))==-1)else frozen['D_source']if group=='D'else frozen[group];d=conds.get(name,{}).get(t['signal_close_ms'],{});whyrows.append(dict(scene=scene,fee_scenario=fee,group=group,origin=t['origin'],signal_close_ms=t['signal_close_ms'],opened_us=t['opened_us'],closed_us=t['closed_us'],entry=t['entry'],exit=t['exit'],net=t['net'],execution='RAW'if observed else'MIXED_RAW_ENTRY_BAR_EXIT'if t['opened_us']<rcfg['raw_execution_end_ms']*1000 else'ASSUMED_BAR',signal_Beijing=local_us(t['signal_close_ms']*1000),opened_Beijing=local_us(t['opened_us']),closed_Beijing=local_us(t['closed_us']),source=name,**{k:d.get(k,'NOT_EVALUATED')for k in ['regime','historical_metric','historical_threshold','current_metric','current_threshold','aligned_lines','short_term_alignment','distance_pct','volume_breakout','confirmed_retest']}))
    pos=q['state_at_end']['position']
    if asset=='ETH'and pos and pos['order']['side']==-1:
     order=pos['order'];stamp=int(order['signal_close_ms']);name='A'if group=='A'or(group=='D'and sigs['A'].get(str(stamp))==-1)else frozen['D_source']if group=='D'else frozen[group];d=conds.get(name,{}).get(stamp,{})
     whyrows.append(dict(scene=scene,fee_scenario=fee,group=group,origin=order['origin'],signal_close_ms=stamp,signal_Beijing=local_us(stamp*1000),opened_Beijing=local_us(q['state_at_end']['position_opened_us']),entry=order['price'],exit=None,net=None,execution='OPEN_AT_SCENE_END',source=name,**{k:d.get(k,'NOT_EVALUATED')for k in ['regime','historical_metric','historical_threshold','current_metric','current_threshold','aligned_lines','short_term_alignment','distance_pct','volume_breakout','confirmed_retest']}))
   if(asset,'A')in accounts:
    for group in ['B','C','D']:
     if(asset,group)in accounts:attribute('RECENT_'+scene,'NOV',asset,fee,group,accounts[asset,'A'][0],accounts[asset,group][0],maps[asset,'A'],maps[asset,group])
  for group in GROUPS:
   if('BTC',group)not in accounts or('ETH',group)not in accounts:continue
   a,av=accounts['BTC',group];b,bv=accounts['ETH',group];v=av+bv;initial=float(v[ix-1]);ts=[t for t in a['trades']+b['trades']if t['closed_us']>=rcfg['enable_rebound_ms']*1000];recentrows.append(dict(scene=scene,asset='COMBINED',fee_scenario=fee,group=group,status='COMPLETE_RAW_TRADE_SIMULATION'if scene=='RAW'else'COMPLETED_WITH_15M_EXECUTION_ASSUMPTIONS',Nov9_initial_equity=initial,**metrics(v[ix:],initial,ts),Nov1_to_end_return_pct=100*(v[-1]/1000-1),Nov9_net_USDT=float(v[-1]-initial)))
for name,rs in [('annual.csv',rows),('trades.csv',trades),('signal_attribution.csv',comparison),('trade_matching.csv',matches),('recent.csv',recentrows),('recent_trades.csv',recenttrades),('recent_ETH_short_reasons.csv',whyrows)]:csvwrite(O/name,rs)
(O/'accounting_checks.json').write_text(json.dumps(dict(passed=True,outputs=len(audit),checks=audit),indent=2));(O/'incomplete.json').write_text(json.dumps(fail,indent=2))
text=['# 双币同参自适应密集条件实验','', '**本轮A是无V2的原CONTROL，pause_transition=True，不能复用上一轮含V2的A。** 所有版本均无反弹续跌、无分批减仓，2%硬止损及无上限阶梯止损不改。资金费0；两费用分别0、每边0.05%假设，退出滑点0.02%。每年每币500独立起算，不拼接跨年复利。','', '实际调用链和main快照差异见CALL_CHAIN.md。main核心源码逐字节核对，底层候选与overlay都接入自适应门槛，没有固定.25提前拦截。所有窗口只用过去数据，B不含当前根、C为WilderATR96，不加绝对上下限。','', '## 训练和冻结','', f"2020—2022零手续费组合评分mean(return−maxDD)，B固定为{frozen['B']} {frozen['B_parameters']}，C固定为{frozen['C']} {frozen['C_parameters']}；D信号来源{frozen['D_source']}。冻结UTC：{frozen['frozen_UTC']}。",'', '完整候选分数见training_candidate_scores.csv，逐年分数见training_yearly_scores.csv。手续费场景共用冻结参数，没有按年份/币种/费用重选。2023—2026为冻结后的时间切分检验，这些年份已被看过，不能称完全未见样本外。','', '**D同时改变信号并集、补充仓位和优先级，不能把D相对B/C差异解释成优先级独立效果。** D CORE为A完整信号并优先方向，CORE3x、EXTRA1x，同一钱包不叠加资金或敞口。','']
for fee in FEES:
 text += [f'## 年度组合：{fee}','', '|区间|A收益/回撤%|B收益/回撤%|C收益/回撤%|D收益/回撤%|','|---|---:|---:|---:|---:|']
 for period in PERIODS:
  cells=[]
  for group in GROUPS:
   r=next((r for r in rows if r['period']==period and r['asset']=='COMBINED'and r['fee_scenario']==fee and r['group']==group),None);cells.append(f"{r['return_pct']:.3f}/{r['max_drawdown_pct']:.3f}"if r else'未验证')
  text.append('|'+period+'|'+'|'.join(cells)+'|')
text+=['','2020仅2月16日起，2026仅1—10月；2025ETH仅S_ALL异常视图，组合保持COMPLETED_WITH_DATA_ANOMALY，未重复九情景，也不将旧九情景一致用于证明新策略。CSV含每年×币种/组合的权益、收益、回撤、已平仓数、胜率、总亏损及最大单亏。','', '## 信号归因与执行代价','', 'signal_attribution.csv按A完整策略信号与实际交易分别核对。all_original_complete_signals_removed是主动过滤，不能算占仓；原盈利单缺失另标过滤、真实持仓/挂单证据、已提交未成交、最低名义或未确定。近期只归因9日后信号；完整账户终值差额含1日起路径，另列post9_net_change_difference以排除9日前权益差额，不混用。D所有A信号保留，但不保证恢复所有A实际成交：替换退出、重新挂单及余额路径仍有代价。完整账户差额不是新增单净额简单相加。trade_matching.csv保留新增、消失、保留、变化及未平匹配，不强行配对。','', '## 近期独立区间','', '所有版本从11月1日起按各自完整策略运行，保留各自9日前现金/持仓/挂单，9日不重置，也不强制它们状态相同。recent.csv单列9日起表现及Nov1累计表现。RAW截止北京'+datetime.datetime.fromtimestamp(rcfg['raw_execution_end_ms']/1000,datetime.timezone(datetime.timedelta(hours=8))).isoformat()+'；后续至'+datetime.datetime.fromtimestamp(rcfg['bar_execution_end_ms']/1000,datetime.timezone(datetime.timedelta(hours=8))).isoformat()+'为已有OHLC/OLHC假设路径，非真实逐笔或严格收益上下界。','', 'recent_ETH_short_reasons.csv逐笔列ETH是否重新开空、入场/退出、历史密集指标/门槛、ER、量价/回踩理由；占用与过滤归因见RECENT行。重复RAW前缀与两个假设场景不是独立样本，不能相加。','', '## 完成状态','',f'年度输出{len(rows)}行，账本对账{len(audit)}份；未完成账户条件{len(fail)}条。完整运行日志和失败原因保留，缺失不填0。','', '复跑入口：先train_supervisor.py，再freeze.py（只写一次），再final_supervisor.py、report.py。pipeline.py可等待全部训练完成后自动冻结及执行后续阶段。无合并main，无额外大包，无前瞻任务，无追加优化。']
text+=['','## 固定版本结果概览','']
for fee in FEES:
 for group in ['B','C','D']:
  paired=[]
  for period in PERIODS:
   a=next((r for r in rows if r['period']==period and r['asset']=='COMBINED'and r['fee_scenario']==fee and r['group']=='A'),None);b=next((r for r in rows if r['period']==period and r['asset']=='COMBINED'and r['fee_scenario']==fee and r['group']==group),None)
   if a and b:paired.append((period,b['return_pct']-a['return_pct'],b['max_drawdown_pct']-a['max_drawdown_pct']))
  if paired:text.append(f"{fee}：{group}相对A，收益更高{sum(x[1]>0 for x in paired)}/{len(paired)}个区间、回撤扩大{sum(x[2]>0 for x in paired)}/{len(paired)}个区间。各区间差额（收益百分点/回撤百分点）："+'；'.join(f'{p} {r:+.3f}/{d:+.3f}'for p,r,d in paired)+'。')
text+=['','## ETH近期重新开空','']
for scene in ['RAW','OHLC','OLHC']:
 for fee in FEES:
  for group in GROUPS:
   rr=[x for x in whyrows if x['scene']==scene and x['fee_scenario']==fee and x['group']==group and x['signal_close_ms']>=rcfg['enable_rebound_ms']]
   if not rr:text.append(f'{scene}/{fee}/{group}：9日后未见已成交ETH空单。');continue
   text.append(f'{scene}/{fee}/{group}：'+ '；'.join(f"信号{x['signal_Beijing']}，入场{x['entry']}，状态{x['execution']}，来源{x['source']}，历史密集{x['historical_metric']}≤{x['historical_threshold']}，ER={x['regime']}，放量={x['volume_breakout']}、回踩={x['confirmed_retest']}"for x in rr)+'。')
(O/'CONCLUSION.md').write_text('\n'.join(text));print('REPORTED',len(rows),len(audit),len(fail))
