from pathlib import Path
import csv,json
O=Path(__file__).resolve().parent
load=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
a=load('annual.csv');p=load('period_summary.csv');d=load('downweighted_summary.csv');t=load('btc_2024_long_position.csv');f=json.loads((O/'FREEZE.json').read_text());v=json.loads((O/'verification.json').read_text())
assert len(a)==126 and v['accounts']==84
find=lambda rr,**kw:next(r for r in rr if all(r[k]==str(x)for k,x in kw.items()))
F=lambda x:format(float(x),'.2f')
lines=['# 高波动减仓与固定降杠杆对照','', '## 完成范围与冻结','',f"完成全部84份账户结果：56份新回放、28份经SHA/区间/信号/配置核实的A_BASE复用。每年每币500独立起算，2020仅2月16日起、2026仅1—10月。无V2、无提前退出、无撤单，无资金费。15m信号＋原1m OHLC合成路径，不是RAW逐笔或实盘成交。两种费用不共享金融结果。",'',f"训练期六个A_VOL ZERO账户全部完成后，以{f['successful_submitted_orders']}张成功提交订单的目标杠杆等权平均冻结 L_fixed={f['L_fixed']:.16g}。冻结时刻UTC：{f['frozen_at_UTC']}。包括后来未成交挂单；未使用后续年份。固定方案训练期是回顾性校准对照；2023—2026为冻结后时间切分检验，已有年份被反复观察，不称全新样本外。",'','## 逐年组合结果','', '净盈亏包含期末按最后1m收盘估值的未平浮盈，减去已付入场费；不能当成全部已兑现收益。回撤为每年同分钟BTC＋ETH权益最大回撤。','']
for fee in ['ZERO','MAKER_002_SIDE']:
 lines+=['### '+fee,'','|区间|原3x净盈亏|高波动减仓净盈亏|固定降杠杆净盈亏|原／动态／固定回撤|原／动态／固定已平数|','|---|---:|---:|---:|---|---|']
 for y in range(2020,2027):
  rr=[find(a,period=y,asset='COMBINED',fee_scenario=fee,group=g)for g in ['A_BASE','A_VOL','A_FIXED_LOW']];lines.append('|'+str(y)+'|'+'|'.join(F(r['net_pnl_USDT'])for r in rr)+'|'+' / '.join(F(r['max_drawdown_pct'])+'%'for r in rr)+'|'+' / '.join(r['closed_trades']for r in rr)+'|')
 lines+=['','|独立区间合计|原3x|高波动减仓|固定降杠杆|动态相对原／固定|动态胜出年数相对原／固定|动态回撤降低年数相对原／固定|','|---|---:|---:|---:|---|---|---|']
 for stage in ['TRAIN_2020_2022','LATER_2023_2026','ALL_7']:
  rr=[find(p,stage=stage,asset='COMBINED',fee_scenario=fee,group=g)for g in ['A_BASE','A_VOL','A_FIXED_LOW']];q=rr[1];lines.append('|'+stage+'|'+'|'.join(F(r['net_pnl_USDT'])for r in rr)+'|'+F(q['difference_vs_base_USDT'])+' / '+F(q['difference_vs_fixed_low_USDT'])+'|'+q['outperform_years_vs_base']+' / '+q['outperform_years_vs_fixed_low']+'|'+q['lower_drawdown_years_vs_base']+' / '+q['lower_drawdown_years_vs_fixed_low']+'|')
 lines+=['','|后期2023—2026|已平净额|期末浮盈合计|未平入场费用|总亏损|最大单亏|平均实际入场杠杆|含空仓分钟敞口|','|---|---:|---:|---:|---:|---:|---:|---:|']
 for g in ['A_BASE','A_VOL','A_FIXED_LOW']:
  q=find(p,stage='LATER_2023_2026',asset='COMBINED',fee_scenario=fee,group=g);lines.append('|'+g+'|'+'|'.join(F(q[k])for k in ['closed_net_USDT','end_unrealized_USDT','open_entry_fee_USDT','total_loss_USDT','max_single_loss_USDT','avg_actual_entry_leverage','timeweighted_gross_equity'])+'|')
 lines+=['','七期仅USDT简单合计，不跨年复利，不把重置账户拼接计算回撤。完整BTC、ETH分年胜率、最大单亏、现金和浮盈见 annual.csv。','']
lines+=['## 减仓归因','', '以下仅汇总A_VOL目标L<3的匹配交易；实际USDT同时受历史余额变化影响，每1000初始名义的差额另列。基准期末未平仓不称最终赢家或输家。归因不是可相加的独立反事实收益。','', '|费用|阶段|基准结局|匹配数|基准贡献|动态贡献（含未匹配）|匹配实际差额|匹配每1000名义差额合计|','|---|---|---|---:|---:|---:|---:|---:|']
for fee in ['ZERO','MAKER_002_SIDE']:
 for stage in ['TRAIN_2020_2022','LATER_2023_2026','ALL_7']:
  for cat in ['BASE_WIN','BASE_LOSS','BASE_OPEN_AT_END','NO_BASE_FILL']:
   q=find(d,stage=stage,asset='COMBINED',fee_scenario=fee,base_outcome=cat);lines.append('|'+fee+'|'+stage+'|'+cat+'|'+q['matched_fills']+'|'+'|'.join(F(q[k])for k in ['base_contribution_USDT','variant_contribution_USDT','matched_actual_difference_USDT','matched_sum_r1000_difference'])+'|')
lines+=['','## 2024年BTC约329天未平仓','', '|费用|版本|初始数量|初始实际名义|实际入场杠杆|期末浮盈|已付入场费|期末贡献|该信号动态目标L|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
for q in t:lines.append('|'+q['fee_scenario']+'|'+q['group']+'|'+q['quantity']+'|'+'|'.join(F(q[k])for k in ['notional_USDT','actual_entry_leverage','unrealized_USDT','open_entry_fee_USDT','contribution_USDT','vol_target_L'])+'|')
lines+=['','该信号不做特殊保留。即使目标杠杆不超过3，之前交易减少亏损带来的现金增长仍可能让后续实际数量高于原基准；这属于完整账户复利路径，不能误认作突破杠杆上限。','', '## 数据、核对和文件','', '- ATR96采用Wilder RMA、96根有效TR均值初始化。参考中位数严格shift(1)，包含当前的ATR只来自已闭15m；不足2880有效历史或无效时回退3x且记录。原缓存预热区间足够，实际次数见 annual.csv。', '- 数量向下取整和最小名义沿用原逻辑；所有成功提交订单逐笔校验目标名义与步长差额，拒单见 sizing_audit.csv；不能把信号不变等同于成交必然不变。', '- 敞口是分钟末gross/equity的时间平均，含全部空仓分钟；组合先汇总两币gross和equity再求比，不取两个杠杆均值。是分钟网格估计，不是连续时间精确积分。入场实际杠杆分母为入场费扣除前本币权益，包含期末未平仓成交。', '- 每账户现金、现金事件、已平净额、未平浮盈、入场费、最终权益均对账，残差<1e-7。原信号集合相同；无V2、退出fixed、LADDER_CAP=5、pause_transition=True。5档是锁利上限，不是盈利5%立即卖出。', '- 每边0.02%为假设费率，不代表确认的用户Maker费率；所有退出保留0.02%不利滑点，资金费明确排除。', '- 数据来自已有币安USDT永续15m和1m缓存，逐账户input.json及baseline_reuse.json记录源文件、区间和SHA；本轮没有下载行情。2025也为1m OHLC口径，不能引用其他RAW实验的异常模式结果作逐笔验证。', '- annual.csv：逐年分币及组合；period_summary.csv：阶段独立合计；exposure.csv：敞口；trades.csv、trade_matching.csv：含期末未平的完整逐笔匹配；account_decomposition.csv：新增/消失/匹配变化完整对账；downweighted_*：减仓归因；btc_2024_long_position.csv：长期持仓；sizing_audit.csv：成功/拒绝订单与取整；verification.json：核对；FREEZE.json：冻结；RUN.md：复跑命令。','']
(O/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
print('WROTE RESULTS.md')
