"""Read-only numerical answers; no strategy selection or alternative account simulation."""
from collections import Counter
import csv,json
import shared as s
O=s.OUT

def read(name):
 with (O/name).open(encoding='utf-8-sig')as f:return list(csv.DictReader(f))
def n(v):return float(v)if v not in('',None,'None')else 0.
def pick(rows,**key):return next((r for r in rows if all(r.get(k)==v for k,v in key.items())),None)
def main():
 annual=[r for r in read('annual_matrix.csv')if r['asset']=='COMBINED'and r['direction']=='ALL'];ce=read('core_extra.csv');ret=read('advantage_retention.csv');fill=read('fill_sensitivity.csv');out=[]
 lines=['# 数值答复：EXTRA减仓与真实成本','', '结论：保留B作为正式对照。I50/I25可以保留为固定研究版本，但本轮不能证明可直接替换B：部分区间收益增加同时回撤增加，2023相对B收益反而降低；早年完整资金费缺失。以下均不是样本外，也不逐年选择仓位。','', '## 缩小EXTRA的收益与回撤代价','', '下表使用C1，收益差与回撤差相对同成本B；优势保留率只在I100原本优于B时计算。2025为固定S_ALL展示，必须同时参考九情景范围。','', '|区间|版本|相对B收益百分点|保留I100优势%|相对B回撤百分点|相对I100回撤变化百分点|','|---|---|---:|---:|---:|---:|']
 periods=['2020','2021','2022','2023','2024','2025','2026','NOV']
 for p in periods:
  scene='S_ALL'if p=='2025'else'STRICT'
  for g in ['I100','I50','I25']:
   r=pick(ret,period=p,scenario=scene,cost='C1',fill='F_TOUCH',group=g)
   if not r:continue
   retained='不适用'if r['positive_advantage_retained_pct']==''else f"{n(r['positive_advantage_retained_pct']):.1f}"
   lines.append(f"|{p}|{g}|{n(r['advantage_USDT'])/10:+.3f}|{retained}|{n(r['DD_excess_B_pp']):+.3f}|{n(r['DD_difference_I100_pp']):+.3f}|")
   out.append(dict(r))
 lines+=['','2022/2024/2026缩小EXTRA后的增量回撤有所降低，但不代表已与B风险对齐。2020缩小EXTRA反而削弱了I100原有的回撤改善；2023小仓也不能恢复B收益。2025小仓收益非单调，不能按I100盈亏乘比例代替完整回放。','', '## CORE与V2为何不能按比例缩放','', 'C1、ETH，CORE贡献含已平仓与期末未平仓估值；V2统计只针对EXTRA，最小名义拒单为CORE+EXTRA之和。','', '|区间|版本|CORE贡献U|相对I100 CORE差额U|EXTRA V2请求/实际减仓|有减仓交易平均初始减仓比例%|最低名义拒单|','|---|---|---:|---:|---:|---:|---:|']
 for p in periods:
  scene='S_ALL'if p=='2025'else'STRICT';ref=pick(ce,period=p,scenario=scene,cost='C1',fill='F_TOUCH',group='I100',asset='ETH',origin='CORE')
  for g in ['I100','I50','I25']:
   core=pick(ce,period=p,scenario=scene,cost='C1',fill='F_TOUCH',group=g,asset='ETH',origin='CORE');extra=pick(ce,period=p,scenario=scene,cost='C1',fill='F_TOUCH',group=g,asset='ETH',origin='EXTRA')
   if not core or not extra or not ref:continue
   lines.append(f"|{p}|{g}|{n(core['total_contribution_USDT']):+.2f}|{n(core['total_contribution_USDT'])-n(ref['total_contribution_USDT']):+.2f}|{extra['V2_requests']}/{extra['partial_trades']}|{100*n(extra['mean_actual_reduction_fraction']):.2f}|{int(n(core['minimum_rejections'])+n(extra['minimum_rejections']))}|")
 lines+=['','CORE仍按实际余额×3定量；此处差额已包括余额、费用、V2与路径变化。归一化亏损差见loss_amplification.csv.gz，不能把金额变化全说成价格风险，也不能忽略真实现金回撤。','', '## 成本及保守限价成交','', '仅2024/2025/2026/NOV有完整官方费率、结算时刻与标记价。下面比较同一C2完整账户的触价与越一tick代理；费用每边0.05%、退出滑点0.02%、资金费已进入现金。2025只固定展示S_ALL，九情景全年核对另表。','', '|区间|版本|C2触价收益%|C2越价收益%|越价相对同模型B优势U|越价减触价期末U|成交时刻改变笔数（BTC+ETH）|','|---|---|---:|---:|---:|---:|---:|']
 for p in ['2024','2025','2026','NOV']:
  scene='S_ALL'if p=='2025'else'STRICT'
  for g in ['B','I100','I50','I25']:
   a=pick(annual,period=p,scenario=scene,cost='C2',fill='F_TOUCH',group=g);b=pick(annual,period=p,scenario=scene,cost='C2',fill='F_THROUGH',group=g);base=pick(annual,period=p,scenario=scene,cost='C2',fill='F_THROUGH',group='B')
   d=pick(fill,period=p,scenario=scene,cost='C2',group=g,asset='COMBINED')
   if not(a and b and base and d):continue
   changed=sum(int(n(x.get('entry_time_changed')))for x in fill if x['period']==p and x['scenario']==scene and x['cost']=='C2'and x['group']==g and x['asset']in('BTC','ETH'))
   lines.append(f"|{p}|{g}|{n(a['return_pct']):+.3f}|{n(b['return_pct']):+.3f}|{n(b['ending_equity'])-n(base['ending_equity']):+.2f}|{n(d['actual_difference_USDT']):+.2f}|{changed}|")
 lines+=['','越价全量仍不是排队模型或实盘成交概率。C4下的绝对亏损不能被相对B的优势掩盖；2020—2023完整含资金费未验证，不外推成全历史真实净利润。','', '## 是否依赖少数年份或少数交易','']
 for cost in ['C1','C2','C3','C4']:
  for g in ['I100','I50','I25']:
   aa=[r for r in ret if r['cost']==cost and r['fill']=='F_TOUCH'and r['group']==g and r['scenario']in('STRICT','S_ALL')and r['period']!='NOV']
   if not aa:continue
   lines.append(f"- {cost}/{g}：{len(aa)}个可计算年内区间中，相对B期末权益提高{sum(n(x['advantage_USDT'])>1e-7 for x in aa)}个、降低{sum(n(x['advantage_USDT'])< -1e-7 for x in aa)}个、相同{sum(abs(n(x['advantage_USDT']))<=1e-7 for x in aa)}个；其中回撤高于B {sum(n(x['DD_excess_B_pp'])>1e-7 for x in aa)}个。2025仍是异常条件结果，绝非额外严格样本。")
 concentration=read('concentration.csv');positive=[r for r in concentration if r['comparison_base']=='B']if concentration and'comparison_base'in concentration[0]else concentration
 aa=[r for r in positive if r['cost']=='C1'and r['fill']=='F_TOUCH'and r['group']in('I100','I50','I25')and n(r['actual_difference_USDT'])>1e-7]
 if aa:lines.append(f"- 在C1相对B为正的{len(aa)}个“版本×区间”归因中，扣除正向前5项后的算术差额有{sum(n(r['arithmetic_difference_without_top5'])<=0 for r in aa)}个不再为正。这不是删单后重跑，版本、情景与年份也不能当独立样本相加；仅说明盈利集中度，详见concentration.csv。")
 lines+=['','回撤、尾部亏损、最差月、最长连亏、手续费、资金费收支及原交易变化都在固定矩阵与逐笔文件并列；不因收益增加而忽略它们。综合结论是“局部收益改善，风险与成本代价依区间而异；完整真实成本历史数据仍不足”，不是所有年份优势或实盘替换建议。']
 lines+=['','## 收益与增量回撤是否同比缩小','']
 for p in ['2024','2026']:
  scene='STRICT';full=pick(ret,period=p,scenario=scene,cost='C2',fill='F_TOUCH',group='I100')
  if not full:continue
  for g in ['I50','I25']:
   x=pick(ret,period=p,scenario=scene,cost='C2',fill='F_TOUCH',group=g)
   if x and n(full['advantage_USDT'])>0 and n(full['DD_excess_B_pp'])>0:
    lines.append(f"- {p} C2/{g}：保留I100对B的收益优势{100*n(x['advantage_USDT'])/n(full['advantage_USDT']):.1f}%，保留其增量回撤{100*n(x['DD_excess_B_pp'])/n(full['DD_excess_B_pp']):.1f}%。这里比较的是增量，不是总回撤风险已对齐；取舍并未在各区间普遍改善。")
 rr=[r for r in ce if r['cost']=='C1'and r['fill']=='F_TOUCH'and r['asset']=='ETH'and r['group']in('I50','I25')and r['scenario']in('STRICT','S_ALL')]
 if rr and sum(n(r['minimum_rejections'])for r in rr)==0:lines.append('- 此处已完成C1小仓路径没有最低名义拒单；这些CORE利润差异不能归因于最低名义拒单，应查看余额、数量取整、V2与路径变化。其他压力场景仍分别记录，不能从C1代推。')
 (O/'DECISION_NOTES.md').write_text('\n'.join(lines)+'\n');s.dump(O/'decision_notes.json',dict(fixed_C1_comparisons=out,formal_baseline='B',no_promotion_to_live=True,no_per_year_strategy_selection=True))
 print('DECISION_NOTES',len(out))
if __name__=='__main__':main()
