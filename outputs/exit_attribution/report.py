from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv
OUT=Path(__file__).resolve().parent
summary=json.loads((OUT/'annual_attribution.json').read_text());trades=json.loads((OUT/'trade_attribution.json').read_text());losses=json.loads((OUT/'second_stage_loss_counts.json').read_text())
matched=sum(q['matched_closed'] for q in summary)
assert matched==sum(q['same_entry_time'] for q in summary)==sum(q['same_final_exit_time'] for q in summary)==sum(q['same_final_exit_price'] for q in summary)
assert all(abs(q['other_execution_pp'])<1e-8 and abs(q['unmatched_pp'])<1e-8 for q in summary)
lines=['# 原ER与动态：已运行历年交易收益差归因','',f'已实际读取两版逐笔交易流水和权益结果，对齐{matched}笔已平仓交易。各匹配单的信号、方向、入场价、实际开仓时间、最终平仓时间和最终平仓价一致。没有未匹配已平仓交易。没有修改策略或重新优化参数。',
 '', '本报告区分早期现货价格合成模拟与币安永续。2017仅11—12月；2020永续仅2月16日至年底；2026仅1—10月。2016没有有效完整逐笔结果，不归因。',
 '', '收益百分点以两币年初总权益1000USDT为分母。第一/第二档影响：每笔实际减仓数量×方向×（实际减仓成交价−最终退出价），因此已经同时包含卖早少赚与提前退出少亏的净效果。余额仓位影响：动态与原ER初始开仓数量差×原ER每单位盈亏；期末未平仓影响另计。这里只是现有两版流水的精确资金分解，并非分别关闭某一档的独立回测；余额反馈不能唯一再拆分归属哪一档。',
 '', '## 币安USDT永续','', '|年份|第一档净影响|第二档净影响|余额/期末影响|总收益差|','|---|---:|---:|---:|---:|']
for q in summary:
 if q['market']!='BINANCE_USDT_PERPETUAL':continue
 other=q['size_feedback_pp']+q['open_end_pp']+q['other_execution_pp']+q['unmatched_pp']
 lines.append(f"|{q['year']}（{q['window']}）|{q['stage1_direct_pp']:+.2f}|{q['stage2_direct_pp']:+.2f}|{other:+.2f}|{q['total_difference_pp']:+.2f}|")
lines+=['', '## 早期现货行情模拟（非永续）','', '|年份|第一档净影响|第二档净影响|余额/期末影响|总收益差|','|---|---:|---:|---:|---:|']
for q in summary:
 if q['market']!='SPOT_PRICE_SIMULATION':continue
 other=q['size_feedback_pp']+q['open_end_pp']+q['other_execution_pp']+q['unmatched_pp']
 lines.append(f"|{q['year']}（{q['window']}）|{q['stage1_direct_pp']:+.2f}|{q['stage2_direct_pp']:+.2f}|{other:+.2f}|{q['total_difference_pp']:+.2f}|")
perps=[q for q in summary if q['market']=='BINANCE_USDT_PERPETUAL'];losers=sum(q['baseline_losing_trades'] for q in perps);unprotected=sum(q['losing_trades_no_reduction'] for q in perps)
lines+=['', '## 已证实的原因','',
 '1. 多数年份第一档顺向1%便卖25%的直接净拖累大于第二档；第一档减少了后来大盈利交易的暴露，节省的回撤/小亏并不足以抵消。按每笔统一1500USDT名义仓位对比、排除后续账户规模差异后，该方向仍在多数年份成立。统一名义仓位只是流水分析，不是新策略回测收益。',
 '2. 第二档趋势减弱并不等于趋势结束。2025两档的直接影响接近，第二档甚至略大；不能把2025收益下降单独归给第一档。',
 f"3. 永续已匹配亏损单{losers}笔，其中{unprotected}笔（{100*unprotected/losers:.1f}%）两档都未执行。这些单子没有获得中途减仓保护，而盈利单先被减掉仓位。此处是各自初始仓位未减，不代表两版绝对仓位数量相同。",
 f"4. 永续第二档实际减仓{losses['second_fills']}次，其中{losses['second_fills_at_loss']}次执行时已相对入场价亏损；其中{losses['second_loss_then_profitable_final']}次随后原阶梯最终盈利。当前规则没有第二档必须盈利的限制，确认存在回调时亏损减仓、随后恢复盈利的情形。",
 '5. 余额路径会放大或抵消直接效应。2025余额和期末因素进一步拖累21.58个百分点；2024、2026这部分反而抵消一些直接损失。2020永续已测窗口的改善主要来自余额/仓位路径，不宜据此认定某一档单独更优。',
 '', '这里精确拆分的是收益差。最大回撤涉及峰值与谷值变化，不能把上述百分点当作各档对回撤的可加总贡献。',
 '', '## 同一笔交易的证据','', '|市场/年份|币种/方向|开仓北京时间|第一档实际价格收益|第二档实际价格收益|原ER最终价格收益|', '|---|---|---|---:|---:|---:|']
examples=[]
for q in sorted(trades,key=lambda q:q['stage1_direct_effect_usdt']+q['stage2_direct_effect_usdt']):
 if (q['year'],q['market'],q['asset']) not in [(2019,'SPOT_PRICE_SIMULATION','ETH'),(2025,'BINANCE_USDT_PERPETUAL','ETH'),(2025,'BINANCE_USDT_PERPETUAL','BTC')]:continue
 if any(z['year']==q['year'] and z['market']==q['market'] and z['asset']==q['asset'] for z in examples):continue
 examples.append(q)
for q in examples:
 side=1 if q['side']=='LONG' else -1
 gain=lambda px:100*side*(px/q['entry']-1)
 fills={f['stage']:f for f in q['partial_fills']};t=datetime.fromtimestamp(q['opened_us']/1e6,timezone(timedelta(hours=8))).isoformat(timespec='seconds')
 first=f"{gain(fills[1]['execution_price']):+.2f}%" if 1 in fills else '未执行';second=f"{gain(fills[2]['execution_price']):+.2f}%" if 2 in fills else '未执行'
 lines.append(f"|{q['market']} {q['year']}|{q['asset']} {q['side']}|{t}|{first}|{second}|{gain(q['baseline_exit']):+.2f}%|")
lines+=['', '上表是价格相对入场价的顺向收益率，包含原出场滑点，不是3倍账户收益率。最终退出时点两版完全相同。', '', '明细：annual_attribution.csv/json；trade_attribution.csv/json；unmatched_trades.json为空；second_stage_loss_counts.json保存亏损减仓计数。', '', '执行命令：','```sh','/workspace/.venv-btc-eth-original/bin/python outputs/exit_attribution/analyze.py','/workspace/.venv-btc-eth-original/bin/python outputs/exit_attribution/report.py','```']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');(OUT/'examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2))
print('Saved exact annual/trade attribution and checked',matched,'matched closed trades')
