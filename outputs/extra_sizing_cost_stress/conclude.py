from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,json
import shared as s
O=s.OUT

def read(name):
 p=O/name
 if not p.exists():return[]
 op=gzip.open if str(p).endswith('.gz')else open
 with op(p,'rt',encoding='utf-8-sig')as f:return list(csv.DictReader(f))
def num(v):return float(v)if v not in('',None,'None')else 0.
def choose(rows,**match):return next((r for r in rows if all(r.get(k)==v for k,v in match.items())),None)
def dump(name,rows):
 if rows:s.z.csv_dump(O/name,rows)
def main():
 fullrows=[r for r in read('annual_matrix.csv')if r['asset']=='COMBINED'and r['direction']=='ALL'];rows=read('mobile_annual.csv');ce=read('core_extra.csv');attrs=read('trade_attribution.csv.gz');selected=lambda r:r.get('scenario')in('STRICT','S_ALL')
 attrs=[r for r in attrs if selected(r)];ce=[r for r in ce if selected(r)];ret=[];groups=['B','G','H','I100','I50','I25'];periods=['2020','2021','2022','2023','2024','2025','2026','NOV']
 for r in fullrows:
  if r['group']not in ('I100','I50','I25'):continue
  base=choose(fullrows,period=r['period'],scenario=r['scenario'],cost=r['cost'],fill=r['fill'],group='B');full=choose(fullrows,period=r['period'],scenario=r['scenario'],cost=r['cost'],fill=r['fill'],group='I100')
  if not base or not full:continue
  gain=num(r['ending_equity'])-num(base['ending_equity']);fullgain=num(full['ending_equity'])-num(base['ending_equity']);dd=num(r['max_drawdown_pct'])-num(base['max_drawdown_pct'])
  cat='收益增加但风险也增加'if gain>1e-7 and dd>1e-8 else'收益与回撤同时改善'if gain>1e-7 else'风险降低但收益优势消失'if dd< -1e-8 else'与B一致'if abs(gain)<1e-7 and abs(dd)<1e-8 else'未优于B'
  ret.append(dict(period=r['period'],scenario=r['scenario'],cost=r['cost'],fill=r['fill'],group=r['group'],ending_equity=r['ending_equity'],advantage_USDT=gain,I100_advantage_USDT=fullgain,positive_advantage_retained_pct=100*gain/fullgain if fullgain>1e-7 else None,DD_excess_B_pp=dd,DD_difference_I100_pp=num(r['max_drawdown_pct'])-num(full['max_drawdown_pct']),category=cat))
 dump('advantage_retention.csv',ret)
 lost=[];concentr=[]
 for a in attrs:
  if num(a.get('old_net'))<0 and num(a.get('new_net'))<0:
   lost.append(dict(a,actual_loss_expanded=num(a['new_net'])<num(a['old_net'])-1e-8,normalized_loss_expanded=num(a['new_normalized_1000'])<num(a['old_normalized_1000'])-1e-8,same_entry_exit_prices_times=all(a.get(k)==a.get(k.replace('old_','new_'))for k in ['old_entry','old_exit','old_opened_us','old_closed_us']),interpretation='normalization retains V2 fraction/rounding/funding effects; not pure price risk'))
 dump('loss_amplification.csv.gz',lost)
 bucket=defaultdict(list)
 for a in attrs:
  if a['comparison_base']=='B':bucket[(a['period'],a['cost'],a['fill'],a['group'])].append(a)
 for key,aa in bucket.items():
  vals=sorted((num(x['actual_USDT_delta'])for x in aa if num(x['actual_USDT_delta'])>0),reverse=True);pos=sum(vals);total=sum(num(x['actual_USDT_delta'])for x in aa)
  concentr.append(dict(period=key[0],cost=key[1],fill=key[2],group=key[3],actual_difference_USDT=total,positive_attribution_USDT=pos,top5_positive_USDT=sum(vals[:5]),top5_positive_share_pct=100*sum(vals[:5])/pos if pos else None,arithmetic_difference_without_top5=total-sum(vals[:5]),not_a_removed_trade_backtest=True))
 dump('concentration.csv',concentr)
 def cell(r,field,signed=False):
  if not r:return '未验证'
  values=[num(x[field])for x in fullrows if x['period']==r['period']and x['cost']==r['cost']and x['fill']==r['fill']and x['group']==r['group']]if r['period']=='2025'else[num(r[field])]
  if r['period']=='2025'and len(values)!=9:return '九情景未齐'
  fmt=lambda x:f'{x:+.2f}'if signed else f'{x:.2f}'
  return fmt(min(values))if max(values)-min(values)<1e-8 else'['+fmt(min(values))+','+fmt(max(values))+']'
 lines=['# 中文结论：固定EXTRA仓位与成本压力','', '不能据现有结果认定I在完整历史中覆盖了真实交易成本。2020—2023缺完整官方结算标记价，含资金费全年结果未验证；2024/2025/2026/NOV只按实际完整结果判断。I50/I25是固定仓位实验，不按年份挑比例，不称I25已风险对齐，也不直接替换B。','', '2025表格为九情景范围（相同则仅显示一个数），不能选择有利情景。归因集中度与V2示例默认固定S_ALL，完整其他情景见原逐笔表；S_ALL不是官方修复。2025只标COMPLETED_WITH_DATA_ANOMALY；其九情景范围另列，不与原七严格区间混称全历史严格通过。已有年份被重复观察，不是样本外。','', '## C1：每边0.05%假设手续费、出场滑点0.02%，不含资金费','', '|区间|B收益/回撤%|G|H|I100|I50|I25|','|---|---:|---:|---:|---:|---:|---:|']
 for period in periods:
  cells=[]
  for group in groups:
   r=choose(rows,period=period,cost='C1',fill='F_TOUCH',group=group);cells.append(cell(r,'return_pct',True)+'/'+cell(r,'max_drawdown_pct')if r else'未验证')
  lines.append('|'+period+'|'+'|'.join(cells)+'|')
 lines+=['','2020仅2月16日至年底，2026仅1—10月，NOV独立起算至11月13日08:00北京；各区间各币500，非跨年复利。','', '## 含实际资金费：C2/C3/C4（假设手续费与滑点仍按预先固定矩阵）','', '|区间|成本|版本|收益%|回撤%|相对B U|','|---|---|---|---:|---:|---:|']
 for period in ['2024','2025','2026','NOV']:
  for cost in ['C2','C3','C4']:
   for group in groups:
    r=choose(rows,period=period,cost=cost,fill='F_TOUCH',group=group);base=choose(rows,period=period,cost=cost,fill='F_TOUCH',group='B')
    if r and base:lines.append(f"|{period}|{cost}|{group}|{cell(r,'return_pct',True)}|{cell(r,'max_drawdown_pct')}|{cell(r,'relative_B_USDT',True)}|")
 lines+=['','## 重点回答','', '1. EXTRA缩小后保留的优势逐区间列于advantage_retention.csv。只有I100相对B原本为正时才算保留比例；原优势为负不伪装成保留收益。实际USDT变化与固定初始名义1000的逐笔归一化在独立字段列示。','', '2. 重点回撤代价（C1，相对B百分点）：','', '|区间|I100|I50|I25|','|---|---:|---:|---:|']
 for period in ['2022','2024','2026']:
  cells=[]
  for group in ['I100','I50','I25']:
   r=choose(ret,period=period,cost='C1',fill='F_TOUCH',group=group);cells.append(f"{num(r['DD_excess_B_pp']):+.3f}"if r else'未验证')
  lines.append('|'+period+'|'+'|'.join(cells)+'|')
 lines+=['','3. 不能用同比缩小解释全部变化。完整账户按余额重新定量，CORE后续数量和V2部分退出都会变。drawdown_extremes.csv逐案例列组合峰值/谷值及BTC、ETH贡献；overlapping_exposure.csv另列重叠持仓风险，不把参考止损风险当保证。']
 for group in ['I100','I50','I25']:
  aa=[r for r in ret if r['cost']=='C1'and r['fill']=='F_TOUCH'and r['group']==group and r['period']not in('2025','NOV')]
  counts=Counter(r['category']for r in aa);lines.append(f"- {group}：已完成的{len(aa)}个严格年内区间分类："+'；'.join(k+str(v)+'个'for k,v in counts.items())+'。')
 lines+=['','4. CORE利润变化与最小名义拒单逐来源列于core_extra.csv；trade_attribution另给I50/I25相对I100的匹配，不只对B。相同信号/时点但数量、V2比例及取整改变的交易单列CHANGED；消失交易保留实际占用/挂单/拒单诊断，不能解释的保留NOT_EVALUATED。旧亏损扩大既给实际USDT也给归一化变化，不能把后者笼统称作价格风险。','', '5. V2 EXTRA实际请求/执行次数（C1；2025单独条件样本，不是额外独立验证）：','', '|区间|I100请求/执行|I50|I25|','|---|---:|---:|---:|']
 for period in periods:
  cells=[]
  for group in ['I100','I50','I25']:
   r=choose(ce,period=period,cost='C1',fill='F_TOUCH',group=group,asset='ETH',origin='EXTRA');cells.append(r['V2_requests']+'/'+r['partial_trades']if r else'未验证')
  lines.append('|'+period+'|'+'|'.join(cells)+'|')
 lines+=['','预算仍是当前余额3%，不是按EXTRA比例缩小；每笔最多一次、初始数量25%上限及步长不变，因此小仓可能更少触发。这是模型运行结果，不是另调V2。','', '6. 资金费与更保守成交：F_THROUGH按真实逐笔越过至少一个tick才按原限价模拟，非真实排队概率；含资金费用C2，缺价年仅C1退路。完整年度指标见annual_matrix，逐笔变化见trade_attribution与fill_sensitivity。收益仍正与相对B仍占优是两件事，C4下相对B改善不能掩盖绝对亏损。早年含资金费未知，所以不能宣称完整真实净优势。','', '7. concentration.csv给每年正向账户归因前5项占比，以及移除这些归因项后的算术差额；这不是删交易重跑，更不是据此筛交易。总差额含仓位、替换、资金费及V2路径，不把少数大盈利说成普遍优势。','', '## 交付与限制','', '固定矩阵、逐情景年度表、逐笔四类归因、成本现金核对、官方资金费原响应及SHA、测试、执行日志和恢复命令全部在本实验目录。2025严格旧失败标签不改，九情景只检验已识别冲突处理，不是官方行情修复、不覆盖其他潜在错误。触价/越价全量成交均为模拟代理，深度、队列与强平未建模；费率是假设而非用户账户实际费率。']
 (O/'CONCLUSION.md').write_text('\n'.join(lines)+'\n');s.dump(O/'conclusion_summary.json',dict(retention_rows=len(ret),attribution_rows=len(attrs),costs_fixed=True,entry_rules_changed=False,conclusion='分区间给出收益与风险代价；早年资金费缺失，不能判定完整实盘净优势',no_year_specific_ratio_selection=True))
 print('CONCLUSION',len(ret),len(attrs))
if __name__=='__main__':
 main()
 import decision_notes
 decision_notes.main()
 import event_exports
 event_exports.main()
 import make_input_manifest
 make_input_manifest.main()
 import scenario_summary
 scenario_summary.main()
