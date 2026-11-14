from pathlib import Path
from collections import Counter
import json,csv
import strategy as z
OUT=z.OUT

def readcsv(name):
 with(OUT/name).open(encoding='utf-8-sig',newline='')as f:return list(csv.DictReader(f))
def fnum(value):return float(value)if value not in('',None)else 0.
def total(rows,key):return sum(fnum(x.get(key))for x in rows)
if __name__=='__main__':
 a=json.loads((OUT/'analysis.json').read_text());audit=json.loads((OUT/'audit.json').read_text());assert audit['verification_passed']
 stats=json.loads((OUT/'summary_stats.json').read_text());m={(x['period'],x['cost'],x['group'],x['asset'],x['direction']):x for x in a['metrics']};quality=readcsv('signal_quality.csv');filters=readcsv('btc_filter_audit.csv');shadow=readcsv('shadow_results.csv');conc=readcsv('concentration_overall.csv');extra_conc=readcsv('extra_profit_concentration.csv')
 def stat(g,cost,base='B'):return next(x for x in stats if x['variant']==g and x['base']==base and x['cost']==cost)
 def priorities(g,cost):return[x for x in a['priority']if x['group']==g and x['cost']==cost]
 lines=['# 结论：正式策略保留0.25%，不将本轮改动合入main','','G（BTC确认）和I（两者结合）在已验证区间增加了账户收益，I也明显减少了CORE被挤占；但它们没有同时解决总亏损、回撤和最差月的代价，2023收益仍低于B，2025新组未验证。**保留B作为正式基准；I/G只保存独立实验结果，不继续调参制造正收益。H单独启用优先替换在费用压力后反而不及B。**','','这些是已有年份上的固定规则对照，不是独立样本外验证，也不是目标机器人原始规则已获证实。资金费未计，假设手续费不是用户实际费率。','','## 已完成范围','','B=.25 V2；D=.30 V2；G=仅EXTRA需同根BTC原策略完整信号同向；H=CORE优先；I=两者。全部原ER BASELINE、use_entry_crosses=False。没有.35或其他阈值搜索，BTC始终.25 V2。','每个区间各币500，已实现余额×3；每组每费用独立完整账户路径。2020仅02-16至年底，2021—2024全年，2026仅1—10月；NOV独立11-01至11-13 08:00北京时间，不拼接全年。2025 B全年完成，D/G/H/I各费率真实尝试后因冲突ID停止，不能填0或用B替代。',f"原32＋入场/执行39＋归因8＋影子12＋完整循环边界8＋断点8共107项通过；另46项存档引用检查通过。2024/25既有对照闭仓/权益复现；其余B/D在可验证区间亦精确复现。完成{audit['completed_portfolio_scenarios']}个组合情景、{audit['completed_account_checks']}次资产账本核对，648条指标、10,994条配对归因记录。它们不是等量独立样本。",'当前云端2024/25 BTC及全部ETH新播放；其他BTC只读复用同策略独立对照，完整信号和原生缓存SHA一致，未用旧ETH结果供给新订单行情。所有实际回放用币安USDT永续官方原始逐笔，无OHLC高低顺序兜底。','','## 完整账户收益差额','','下表是7个独立已验证区间的USDT差额合计，**不是跨年复利收益率**；不含2025新组。ZERO与每边.05%假设分别重放，资金费未计。','','|组|相对D：零费 / 假设费U|相对B：零费 / 假设费U|假设费下相对B总亏损增加U|','|---|---:|---:|---:|']
 for g in('G','H','I'):
  d0=stat(g,'ZERO','D');df=stat(g,'ASSUMED_005_SIDE','D');b0=stat(g,'ZERO');bf=stat(g,'ASSUMED_005_SIDE')
  lines.append(f"|{g}|{d0['actual_USDT_delta']:+.2f} / {df['actual_USDT_delta']:+.2f}|{b0['actual_USDT_delta']:+.2f} / {bf['actual_USDT_delta']:+.2f}|{bf['gross_loss_delta']:+.2f}|")
 lines+=['','## 五组年度／独立区间收益与回撤','','每格为“收益% / 最大回撤%”。回撤按分钟末组合权益，不是逐笔峰谷最大回撤。','','### ZERO：零手续费','','|区间|B|D|G|H|I|','|---|---:|---:|---:|---:|---:|']
 for cost in z.COSTS:
  if cost!='ZERO':lines+=['','### ASSUMED_005_SIDE：每边0.05%假设手续费','','|区间|B|D|G|H|I|','|---|---:|---:|---:|---:|---:|']
  for period in['2020','2021','2022','2023','2024','2025','2026','NOV']:
   row=[]
   for g in z.GROUPS:
    x=m.get((period,cost,g,'COMBINED','ALL'));row.append(f"{x['return_pct']:+.2f} / {x['max_drawdown_pct']:.2f}"if x else'未验证')
   lines.append('|'+period+'|'+'|'.join(row)+'|')
 lines+=['','## 1. BTC确认是否提高EXTRA质量？','','在已完成区间，实际闭仓EXTRA的单位初始名义收益提高；不能因此声称统计显著或每个被拒信号都差。CORE/EXTRA按当时完整信号分类，与账户匹配中的ADDED不是同一概念。','','|组|费用|EXTRA已平赢/亏|EXTRA净额U|平均净额/1000初始名义U|','|---|---|---:|---:|---:|']
 for g in('D','G','H','I'):
  for cost in z.COSTS:
   use=[x for x in quality if x['group']==g and x['cost']==cost and x['origin']=='EXTRA'and x['direction']=='ALL'];n=total(use,'closed');mean=sum(fnum(x['mean_net_per_1000'])*fnum(x['closed'])for x in use)/n if n else 0
   lines.append(f"|{g}|{cost}|{int(total(use,'wins'))}/{int(total(use,'losses'))}|{total(use,'net'):+.2f}|{mean:+.2f}|")
 valid=[x for x in filters if x['cost']=='ZERO'and x['D_status']!='NOT_EVALUATED'];rejected=[x for x in valid if x['BTC_confirm_pass']=='False'];dclosed=[x for x in rejected if x['D_status']=='CLOSED']
 lines += ['',f"七个可验证区间共有{len(valid)}个EXTRA候选，BTC过滤拒绝{len(rejected)}个，其中{len(dclosed)}笔在D实际闭仓（41赢/40亏）；这些被过滤的D交易本身零费净赚{total(dclosed,'D_net'):.2f}U。因此过滤不是简单删掉亏损单，而是改变账户占用路径。通过确认的D已平EXTRA仅17笔，样本很小；其后续表现只作事后归因，没有用于决定过滤。2025另有182候选的D结果NOT_EVALUATED，不混入收益统计。",'G实际成交EXTRA多于D样本中通过确认的17笔，是账户占用变化后额外获得了机会；不能把两者强行一一配对。归一化只是归因，不是另开资金的可执行策略。','','## 2. CORE优先是否减少挤占？','','是。D原来缺少43笔B基准交易；H恢复39笔（26笔原盈利、13笔原亏损），仍缺4笔；I恢复42笔（28笔原盈利、14笔原亏损），仍缺1笔原盈利。恢复按资产/方向/原signal_close_ms匹配，不保证数量和后续收益完全恢复。','','|组|撤EXTRA挂单|提前退出 同向/反向|随后CORE提交/成交/过期|假设费下主动退出整笔net U|','|---|---:|---:|---:|---:|']
 for g in('H','I'):
  use=priorities(g,'ASSUMED_005_SIDE');lines.append(f"|{g}|{int(total(use,'cancelled_EXTRA_orders'))}|{int(total(use,'active_exit_same_direction'))}/{int(total(use,'active_exit_opposite_direction'))}|{int(total(use,'replacement_CORE_submitted'))}/{int(total(use,'replacement_CORE_filled'))}/{int(total(use,'replacement_CORE_expired'))}|{total(use,'active_exited_full_trade_net'):+.2f}|")
 lines+=['','主动退出整笔net包含此前V2部分退出和完整开仓费，不能直接称为相对不替换的增量损失。H有12笔替换后的CORE过期未成交；I有1笔，没有把已提交当作恢复成交。stop优先、同向/反向替换、同事件不得退出再填及重复请求锁定已测试。','','## 3. 提前退出和重开成本是否抵消改善？','','H：是。相对B零费+160.43U，假设手续费后−81.02U，完整账户手续费多195.73U；不能只宣传恢复了26笔原盈利单。','I：没有完全抵消收益改善，但仍有代价。相对B假设费后+269.07U，总手续费多102.11U；其EXTRA单位名义收益低于G，但CORE恢复更多，完整账户结果好于G。这不是把独立新增单收益加到账户。','','独立影子从每次强制退出前同一持仓状态按原V2继续，不加入后续CORE。假设手续费下：']
 for g in('H','I'):
  use=[x for x in shadow if x['group']==g and x['cost']=='ASSUMED_005_SIDE'];lines.append(f"- {g}：估计失去收益{total(use,'estimated_foregone_profit'):.2f}U、避免损失{total(use,'estimated_avoided_loss'):.2f}U，实际减影子合计{total(use,'actual_minus_shadow'):+.2f}U。")
 lines+=['','影子差额不是另一条完整账户回测，不可与CORE收益直接相加。实际完整账户收益与费用已经单独对账。','','## 4. 扣费后是否优于原0.25%？','','描述性的独立区间合计：G、I优于B，H低于B。但G/I都只在2020、2022、2024、2026提高收益；2021和独立NOV相同，2023更低。I在2020费用压力下仍亏8.75%，没有为了每年转正继续调规则。2025新组缺失，不能宣称完整历史优势或真实实盘净收益。','','## 5. 总亏损、回撤或尾部是否恶化？','']
 for g in('G','H','I'):
  x=stat(g,'ASSUMED_005_SIDE');lines.append(f"- {g}/B：总亏损金额增加{x['gross_loss_delta']:.2f}U；回撤恶化区间{x['DD_worsened']}，最差月恶化{x['worst_month_worsened']}；ETH最大单笔USDT亏损恶化{x['tail_USDT_worsened']}，同1000初始名义最大单亏恶化{x['tail_per1000_worsened']}。")
 lines+=['','匹配原亏损单的扩大要分清仓位：假设费场景G/H/I实际USDT亏损扩大104/61/109笔，归一化后扩大41/47/49笔。这些匹配扩大案例的入场/退出及部分退出价格、时点未变，差异来自余额累积、初始数量与V2减仓比例/步长取整，不能当作价格风险变坏。新交易和整个组合的亏损、回撤代价仍是真实模拟结果，不能因此忽略。详见loss_amplification.csv。','','## 6. 改善是否依赖少数年份或交易？','','H零费改善主要依赖2020，其他若干年损失抵消收益；费用后总差额转负。G/I的改善分布在4个年内区间，非只靠一年，但仍对少数正向归因项敏感：']
 for g in('G','H','I'):
  x=next(x for x in conc if x['variant']==g and x['base']=='B'and x['cost']=='ASSUMED_005_SIDE');y=next(x for x in extra_conc if x['group']==g and x['cost']=='ASSUMED_005_SIDE')
  lines.append(f"- {g}：前5项正向归因占全部正向差额{fnum(x['top5_positive_share'])*100:.1f}%；扣除这5项后的算术差额{fnum(x['delta_without_top5_positive_attribution']):+.2f}U。实际EXTRA盈利中前5笔占{fnum(y['top5_profit_share'])*100:.1f}%。")
 lines+=['','上述扣除只是归因敏感度，不是删掉5笔后重跑账户，更没有据此筛交易或改规则。已有年份被反复查看，不称样本外。','','## 对账、阻断与交付','','已平仓净额＋未平仓开仓费/部分退出/期末估值＝期末权益−500；现金事件与现金、费用与完整成交turnover均通过。BTC在所有版本相同，不能把复用结果当额外独立样本。','2025-08-29 ETH官方日ZIP SHA053164460ed94f8b586ffd2e2d01e85612e752031f06b7d51776f27c7f6aa9db与当前官方checksum一致，但3个重复ID内容冲突；上轮月档目标日逐字节相同证据保留，本轮没有再次盲下月包。D/G/H/I两费率分别尝试均停止。同财务代码月末断点保留到2025-08-01 00:00北京时间，之后不能当全年结果。', '3月25日一次下载SHA不匹配已隔离，重新取得官方正确文件后恢复；未使用错误文件计算。未猜价、删冲突记录、改交易所或用OHLC兜底。','2019未验证，NOV截止以后未验证。资金费缺失、真实账户费率未知、深度和队列未建模，限价触达全量只是模拟代理。','','主要文件：comparison_five_groups.csv（五组完整表），yearly_metrics.csv（分资产/方向），trade_attribution及四类CSV，btc_filter_audit/summary，signal_quality，priority_events/summary，shadow_results/summary，loss_amplification，cash_reconciliation，concentration，data_check、coverage及来源/运行日志。执行命令及数据恢复见EXPERIMENT.md。','代码与结果均在独立实验分支codex/eth-core-priority-btc-confirm-20261114；源提交01937b2d4a1306ab211a9c1853bda285258c2853，冻结财务代码提交2292b8a2cfc7d802c639014cba1b8ae7d1ef917c。不合并main，不替换正式策略。']
 text='\n'.join(lines)+'\n';(OUT/'CONCLUSION.md').write_text(text)
 detail=(OUT/'report.md').read_text()
 # Idempotently avoid recursively embedding an earlier combined report.
 if '\n<!-- DETAIL_REPORT -->\n'in detail:detail=detail.split('\n<!-- DETAIL_REPORT -->\n',1)[1]
 (OUT/'report.md').write_text(text+'\n<!-- DETAIL_REPORT -->\n'+detail)
 print('WROTE_CONCLUSION',len(lines),'lines')
