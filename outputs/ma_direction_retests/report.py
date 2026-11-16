"""Uniform read-only accounting. Cached baseline loaded once per coordinator process."""
import common as c
from catalog import SPECS,canonical,STAGES,ALIASES
import json,csv
np=c.np;CACHE={}
def rows_csv(name,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))or['status']
 with(c.OUT/name).open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def load(key,year,asset):
 p=c.existing(key,year,asset)
 if not p:return None
 sha=c.digest(p/'result.json');ident=str(p)+sha
 if ident not in CACHE:
  q=json.loads((p/'result.json').read_text());m=np.load(p/'equity.npz')['marks'];assert abs(m[-1]-q['ending_equity'])<1e-7;CACHE[ident]=(q,m,json.loads((p/'status.json').read_text()).get('source','BASELINE_REUSED'))
 return CACHE[ident]
def metric(q,m,seed):
 tr=q['trades'];net=sum(t['net']for t in tr);e=q['ending_equity'];a=np.r_[seed,m];dd=float(np.max(100*(1-a/np.maximum.accumulate(a))))
 return dict(ending_equity=e,return_pct=100*(e/seed-1),net_pnl=e-seed,minute_max_drawdown_pct=dd,closed_trades=len(tr),closed_net=net,end_open_contribution=e-seed-net,total_loss=sum(min(0,t['net'])for t in tr),maximum_single_loss=min([0]+[t['net']for t in tr]))
def selected():
 winners={}
 for name in ['B','C']:
  p=c.OUT/f'freeze_adaptive_{name}.json'
  if p.exists():winners[name]=json.loads(p.read_text())[name+'_winner']
 return winners
def groups():return [k for k in SPECS if k!='REBOUND']+['REBOUND_BTC','REBOUND_ETH','REBOUND_BOTH']
def identity(group,asset):
 if group.startswith('REBOUND_'):return 'REBOUND'if group=='REBOUND_BOTH'or group=='REBOUND_'+asset else'REF'
 return canonical(group,asset)
def refresh(stage=None):
 annual=[];matching=[];recon=[];winners=selected();missing=[]
 for group in groups():
  for year in range(2020,2027):
   if group in SPECS and SPECS[group]['kind']=='adaptive'and year>2022:
    family=SPECS[group]['family'];winner=winners.get(family)
    if winner!=group:
     annual.append(dict(group=group,year=year,asset='COMBINED',status='AWAITING_TRAINING_FREEZE'if not winner else'NOT_SELECTED_FROZEN_TRAINING',completed=False));continue
   book={};refs={}
   for asset in ['BTC','ETH']:
    key=identity(group,asset);b=load('REF',year,asset);a=load(key,year,asset)
    if not a or not b:
     annual.append(dict(group=group,year=year,asset=asset,status='UNVERIFIED',completed=False));missing.append(dict(group=group,key=key,year=year,asset=asset));continue
    q,m,source=a;ref,bm,_=b;book[asset]=a;refs[asset]=b;row=dict(group=group,key=key,year=year,asset=asset,status=q.get('status','COMPLETE'),source=source,completed=True,**metric(q,m,500),difference_vs_reference=q['ending_equity']-ref['ending_equity']);annual.append(row)
    if key=='REF':continue
    old={(t['side'],t['signal_close_ms']):t for t in ref['trades']};new={(t['side'],t['signal_close_ms']):t for t in q['trades']};matched_delta=0
    signals=None;p=c.existing(key,year,asset)
    if(p/'signals.json').exists():signals={int(t):d for t,d in json.loads((p/'signals.json').read_text())['actual'].items()}
    for ident in sorted(old.keys()|new.keys()):
     a0=old.get(ident);a1=new.get(ident);kind='NEW'if a0 is None else'DISAPPEARED'if a1 is None else'RETAINED'if all(a0.get(k)==a1.get(k)for k in ['opened_us','closed_us','entry','exit','quantity','partial_fills','net'])else'CHANGED'
     norm=lambda t:1000*t['net']/(t['entry']*t['quantity']);delta=(a1['net']if a1 else 0)-(a0['net']if a0 else 0);matched_delta+=delta;reason=None
     if kind=='DISAPPEARED':
      if signals is not None and signals.get(ident[1])!=ident[0]:reason='SIGNAL_FILTERED_BY_DECLARED_RULE'
      else:
       t=ident[1]*1000+10000000;occupied=next((r for r in q['trades']if r['opened_us']<=t<r['closed_us']),None);state=q.get('state_at_end',{});pos=state.get('position');opentime=state.get('position_opened_us')
       if occupied or(pos and opentime is not None and opentime<=t):reason='EVIDENCED_POSITION_OCCUPANCY'
       else:reason='ORDER_FUNDS_MINIMUM_OR_UNMATCHED_REASON_NOT_PROVEN'
     elif kind=='CHANGED':reason='QUANTITY_BALANCE_OR_EXIT_PATH_CHANGE'
     elif kind=='NEW':reason='ADDED_SIGNAL_OR_RELEASED_CAPACITY'
     matching.append(dict(group=group,year=year,asset=asset,side=ident[0],signal_close_ms=ident[1],classification=kind,reason=reason,reference_net=a0['net']if a0 else None,variant_net=a1['net']if a1 else None,actual_net_change=delta,reference_normalized_1000=norm(a0)if a0 else None,variant_normalized_1000=norm(a1)if a1 else None,normalized_change=norm(a1)-norm(a0)if a0 and a1 else None,reference_quantity=a0['quantity']if a0 else None,variant_quantity=a1['quantity']if a1 else None,reference_opened_us=a0['opened_us']if a0 else None,variant_opened_us=a1['opened_us']if a1 else None,reference_closed_us=a0['closed_us']if a0 else None,variant_closed_us=a1['closed_us']if a1 else None,quantity_changed=bool(a0 and a1 and a0['quantity']!=a1['quantity']),entry_price_changed=bool(a0 and a1 and a0['entry']!=a1['entry']),exit_price_changed=bool(a0 and a1 and a0['exit']!=a1['exit']),partial_exit_changed=bool(a0 and a1 and a0.get('partial_fills')!=a1.get('partial_fills'))))
    bstat=metric(ref,bm,500);open_delta=row['end_open_contribution']-bstat['end_open_contribution'];residual=row['difference_vs_reference']-matched_delta-open_delta;assert abs(residual)<1e-6
    recon.append(dict(group=group,year=year,asset=asset,closed_matching_net_change=matched_delta,open_contribution_change=open_delta,account_equity_change=row['difference_vs_reference'],residual=residual))
   if len(book)==2:
    q1,m1,_=book['BTC'];q2,m2,_=book['ETH'];assert m1.shape==m2.shape
    combined=dict(trades=q1['trades']+q2['trades'],ending_equity=q1['ending_equity']+q2['ending_equity']);baseline=sum(refs[a][0]['ending_equity']for a in refs);annual.append(dict(group=group,year=year,asset='COMBINED',status='COMPLETED_WITH_DATA_ANOMALY'if year==2025 else'COMPLETE_RAW_PROXY',completed=True,**metric(combined,m1+m2,1000),difference_vs_reference=combined['ending_equity']-baseline))
 summary=[]
 for group in groups():
  if group=='REF':continue
  for period,years in [('TRAIN_2020_2022',[2020,2021,2022]),('EVAL_2023_2026',[2023,2024,2025,2026]),('ALL_INDEPENDENT',list(range(2020,2027)))]:
   a=[r for r in annual if r['group']==group and r['year']in years and r['asset']=='COMBINED'and r.get('completed')];refs={r['year']:r for r in annual if r['group']=='REF'and r['asset']=='COMBINED'and r.get('completed')};diff=sum(r['difference_vs_reference']for r in a);inc=sum(r['minute_max_drawdown_pct']>refs[r['year']]['minute_max_drawdown_pct']+1e-9 for r in a);dec=sum(r['minute_max_drawdown_pct']<refs[r['year']]['minute_max_drawdown_pct']-1e-9 for r in a);pos=[max(0,r['difference_vs_reference'])for r in a]
   label='统计未完成'
   if len(a)==len(years):
    label='收益改善候选'if diff>1e-7 and inc==0 else'回撤改善候选'if diff<=1e-7 and dec>inc else'收益风险互有取舍'if(diff>1e-7 and inc>0)or(diff<0 and dec>0)else'无明显改善'
   trades=[max(0,r['actual_net_change'])for r in matching if r['group']==group and r['year']in years]
   summary.append(dict(group=group,period=period,complete_periods=len(a),required_periods=len(years),independent_net_sum=sum(r['net_pnl']for r in a),account_difference_sum=diff,winning_years=sum(r['difference_vs_reference']>1e-7 for r in a),drawdown_increased_years=inc,drawdown_decreased_years=dec,max_positive_year_share=max([0]+pos)/sum(pos)if sum(pos)>0 else None,max_positive_matched_trade_share=max([0]+trades)/sum(trades)if sum(trades)>0 else None,classification=label,attribution_not_executable_profit=True))
 training=[]
 for family in ['B','C']:
  f=c.OUT/f'freeze_adaptive_{family}.json'
  if f.exists():
   q=json.loads(f.read_text())
   for row in q[family+'_scores']:
    for y in row['years']:training.append(dict(family=family,key=row['key'],parameters=str(row['parameters']),score=row['score'],worst_drawdown=row['worst_drawdown'],total_fills=row['total_fills'],selected=q[family+'_winner']==row['key'],**y))
 rows_csv('training_scores.csv',training)
 causes={}
 for row in matching:
  key=(row['group'],row['classification'],row['reason'])
  out=causes.setdefault(key,dict(group=key[0],classification=key[1],reason=key[2],count=0,actual_net_change=0.,normalized_matched_change=0.))
  out['count']+=1;out['actual_net_change']+=row['actual_net_change'];out['normalized_matched_change']+=row['normalized_change']or 0.
 rows_csv('change_reason_summary.csv',list(causes.values()))
 rows_csv('annual.csv',annual);rows_csv('period_summary.csv',summary);rows_csv('trade_matching.csv',matching);rows_csv('account_reconciliation.csv',recon);rows_csv('incomplete.csv',missing)
 lines=['# 旧六线方向分类版独立优化','', '2026从1月1日连续至北京时间11月16日00:00前，包含11月15日全天；不在11月重置。其余年度独立500U/币。零手续费/资金费、0.02%退出滑点、RAW触价模拟代理。2025ETH沿用S_ALL。','只复用均线版基准；全部优化独立计算，失败或缺数据不当0。训练只用2020—2022原网格，未选候选不跑后续年。所有阶段结果展示，不只展示赢家。','官方档案更新时，只允许匹配原基准已记录SHA和CRC的冻结旧快照，另记dataset_revision_notices，不声称匹配最新版或修复官方数据。','七期是独立区间合计，不拼复利或跨年回撤。历史已见，不称全新样本外。分类只是描述：正增益且回撤无扩大=收益候选；非正增益且回撤改善年多于扩大年=回撤候选；增益/风险分歧=取舍。未完成不作完整排名。','', '|组|年|收益%|分钟回撤%|相对基准U|','|---|---|---:|---:|---:|']
 for r in annual:
  if r['asset']=='COMBINED'and r.get('completed'):lines.append(f"|{r['group']}|{r['year']}|{r['return_pct']:.2f}|{r['minute_max_drawdown_pct']:.2f}|{r['difference_vs_reference']:+.2f}|")
 lines+=['','signal_filtered只在实际信号字典有证据时标记；占仓仅有实际持仓证据时认定，其他原因保持未证实。逐笔按初始实际名义1000U归一化，区别余额、数量和退出路径影响；这些不是可直接相加的账户增益。账户差额用已平匹配差额＋未平贡献差额闭合。','',f'尚缺单币结果记录：{len(missing)}；仅复用旧六线方向版12个基准单币账户；全部优化独立计算，不借用ER＋V2利润、断点或训练值。2026补自身新全段基准；本报告不是ER与MA之间的比较。']
 (c.OUT/'REPORT.md').write_text('\n'.join(lines))
 if stage is not None:
  print('\nSTAGE',stage,STAGES[stage],flush=True)
  for r in annual:
   g=r['group'];st=11 if g.startswith('REBOUND_')else SPECS[g]['stage']
   if st==stage and r['asset']=='COMBINED'and r.get('completed'):print(g,r['year'],f"return {r['return_pct']:.2f}% DD {r['minute_max_drawdown_pct']:.2f}% delta {r['difference_vs_reference']:+.2f}U",flush=True)
 c.backup(c.OUT);return annual
