"""Read-only 2025 conditional results and exact scenario differences."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,csv,gzip,hashlib,copy
import numpy as np
import bridge as b
import observer as o
OUT=b.OUT;h=b.z.module('sensitivity_report_helpers',b.PARENT/'analysis_helpers.py')

def read(path):return json.loads(path.read_text())
def write_csv(path,rows,fields=None):
 if fields is None:fields=list(dict.fromkeys(k for row in rows for k in row))
 if not fields:fields=['status']
 op=gzip.open if path.suffix=='.gz'else open
 with op(path,'wt',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def trace_key(rec):
 token=rec['input'];return(token['time_us'],token['kind'],token.get('internal_event_id','')if token['kind']=='RAW'else'',rec['method'])
def financial(summary):return{k:v for k,v in summary.items()if k not in('raw_sequence','_visit_side')}
def compare_traces(old,new,scenario,key):
 left={trace_key(r):r for r in old};right={trace_key(r):r for r in new};assert len(left)==len(old)and len(right)==len(new)
 result=[]
 for token in sorted(left.keys()|right.keys()):
  x,y=left.get(token),right.get(token)
  if x==y:continue
  input_diff=x is None or y is None or x['input']!=y['input'];state_diff=False
  if x and y:state_diff=financial(x['post_state'])!=financial(y['post_state'])
  elif x:state_diff=financial(x['pre_state'])!=financial(x['post_state'])
  elif y:state_diff=financial(y['pre_state'])!=financial(y['post_state'])
  raw_events_differ=(x or{}).get('events_generated')!=(y or{}).get('events_generated')
  result.append(dict(scenario=scenario,key=key,time_us=token[0],time_Beijing=b.r.local_s(token[0]/1e6),kind=token[1],method=token[3],input_changed=input_diff,financial_state_difference_observed=state_diff,generated_events_differ=raw_events_differ,baseline_input=json.dumps(x['input'],ensure_ascii=False)if x else None,scenario_input=json.dumps(y['input'],ensure_ascii=False)if y else None,baseline_post_state=json.dumps(x['post_state'],ensure_ascii=False)if x else None,scenario_post_state=json.dumps(y['post_state'],ensure_ascii=False)if y else None,baseline_generated_events=json.dumps(x['events_generated'],ensure_ascii=False)if x else None,scenario_generated_events=json.dumps(y['events_generated'],ensure_ascii=False)if y else None))
 return result

def verify_B_history():
 folder=b.PARENT/'runs/2025/ETH/B';source=read(folder/'raw_sources.json');q=read(folder/'ZERO_B_result.json');sm=read(folder/'signals.json');lo=1756425600000000;hi=lo+86400000000
 signals=[(int(k),v)for k,v in sm['core'].items()if lo<=int(k)*1000<hi]
 orders=[e for e in q['events']if e['event']=='order_sent'and e['time_us']<hi and e['time_us']+3600000000>lo]
 positions=[t for t in h.rows(q)if t['opened_us']<hi and(t['closed_us']or h.us(q['window'][1]))>=lo]
 assert not signals and not orders and not positions and b.DAY not in source
 evidence=dict(old_source=q['source'],old_window=q['window'],UTC_day_Beijing=['2025-08-29T08:00:00+08:00','2025-08-30T08:00:00+08:00'],old_CORE_signals_in_day=signals,old_pending_orders_in_day=orders,old_positions_overlapping_day=positions,old_raw_archive_loaded=b.DAY in source,nearby_old_loaded_days=[x for x in sorted(source)if'2025-08-25'<=x<='2025-09-03'],reason='same Binance USDT perpetual engine, idle/no signals/orders/positions, no need to load anomaly archive; not a different source')
 b.dump(OUT/'B_original_archive_evidence.json',evidence);return evidence

def main():
 status=read(OUT/'status.json');assert status['completed']and status['status']=='COMPLETED_WITH_DATA_ANOMALY'
 frozen=read(OUT/'frozen_runtime.json')
 for name,sha in frozen['files'].items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==sha,name
 assert status['runtime_fingerprint']==frozen['runtime_fingerprint']
 info=b.z.prepare('2025','BTC');oldprovenance=read(b.PARENT/'runs/2025/BTC/B/input_provenance.json');hashes={n:hashlib.sha256((info['data']/n).read_bytes()).hexdigest()for n in['BTC_15m.csv','BTC_1m.npy']};assert hashes==oldprovenance['derived_SHA256']
 signals=read(OUT/'signals.json');assert {int(k):v for k,v in signals['BTC'].items()}==info['core']==info['wide']
 reference={};refdir=OUT/'reference_BTC';refdir.mkdir(exist_ok=True)
 for cost,fee in b.z.COSTS.items():
  folder=b.PARENT/'runs/2025/BTC/B';q=read(folder/f'{cost}_B_result.json');marks=np.load(folder/f'{cost}_B_equity.npy');assert q['fee']==fee and q['source']=='BINANCE_USDT_PERPETUAL_ONLY';h.curve(q,marks)
  reference[cost]=(q,marks);b.dump(refdir/f'{cost}_result.json',q)
 b.dump(OUT/'BTC_reuse_proof.json',dict(source_commit=b.BASE_COMMIT,independent_asset_cash=True,BTC_rules_unchanged=True,BTC_complete_signals_exact=True,BTC_native_SHA256=hashes,unchanged_parent_financial_fingerprint=b.PARENT_FP,sources={cost:dict(q_path=str(b.PARENT/'runs/2025/BTC/B'/f'{cost}_B_result.json'),q_SHA256=hashlib.sha256((b.PARENT/'runs/2025/BTC/B'/f'{cost}_B_result.json').read_bytes()).hexdigest(),equity_SHA256=hashlib.sha256(marks.tobytes()).hexdigest(),ending_equity=q['ending_equity'])for cost,(q,marks)in reference.items()},not_ninety_new_BTC_replays=True))
 conflict_lines={r['source_line']for c in read(OUT/'whitelist_manifest.json')['conflicts']for r in c['records']}
 bproof=verify_B_history();metrics=[];monthly=[];reconcile=[];curve_differences=[];trace_differences=[];trade_differences=[];event_differences=[];trace_summary=[];loaded={};oldBchecks=[];access=[]
 for scenario in b.SCENARIOS:
  for cost in b.z.COSTS:
   btc,btcmarks=reference[cost]
   for group in b.z.GROUPS:
    key=cost+'_'+group;folder=OUT/'results'/scenario;q=read(folder/f'{key}_result.json');marks=np.load(folder/f'{key}_equity.npy');assert q['status']=='COMPLETED_WITH_DATA_ANOMALY';vec=h.curve(q,marks);loaded[scenario,cost,group]=(q,marks)
    assert len(marks)==len(btcmarks)and q['window']==btc['window']
    residual=q['ending_equity']-500-sum(t['net']for t in q['trades'])-q['open_contribution'];cashres=q['cash']-500-sum(x['delta']for x in q['cash_events']);assert abs(residual)<1e-7 and abs(cashres)<1e-7
    reconcile.append(dict(scenario=scenario,cost=cost,group=group,closed_net=sum(t['net']for t in q['trades']),open_entry_fees_partial_and_MTM=q['open_contribution'],cash=q['cash'],ending_equity=q['ending_equity'],equity_residual=residual,cash_residual=cashres,fees=q['stats'].get('fees',0)))
    for asset,qq,values,initial,ts in [('ETH',q,marks,500.,q['trades']),('BTC',btc,btcmarks,500.,btc['trades']),('COMBINED',None,marks+btcmarks,1000.,btc['trades']+q['trades'])]:
     count=sum(bool(x['state_at_end']['position'])for x in([qq]if qq else[btc,q]));m=h.metrics(ts,values,initial,q['window'],count);months=m.pop('monthly');m.update(scenario=scenario,cost=cost,group=group,asset=asset,status='STRICT_REFERENCE_REUSED_UNCHANGED'if asset=='BTC'else'COMPLETED_WITH_DATA_ANOMALY',cash=qq['cash']if qq else btc['cash']+q['cash'],fees_paid_USDT=sum(x['stats'].get('fees',0)for x in([qq]if qq else[btc,q])),opens=sum(x['opens']for x in([qq]if qq else[btc,q])),expired=sum(x['stats'].get('expired',0)for x in([qq]if qq else[btc,q])))
     metrics.append(m);monthly.extend(dict(scenario=scenario,cost=cost,group=group,asset=asset,**x)for x in months)
    with gzip.open(OUT/q['trace_file'],'rt',encoding='utf-8')as f:trace=json.load(f)
    if scenario=='S_ALL':baseq,basemarks=q,marks;base_trace=trace
    else:
     baseq,basemarks=loaded['S_ALL',cost,group]
     with gzip.open(OUT/baseq['trace_file'],'rt',encoding='utf-8')as f:base_trace=json.load(f)
     changed=np.flatnonzero(marks!=basemarks)
     curve_differences.extend(dict(scenario=scenario,cost=cost,group=group,minute_end_us=round((info['start']+(int(i)+1)*60)*1e6),baseline_equity=float(basemarks[i]),scenario_equity=float(marks[i]),delta=float(marks[i]-basemarks[i]))for i in changed)
     td=compare_traces(base_trace,trace,scenario,key);trace_differences.extend(td)
     tr=h.compare(baseq,q,{})
     trade_differences.extend(dict(scenario=scenario,cost=cost,group=group,**x)for x in tr if x['category']!='RETAINED')
     if q['events']!=baseq['events']:
      for i in range(max(len(q['events']),len(baseq['events']))):
       x=baseq['events'][i]if i<len(baseq['events'])else None;y=q['events'][i]if i<len(q['events'])else None
       if x!=y:event_differences.append(dict(scenario=scenario,cost=cost,group=group,index=i,baseline_event=json.dumps(x,ensure_ascii=False),scenario_event=json.dumps(y,ensure_ascii=False)))
    countprice=sum(x['input'].get('latest_real_quote',{}).get('original_source_line')in conflict_lines for x in trace if x['input']['kind']=='POLL')
    trace_summary.append(dict(scenario=scenario,cost=cost,group=group,observed_event_count=len(trace),polls_using_conflicting_record_as_latest=countprice,trade_journal_equal_to_S_ALL=q['trades']==baseq['trades'],financial_events_equal_to_S_ALL=q['events']==baseq['events'],cash_exact_to_S_ALL=q['cash']==baseq['cash'],equity_minute_history_exact_to_S_ALL=np.array_equal(marks,basemarks),first_different_minute_end_us=next((r['minute_end_us']for r in curve_differences if r['scenario']==scenario and r['cost']==cost and r['group']==group),None)))
    ac=read(folder/f'{key}_access.json');baduses=[]
    for phase,record in ac.items():
     if record and(b.DAY in record['marks']or b.DAY in record['events']):baduses.append(phase)
    access.append(dict(scenario=scenario,cost=cost,group=group,anomaly_archive_financial_access_phases=';'.join(baduses),B_anomaly_day_financial_reads=bool(baduses)if group=='B'else'NOT_APPLICABLE'))
    if group=='B':
     old=read(b.PARENT/'runs/2025/ETH/B'/f'{key}_result.json');oldmarks=np.load(b.PARENT/'runs/2025/ETH/B'/f'{key}_equity.npy')
     assert q['trades']==old['trades']and q['cash']==old['cash']and q['ending_equity']==old['ending_equity']and np.array_equal(marks,oldmarks)and not baduses
     oldBchecks.append(dict(scenario=scenario,cost=cost,trades_cash_equity_and_minute_curve_exact=True,anomaly_day_no_signal_order_position_and_no_financial_reads=True))
  print('ANALYZED',scenario,flush=True)
 # Relative to same-scenario B, never another scenario or best branch.
 lookup={(x['scenario'],x['cost'],x['group'],x['asset']):x for x in metrics}
 for x in metrics:
  ref=lookup[x['scenario'],x['cost'],'B',x['asset']];x.update(relative_B_USDT=x['ending_equity']-ref['ending_equity'],relative_B_return_pp=x['return_pct']-ref['return_pct'],relative_B_max_drawdown_pp=x['max_drawdown_pct']-ref['max_drawdown_pct'])
 ranges=[];conclusions=[]
 for cost in b.z.COSTS:
  for group in b.z.GROUPS:
   for asset in('ETH','BTC','COMBINED'):
    use=[lookup[s,cost,group,asset]for s in b.SCENARIOS];r=dict(cost=cost,group=group,asset=asset,status='COMPLETED_WITH_DATA_ANOMALY')
    for field in('return_pct','ending_equity','cash','max_drawdown_pct','gross_losing_trade_net','max_single_trade_loss','closed','fees_paid_USDT','relative_B_USDT'):
     vals=[x[field]for x in use];r[field+'_min']=min(vals);r[field+'_max']=max(vals);r[field+'_span']=max(vals)-min(vals)
    ranges.append(r)
   vals=[lookup[s,cost,group,'COMBINED']['relative_B_USDT']for s in b.SCENARIOS]
   conclusions.append(dict(cost=cost,group=group,scenarios_better_than_B=sum(x>0 for x in vals),scenarios_equal_B=sum(x==0 for x in vals),scenarios_worse_than_B=sum(x<0 for x in vals),relative_B_min=min(vals),relative_B_max=max(vals),sign_consistent=len({(x>0)-(x<0)for x in vals})==1))
 for name,rows in[('annual_scenarios.csv',metrics),('monthly_scenarios.csv',monthly),('scenario_ranges.csv',ranges),('relative_B_conclusions.csv',conclusions),('cash_reconciliation.csv',reconcile),('B_exact_comparison.csv',oldBchecks),('archive_access_evidence.csv',access),('anomaly_trace_summary.csv',trace_summary),('anomaly_event_differences.csv.gz',trace_differences),('minute_equity_differences.csv.gz',curve_differences),('trade_differences_vs_S_ALL.csv',trade_differences),('financial_event_differences.csv',event_differences)]:write_csv(OUT/name,rows)
 summary=dict(status='COMPLETED_WITH_DATA_ANOMALY',original_strict_2025_DGHI='UNVERIFIED',ETH_scenario_accounts=len(reconcile),rows=len(metrics),B_exact_comparisons=len(oldBchecks),all_cash_and_fee_checks=True,all_annual_primary_metrics_identical_across_scenarios=all(x[f+'_span']==0 for x in ranges for f in('return_pct','ending_equity','max_drawdown_pct','gross_losing_trade_net','max_single_trade_loss','closed','fees_paid_USDT')),any_minute_equity_history_difference=bool(curve_differences),minute_equity_difference_rows=len(curve_differences),max_abs_minute_equity_difference=max([abs(x['delta'])for x in curve_differences]+[0]),trade_differences=len(trade_differences),financial_event_difference_rows=len(event_differences),trace_difference_rows=len(trace_differences),trace_post_financial_difference_rows=sum(x['financial_state_difference_observed']for x in trace_differences),conclusions=conclusions,ranges=ranges,pooling=read(OUT/'pooling.json'),funding='NOT_INCLUDED',fees='hypothetical .05pct/side; actual account fee unknown',scope='nine specified treatments of identified duplicate IDs only; additional quote anomalies/gaps retained; not official repair, not all possible data errors, not merged into seven old strictly verified intervals')
 b.dump(OUT/'analysis.json',summary);render(summary,metrics,ranges,conclusions,trace_summary,trace_differences,trade_differences,event_differences,curve_differences)
 print('REPORT_DONE',len(metrics),'annual metrics',len(trace_differences),'trace differences',len(curve_differences),'equity differences',flush=True)

def render(s,metrics,ranges,conclusions,traces,td,tr,ed,curves):
 lines=['# 2025 已识别逐笔冲突的九情景敏感性结果','','**状态：COMPLETED_WITH_DATA_ANOMALY。原严格D/G/H/I仍UNVERIFIED。** 本报告不将2025条件结果与七个严格区间混成全历史严格验证，也不把任何情景当官方修复。','','## 年度结果范围（BTC＋ETH）','','各组每币500，每次本币已实现余额×3，V2及全部策略/执行不改；ZERO零费，ASSUMED_005_SIDE每边.05%明确假设，资金费未计。每个范围覆盖S_ALL与8种选择，不选择最大值当正式结果。','','|费用|组|全年收益%范围|期末权益U范围|最大回撤%范围|相对B损益U范围|','|---|---|---:|---:|---:|---:|']
 for x in ranges:
  if x['asset']!='COMBINED':continue
  def span(field):return f"{x[field+'_min']:.10g} — {x[field+'_max']:.10g}"
  lines.append(f"|{x['cost']}|{x['group']}|{span('return_pct')}|{span('ending_equity')}|{span('max_drawdown_pct')}|{span('relative_B_USDT')}|")
 lines+=['','## 冲突究竟改变了什么？','']
 if s['all_annual_primary_metrics_identical_across_scenarios']:lines.append('九情景的全年收益、期末权益、最大回撤、总亏损、最大单亏、交易数及费用逐组逐费率完全一致：这些年度指标对已测试冲突处理不敏感。这不意味着输入、局部路径或所有可能数据错误都不敏感。')
 else:lines.append('九情景的部分年度指标不同。完整最小值/最大值/跨度在scenario_ranges.csv，不挑有利情景当结论。')
 lines += [f"配对交易变化记录{s['trade_differences']}条，原金融事件变化{s['financial_event_difference_rows']}条；异常窗口输入/状态差异{s['trace_difference_rows']}条，其中可观察金融后状态不同{s['trace_post_financial_difference_rows']}条。",f"分钟权益不同{s['minute_equity_difference_rows']}行，最大绝对差{s['max_abs_minute_equity_difference']:.12g}U；这些历史前缀独立保留并重算全年峰值/回撤，没有因后续状态相同而覆盖。"]
 if td:
  first=min(td,key=lambda x:x['time_us']);lines.append(f"最早被原引擎读取的情景差异：{first['time_Beijing']}，{first['scenario']} / {first['key']} / {first['kind']}。完整原行号、原ID、轮询最新价、前后状态和生成事件见anomaly_event_differences.csv.gz及各scenario trace。")
 if curves:
  first=min(curves,key=lambda x:x['minute_end_us']);lines.append(f"最早分钟权益差异：{b.r.local_s(first['minute_end_us']/1e6)}，{first['scenario']} / {first['cost']} / {first['group']}，差额{first['delta']:.12g}U。")
 lines+=['','## G/I相对B的结论是否随情景改变？','','|费用|组|高于/等于/低于B情景数|相对B最小/最大U|符号一致|','|---|---|---:|---:|---|']
 for x in conclusions:
  if x['group']not in('G','I'):continue
  lines.append(f"|{x['cost']}|{x['group']}|{x['scenarios_better_than_B']}/{x['scenarios_equal_B']}/{x['scenarios_worse_than_B']}|{x['relative_B_min']:.12g} / {x['relative_B_max']:.12g}|{x['sign_consistent']}|")
 pooling=s['pooling'];lines+=['','## 完整状态比较与后续执行共享','',f"所有90个ETH情景账本先运行到最晚冲突记录之后的比较点{pooling['merge_time']}。完整Book（含原交易/事件历史）、现金、持仓/挂单、有效止损/档位、V2队列/标记/部分退出、CORE请求、数量/fee/stats/tranches、最新轮询/真实报价和不可变信号/代码指纹严格比较，共形成{pooling['groups_after']}个后续执行池。hash相等后仍比较原字节，不按期末cash近似合并。",'每情景保留自己的异常窗口trace和年度分钟权益前缀、峰值/回撤；若只权益历史不同但完整原Book与后续输入相同，允许共享后缀，期末仍用各自全年曲线计算回撤。若原Book或轮询未来状态不同，不合并。池证明见pooling.json及view_equivalence.json。','','## 原B为什么可完成？','','实际旧B来源也是BINANCE_USDT_PERPETUAL_ONLY。该UTC档案日对应北京时间08-29 08:00—08-30 08:00，旧B无CORE信号、无挂单、无持仓，raw_sources没有加载此日；不是换了交易所或执行模型。本轮B从年初新播放，18个B情景交易/现金/期末权益/完整分钟数组与旧B逐项完全相同，而且没有该日金融价格读取。证据B_original_archive_evidence.json、B_exact_comparison.csv及archive_access_evidence.csv。BTC经完整信号、原生缓存SHA、源代码及独立账户核对后复用原2025逐笔对照，不冒充90次新BTC回放。','','## 全日审计及覆盖限制','','全日7454972条按原字符串、整数ID和整数毫秒时间审计。仅3个重复ID各2条，2处时间倒序；另有7301处正向ID跳号，完整输出，不据此证明市场全集完整。','还发现3条quote_qty与price×qty不一致：原行1493267、1513648、7261393，原字段/邻接及精确乘积已列。所有9情景原样保留这些字段；原模型只读取ID/price/time，成交量指标来自不变15m，原始qty/quote不用于触价全量代理。九情景不判断哪一字段正确，也不覆盖这些问题。','18个整分钟无逐笔，原生分钟成交量也为0。保持最后真实已知价轮询，不插值或OHLC造价，18分钟空档也不作已修复声明。','原日ZIP SHA053164460ed94f8b586ffd2e2d01e85612e752031f06b7d51776f27c7f6aa9db保留，CSV SHA1149b44ac2927660cea1bda5ab19aac620f50067c12bbf3d841e70fe240f9ed2与上轮月档对应日逐字节证据相同；没有重复下载2GB月档。','严格模式原校验仍拒绝这些冲突，普通日期继续调用原严格Cache；白名单精确限定SHA/日期/交易对/记录及已确认附加发现。S_ALL不去重，8组合只在派生索引排除3行，所有剩余原字段不改。原成交ID保留；内部事件ID用文件SHA+原行号。','九情景仅是有限数据异常假设，不是官方修复、不覆盖所有潜在错误、不构成独立样本外，也不是新的入场/止损优化。资金费未计、费率是假设、触价全额为模拟代理。','','## 交付与复跑','','annual_scenarios.csv逐情景/资产列全部年度指标和相对同情景B差额；scenario_ranges.csv列精确最小/最大/跨度；trade/financial_event差异、分钟权益差异和90份anomaly trace提供首次影响；results/各情景JSON保留完整交易及事件；cash_reconciliation.csv核对整笔net、费用和期末持仓估值。','固定命令、迁移/断点兼容、完整日志和数据来源见EXPERIMENT.md、run.log、compatibility_*.json、strict_prices/raw_sources.json。原七区间及main不变；仅此新目录和独立实验分支提交。']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
