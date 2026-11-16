from pathlib import Path
import csv,json
O=Path(__file__).resolve().parent
load=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
a=load('annual.csv');p=load('period_summary.csv');risk=load('risk_summary.csv');att=load('attribution_summary.csv');mt=load('trade_matching.csv');ts=load('trades.csv');long=load('btc_2024_long_position.csv');verify=json.loads((O/'verification.json').read_text());assert len(a)==84 and verify['accounts']==56
find=lambda rr,**kw:next(r for r in rr if all(r[k]==str(v)for k,v in kw.items()))
f=lambda x:format(float(x),'.2f')if x not in ['',None]else'—'
lines=['# ATR自适应初始止损＋单笔计划风险上限','', '**结论：不建议保留为正式策略。** 更近的止损确实减少许多原亏损单的损失，但误杀原盈利单的代价更大；2023—2026仅2024收益改善，2025、2026回撤扩大。未追加其他参数或策略。','', '完成28个A_ATR_STOP新账户完整回放，复用28个核验一致的A_BASE，全部56份账户现金、交易及期末估值对账通过，最大残差'+str(verify['max_ledger_residual'])+' USDT。main及旧源码、旧账本未改。','', '## 逐年组合结果','', '净盈亏单位USDT，包含期末按最后1m收盘价计算的未平浮盈，扣已付未平仓入场费。回撤是同分钟合并BTC和ETH权益的各年度最大回撤。2020从北京时间2月16日开始，2026仅1—10月。','']
for fee in ['ZERO','MAKER_002_SIDE']:
 lines+=['### '+fee,'', '|区间|A_BASE净盈亏|ATR止损净盈亏|差额|基准／实验分钟回撤|基准／实验已平数|','|---|---:|---:|---:|---|---|']
 for y in range(2020,2027):
  b=find(a,period=y,asset='COMBINED',fee_scenario=fee,group='A_BASE');v=find(a,period=y,asset='COMBINED',fee_scenario=fee,group='A_ATR_STOP');lines.append('|'+str(y)+'|'+f(b['net_pnl_USDT'])+'|'+f(v['net_pnl_USDT'])+'|'+f(v['difference_vs_base_USDT'])+'|'+f(b['max_drawdown_pct'])+'% / '+f(v['max_drawdown_pct'])+'%|'+b['closed_trades']+' / '+v['closed_trades']+'|')
 lines+=['','|独立区间合计|A_BASE|ATR止损|差额|跑赢年份|回撤扩大年份|','|---|---:|---:|---:|---:|---:|']
 for stage in ['EARLY_2020_2022','LATER_2023_2026','ALL_7']:
  b=find(p,stage=stage,asset='COMBINED',fee_scenario=fee,group='A_BASE');v=find(p,stage=stage,asset='COMBINED',fee_scenario=fee,group='A_ATR_STOP');lines.append('|'+stage+'|'+f(b['net_pnl_USDT'])+'|'+f(v['net_pnl_USDT'])+'|'+f(v['difference_vs_base_USDT'])+'|'+v['outperform_years']+'/'+v['independent_intervals']+'|'+v['higher_drawdown_years']+'/'+v['independent_intervals']+'|')
 lines+=['','|2023—2026合计|已平净额|期末未平浮盈|未平已付入场费|总亏损|最大单亏|含空仓分钟平均敞口|','|---|---:|---:|---:|---:|---:|---:|']
 for g in ['A_BASE','A_ATR_STOP']:
  r=find(p,stage='LATER_2023_2026',asset='COMBINED',fee_scenario=fee,group=g);lines.append('|'+g+'|'+'|'.join(f(r[k])for k in ['closed_net_USDT','end_unrealized_USDT','open_entry_fee_USDT','total_loss_USDT','max_single_loss_USDT','timeweighted_gross_equity'])+'|')
 lines+=['','已平胜率、收益率、期末现金、各币种最大单亏等全部见annual.csv。阶段USDT仅简单合计，不是跨年复利；不计算拼接重置账户的跨年回撤。','']
lines+=['## 是止损效果，还是降低仓位？','', 'ZERO全期1174笔成交（含5笔期末未平）中，只有7笔目标杠杆低于3，全部在2021年；2023—2026的748笔成交目标杠杆全部为3。因此后期变化不能主要归因于降低初始杠杆，而是初始止损收紧、持有时间、释放占仓后的新成交及余额复利路径。数量取整后的实际杠杆略小于目标。','', '|ZERO成交统计|平均d|中位d|1%下限比例|3%上限比例|中间比例|平均实际入场杠杆|平均计划价格风险|','|---|---:|---:|---:|---:|---:|---:|---:|']
for stage in ['EARLY_2020_2022','LATER_2023_2026','ALL_7']:
 r=find(risk,stage=stage,asset='COMBINED',fee_scenario='ZERO',group='A_ATR_STOP');lines.append('|'+stage+'|'+'|'.join(f(100*float(r[k]))+'%'for k in ['mean_initial_d','median_initial_d','d_1pct_fraction','d_3pct_fraction','d_middle_fraction'])+'|'+f(r['mean_actual_entry_leverage'])+'|'+f(100*float(r['mean_planned_price_risk_fraction']))+'%|')
lines+=['', '止损距离统计按实际成交等权，包含期末未平，不把未成交挂单当成交易。两费用场景的信号、成交身份一致，但数量/现金分别完整回放。成功提交订单指标、回退与最小名义拒单在sizing_audit.csv；实际回退0，最低名义拒单0。','', '新组成功挂单的计划价格风险最大为'+f(100*verify['max_submitted_planned_price_risk_fraction'])+'%，上限不包含手续费、滑点或跳价，不承诺实际亏损的硬上限。','', '## 同信号匹配：原赢家与输家的变化','', '以下按资产、方向、signal_close_ms精确匹配，包括已平和期末未平；不能强行把消失交易配到其他信号。实际USDT含数量/余额影响，r1000为每笔按1000USDT初始实际名义归一化的贡献。归因金额不能直接视作可执行账户增益。','', '|ZERO阶段|基准结局|匹配数|实际差额|r1000差额合计|r1000逐笔差额均值|更近止损提前结束的原盈利单|这些单原利润|这些单实验贡献|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
for stage in ['EARLY_2020_2022','LATER_2023_2026','ALL_7']:
 for cat in ['BASE_WIN','BASE_LOSS','BASE_OPEN_AT_END']:
  r=find(att,stage=stage,asset='COMBINED',fee_scenario='ZERO',category=cat);lines.append('|'+stage+'|'+cat+'|'+r['matched_count']+'|'+'|'.join(f(r[k])for k in ['actual_difference_USDT','sum_r1000_difference','mean_r1000_difference'])+'|'+r['original_profitable_early_closer_stops']+'|'+f(r['original_profit_on_early_closer_stops_USDT'])+'|'+f(r['variant_contribution_on_early_closer_stops_USDT'])+'|')
lines+=['', 'ZERO后期原亏损单匹配214笔：209笔单位名义收益改善、1笔恶化、4笔未发生实质变化；实际金额211笔改善、3笔恶化。可见止损减少失败交易损失的作用存在，但不能抵消原盈利单损害。','', '后期匹配493笔（含4笔期末未平）的r1000差额逐笔均值约-1.49 USDT，合计-735.99；仅已平匹配489笔的均值约-1.51 USDT，未平记录不计最终胜负。该结果也不支持“只因仓位更小才少赚”的解释。','', '## 更宽止损的样本','', '只有2021年的7笔实际成交d>2%，没有触及3%上限的成交，不能声称已充分覆盖宽止损极端行情。7笔全部匹配基准：2笔最终亏损均比基准亏得更多，实际合计多亏16.88 USDT，单位1000名义差额合计-5.49；另1笔原亏损单转盈利。其余4笔原盈利单开平价格/时间相同，主要数量变化。逐笔见wider_stop_matching.csv。','', '## 新增、消失及账户完整差额','', '|ZERO阶段|新增成交数|新增贡献|消失成交数|消失基准贡献|匹配变化贡献|账户总差额|','|---|---:|---:|---:|---:|---:|---:|']
dec=load('account_decomposition.csv')
for stage,years in [('2020—2022',range(2020,2023)),('2023—2026',range(2023,2027)),('七期',range(2020,2027))]:
 rr=[r for r in dec if r['fee_scenario']=='ZERO'and int(r['period'])in years];lines.append('|'+stage+'|'+str(sum(int(r['new_fills'])for r in rr))+'|'+f(sum(float(r['new_contribution_USDT'])for r in rr))+'|'+str(sum(int(r['lost_fills'])for r in rr))+'|'+f(sum(float(r['lost_contribution_USDT'])for r in rr))+'|'+f(sum(float(r['matched_difference_USDT'])for r in rr))+'|'+f(sum(float(r['account_difference_USDT'])for r in rr))+'|')
lines+=['', '账户差额=新增贡献−消失基准贡献＋匹配贡献变化，每币每年逐项对账。原信号没有删除；成交消失原因由实际挂单/持仓/定量证据判断，保留NOT_EVALUATED而不猜测。七期消失的原盈利单42笔，原利润1121.03 USDT；这与已匹配但被提前止损的133笔原盈利单是两个不同集合，不重复计算。','', '## 2024年BTC约329天未平仓','', '|费用|组别|是否仍未平|初始数量|初始d|期末贡献|持有天数|','|---|---|---|---:|---:|---:|---:|']
for r in long:lines.append('|'+r['fee_scenario']+'|'+r['group']+'|'+r.get('record_type','NO_FILL')+'|'+r.get('quantity','')+'|'+f(100*float(r['initial_d']))+'%|'+f(r['contribution'])+'|'+f(r['holding_days'])+'|')
lines+=['', '这笔信号在新组仍成交并持有到年底，未被1%初始止损结束；但ZERO数量从0.0344降为0.0333，期末贡献少57.53，原因是此前账户余额路径改变，不是对该单降杠杆。没有为此单设置保留例外。','', '## 核对、限制与交付','', '- 原A完整信号与缓存逐文件SHA、区间、配置核对；仅新组28账户回放，基准28份原结果复用。新子类通过原CONTROL继承链，原源码不写入；无V2及其他实验。','- 已验证ATR96种子及递推、未来数据不影响前缀、信号已闭15m与限价计算一致、数量向下取整和最低名义、初始止损在成交同事件先于止损检查生效、阶梯只收紧、费用及现金闭合。','- 原visit副本的入场费用显式读取同值self.fee，避免副本持有旧全局费率；这是实现绑定，未改变费率。执行检查在正式账户回放之前发现并修正，没有错误费用账本进入最终结果。','- 所有执行为15m信号＋1m OHLC原分钟内路径与5秒相位2轮询，不是RAW逐笔或实盘成交。保留基准既有数据/执行标签；2025不能由此冒充原始逐笔异常已修复。资金费按本轮明确设0。','- 每边0.02%只是固定假设，止损退出不保证Maker；出场不利滑点均0.02%。已有历史反复观察，不称全新样本外。','- 不改变ATR参数、上下限、仓位或其他规则，没有追加实验组。','', '[年度及分币CSV](annual.csv) · [逐笔CSV](trades.csv) · [逐笔匹配](trade_matching.csv) · [归因汇总](attribution_summary.csv) · [风险分布](risk_summary.csv) · [敞口](exposure.csv) · [账户差额](account_decomposition.csv) · [长期持仓](btc_2024_long_position.csv) · [核对](verification.json) · [复现命令](RUN.md)','']
(O/'CONCLUSION.md').write_text('\n'.join(lines),encoding='utf-8')
wide=[r for r in mt if r['variant_d']and float(r['variant_d'])>.02]
keys=list(dict.fromkeys(k for r in wide for k in r))
with(O/'wider_stop_matching.csv').open('w',encoding='utf-8-sig',newline='')as fh:w=csv.DictWriter(fh,fieldnames=keys);w.writeheader();w.writerows(wide)
print('WROTE CONCLUSION.md')
