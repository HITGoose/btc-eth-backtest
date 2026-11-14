"""Numerical summary of freshly replayed2025 views, including small historical differences."""
from pathlib import Path
import csv,json,gzip
import shared as s
O=s.OUT

def read(name):
 p=O/name;op=gzip.open if p.suffix=='.gz'else open
 with op(p,'rt',encoding='utf-8-sig')as f:return list(csv.DictReader(f))
def main():
 checks=[x for x in read('scenario_history_checks.csv')if x['primary']=='True'];diff=[x for x in read('scenario_minute_equity_differences.csv.gz')if x['primary']=='True'];ranges=read('2025_scenario_ranges.csv');changed=[]
 for row in checks:
  if row['scenario']=='S_ALL':continue
  folder=O/row['root']/'results';a=json.loads((folder/'S_ALL'/(row['key']+'_result.json')).read_text());b=json.loads((folder/row['scenario']/(row['key']+'_result.json')).read_text())
  for field in ['trades','events','cash_events','sizing_audit','funding_events']:
   if a.get(field)!=b.get(field):changed.append(dict(root=row['root'],key=row['key'],scenario=row['scenario'],field=field))
 q=dict(primary_own_history_checks=len(checks),annual_metric_rows=len(ranges),nonzero_annual_ranges=[x for x in ranges if float(x['span'])>1e-8],primary_minute_difference_rows=len(diff),max_absolute_primary_minute_difference_USDT=max([abs(float(x['difference']))for x in diff]or[0.]),first_primary_different_minute_end_us=min([int(x['minute_end_us'])for x in diff]or[0]),changed_ledger_fields=changed,official_data_repaired=False)
 s.dump(O/'scenario_summary.json',q)
 text=['# 2025本轮九情景复核','',f"完成{len(checks)}个主实验ETH情景账户的自身历史核对（34配置×9，不是独立样本），对应全年组合收益/权益/回撤/总亏损/最大单亏/交易数/费用共{len(ranges)}项区间。非零年度指标跨度{len(q['nonzero_annual_ranges'])}项。",'',f"**不能说全部历史路径逐分钟相同**：主实验有{len(diff)}条情景分钟差异，最大绝对差{q['max_absolute_primary_minute_difference_USDT']:.8f} USDT。各情景自己的分钟数组、历史峰值与回撤均保留；详见scenario_minute_equity_differences.csv.gz。",'',f"最早差异的分钟结束时刻：{s.z.h.time_s(q['first_primary_different_minute_end_us'])if diff else'无'}。逐笔、事件、现金、定量与资金费账本字段发现{len(changed)}项不一致，完整列表见scenario_summary.json；不是只比较现金后合并。",'', '本轮对已测试冲突处理的年度指标不敏感，但局部分钟权益可不同。只限原SHA、三个已识别冲突ID、S_ALL及八种选择视图，不代表官方数据修复，也不覆盖全部潜在错误。旧严格失败标签不改，2025仅COMPLETED_WITH_DATA_ANOMALY。']
 (O/'SCENARIO_RECHECK.md').write_text('\n'.join(text)+'\n');print('SCENARIO_SUMMARY',json.dumps({k:v for k,v in q.items()if k not in('nonzero_annual_ranges','changed_ledger_fields')}))
if __name__=='__main__':main()
