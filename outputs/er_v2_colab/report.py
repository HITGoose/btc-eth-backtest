"""Account differences from complete replay, normalized matching only attribution."""
from pathlib import Path
import os,json,csv,zipfile
import numpy as np
ROOT=Path(os.environ.get('BTC_REPO_ROOT',Path(__file__).resolve().parents[2]));OUT=Path(os.environ['BTC_OUTPUT_ROOT']);V=['ER_V2_REFERENCE','ER_V2_FAIL_EXIT','ER_V2_VOL_SIZE']
def save(name,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))or['status']
 with(OUT/name).open('w',newline='',encoding='utf-8-sig')as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def dd(m):return float(100*np.max(1-m/np.maximum.accumulate(m)))
def metric(q,m,seed):
 trades=q['trades'];closed=sum(t['net']for t in trades);equity=q['ending_equity'];cash=q['cash']
 contribution=equity-seed-closed
 assert abs(cash+q.get('end_unrealized',equity-cash)-equity)<1e-7
 return dict(ending_equity=equity,return_pct=100*(equity/seed-1),net_pnl=equity-seed,minute_max_drawdown_pct=dd(np.r_[seed,m]),closed_trades=len(trades),closed_net=closed,end_open_contribution=contribution,total_loss=sum(min(t['net'],0)for t in trades),max_single_loss=min([0]+[t['net']for t in trades]))
def key(t):return(t['side'],t['signal_close_ms'])
def normalized(t):return 1000*t['net']/(t['entry']*t['quantity'])
def main():
 annual=[];matching=[];fail=[];sizing=[];cache={};missing=[]
 for y in range(2020,2027):
  for asset in ['BTC','ETH']:
   reference=ROOT/f'outputs/baseline_registry/reused/ER_V2_REFERENCE/{y}/{asset}';base=json.loads((reference/'result.json').read_text());bm=np.load(reference/'equity.npz')['marks'];cache[y,asset,V[0]]=(base,bm)
   for version in V:
    if version==V[0]:q,m=base,bm
    else:
     folder=OUT/'runs'/str(y)/asset
     if not(folder/'status.json').exists():missing.append(dict(year=y,asset=asset,version=version,status='UNVERIFIED'));continue
     q=json.loads((folder/'results'/f'{version}_result.json').read_text());m=np.load(folder/'results'/f'{version}_equity.npz')['marks'];cache[y,asset,version]=(q,m)
    row=dict(year=y,asset=asset,version=version,status=q.get('status','COMPLETE'),**metric(q,m,500));row['difference_vs_reference']=q['ending_equity']-base['ending_equity'];annual.append(row)
    if version==V[0]:continue
    old={key(t):t for t in base['trades']};new={key(t):t for t in q['trades']}
    for identity in sorted(old.keys()|new.keys()):
     a=old.get(identity);b=new.get(identity);kind='NEW'if a is None else'DISAPPEARED'if b is None else'RETAINED'if all(a.get(k)==b.get(k)for k in ['opened_us','closed_us','entry','exit','quantity','net','partial_fills'])else'CHANGED'
     match=dict(year=y,asset=asset,version=version,side=identity[0],signal_close_ms=identity[1],classification=kind,reference_net=a['net']if a else None,variant_net=b['net']if b else None,reference_normalized_1000=normalized(a)if a else None,variant_normalized_1000=normalized(b)if b else None,normalized_difference=normalized(b)-normalized(a)if a and b else None,actual_difference=(b['net']if b else 0)-(a['net']if a else 0));matching.append(match)
     if b and b.get('reason')=='failed_breakout_exit':
      initial=b['entry']*b['quantity'];variant_r=normalized(b);baseline_r=normalized(a)if a else None;open_state=base.get('state_at_end',{}).get('position');open_order=open_state.get('order',{})if open_state else{}
      is_open=bool(open_state and open_order.get('side')==identity[0]and open_order.get('signal_close_ms')==identity[1])
      category='BASELINE_OPEN_AT_END'if is_open else'BASELINE_CLOSED_WINNER'if a and a['net']>0 else'BASELINE_HARD_STOP'if a and'hard'in str(a.get('reason','')).lower()else'BASELINE_OTHER_LOSS'if a else'NO_BASELINE_CLOSED_MATCH'
      fail.append(dict(match,baseline_category=category,reference_reason=a.get('reason')if a else None,variant_exit=b['exit'],reference_exit=a.get('exit')if a else None,entry_notional=initial))
    for ev in q['events']:
     if ev['event']=='volatility_sizing':
      identity=(next((t['side']for t in q['trades']if t['signal_close_ms']==ev['signal_close_ms']),0),ev['signal_close_ms']);a=old.get(identity)
      sizing.append(dict(year=y,asset=asset,**ev,baseline_closed_net=a['net']if a else None,baseline_outcome='WINNER'if a and a['net']>0 else'LOSS'if a else'NOT_CLOSED_MATCH'))
  for version in V:
   if not all((y,a,version)in cache for a in ['BTC','ETH']):continue
   q1,m1=cache[y,'BTC',version];q2,m2=cache[y,'ETH',version];assert m1.shape==m2.shape
   q=dict(ending_equity=q1['ending_equity']+q2['ending_equity'],cash=q1['cash']+q2['cash'],trades=q1['trades']+q2['trades']);b1=cache[y,'BTC',V[0]][0];b2=cache[y,'ETH',V[0]][0]
   annual.append(dict(year=y,asset='COMBINED',version=version,status='COMPLETED_WITH_DATA_ANOMALY'if y==2025 else'COMPLETE',**metric(q,m1+m2,1000),difference_vs_reference=q['ending_equity']-b1['ending_equity']-b2['ending_equity']))
 summary=[]
 for phase,years in [('2020_2022',range(2020,2023)),('2023_2026',range(2023,2027)),('ALL_7',range(2020,2027))]:
  for version in V:
   rr=[r for r in annual if r['asset']=='COMBINED'and r['version']==version and r['year']in years];diffs=[r['difference_vs_reference']for r in rr];risk=[]
   for r in rr:
    b=next(t for t in annual if(t['asset'],t['year'],t['version'])==('COMBINED',r['year'],V[0]));risk.append(r['minute_max_drawdown_pct']>b['minute_max_drawdown_pct']+1e-10)
   summary.append(dict(phase=phase,version=version,completed_periods=len(rr),expected_periods=len(list(years)),independent_net_sum=sum(r['net_pnl']for r in rr),difference_sum=sum(diffs),winning_years=sum(d>1e-8 for d in diffs),drawdown_increased_years=sum(risk),largest_positive_year_difference=max([0]+diffs),positive_difference_concentration=max([0]+diffs)/sum(max(x,0)for x in diffs)if sum(max(x,0)for x in diffs)>0 else None))
 concentration=[];effects=[]
 for version in V[1:]:
  for asset in ['BTC','ETH']:
   for y in range(2020,2027):
    matches=[r for r in matching if r['year']==y and r['asset']==asset and r['version']==version];pairs=[r for r in matches if r['reference_net'] is not None and r['variant_net'] is not None]
    effects.append(dict(year=y,asset=asset,version=version,matched=len(pairs),old_loss_actual_change=sum(r['actual_difference']for r in pairs if r['reference_net']<0),old_loss_normalized_change=sum(r['normalized_difference']for r in pairs if r['reference_net']<0),old_win_actual_change=sum(r['actual_difference']for r in pairs if r['reference_net']>0),old_win_normalized_change=sum(r['normalized_difference']for r in pairs if r['reference_net']>0),new_net=sum(r['variant_net']for r in matches if r['classification']=='NEW'),disappeared_original_net=sum(r['reference_net']for r in matches if r['classification']=='DISAPPEARED')))
    positive=[max(0,r['variant_net']or 0)for r in matches];concentration.append(dict(year=y,asset=asset,version=version,closed_positive_net=sum(positive),largest_closed_win=max([0]+positive),largest_win_share=max([0]+positive)/sum(positive)if sum(positive)else None,attribution_not_account_replay=True))
 save('trade_effects.csv',effects);save('concentration.csv',concentration)
 for name,rows in [('annual.csv',annual),('trade_matching.csv',matching),('failed_exit_matching.csv',fail),('sizing.csv',sizing),('period_summary.csv',summary),('missing.csv',missing)]:save(name,rows)
 lines=['# ER＋V2两项独立移植实验','',f'缺失任务记录数：{len(missing)}。没有完成的账户不填零。','逐年与分币结果见annual.csv；阶段简单合计见period_summary.csv。七期不拼复利，不计算跨年回撤；这些历史不是全新样本外。','', '归一化差额仅作退出／仓位归因，不是可执行账户增益。提前退出保留V2已兑现盈亏；NEW与DISAPPEARED来自完整账户路径。2025为S_ALL数据异常敏感性结果。费用0、资金费0、退出滑点0.02%；触价全量成交为模拟代理。','', '## 组合结果','|年|版本|收益%|分钟回撤%|净盈亏U|相对基准U|','|---|---|---:|---:|---:|---:|']
 for r in annual:
  if r['asset']=='COMBINED':lines.append(f"|{r['year']}|{r['version']}|{r['return_pct']:.2f}|{r['minute_max_drawdown_pct']:.2f}|{r['net_pnl']:.2f}|{r['difference_vs_reference']:+.2f}|")
 for version in V[1:]:
  stage=next(r for r in summary if r['phase']=='ALL_7'and r['version']==version)
  lines.append(f"{version}：已完成{stage['completed_periods']}/7期，跑赢{stage['winning_years']}期、回撤扩大{stage['drawdown_increased_years']}期；最大年度正差额{stage['largest_positive_year_difference']:.2f}U，占全部年度正差额{100*(stage['positive_difference_concentration']or 0):.1f}%。")
  for asset in ['BTC','ETH']:
   vals=[max(0,r['actual_difference'])for r in matching if r['version']==version and r['asset']==asset];share=max([0]+vals)/sum(vals)if sum(vals)else 0
   lines.append(f"{asset}最大单笔正向匹配差额占正向匹配差额{100*share:.1f}%；这是归因集中度，不是账户收益分解；另见未平贡献。")
 lines+=['','分币分年及单笔集中度：使用trade_matching.csv的实际差额及每1000初始名义差额对照；单笔归因不能直接相加替代账户差额。未平原交易单独标记BASELINE_OPEN_AT_END。']
 (OUT/'REPORT.md').write_text('\n'.join(lines))
 with zipfile.ZipFile(OUT/'results_for_review.zip','w',zipfile.ZIP_DEFLATED)as z:
  for p in OUT.rglob('*'):
   if p.is_file()and p.name!='results_for_review.zip'and 'temporary'not in p.parts and p.suffix not in ['.zip','.part','.tmp']and p.name!='checkpoint.pkl.gz':z.write(p,p.relative_to(OUT))
 print('Report ready:',OUT/'results_for_review.zip','Missing:',len(missing))
if __name__=='__main__':main()
