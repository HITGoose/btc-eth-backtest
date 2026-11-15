from pathlib import Path
import csv,json
O=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
ss=read('state_summary.csv');yy=read('yearly_state.csv');st=read('stage_comparison.csv');rr=read('trade_details.csv');co=read('concentration.csv');cn=read('consistency.csv');FEES=['ZERO','MAKER_002_SIDE'];STATES=['顺势单边','逆势单边','range','transition']
for name in ['BTC','ETH','COMBINED']:
 with(O/(name+'_state_summary.csv')).open('w',encoding='utf-8-sig',newline='')as stream:
  writer=csv.DictWriter(stream,fieldnames=list(ss[0]));writer.writeheader();writer.writerows([r for r in ss if r['asset']==name])
def f(x,n=2):return '—'if x in ['',None]else f'{float(x):.{n}f}'
def sel(rs,asset,fee=None,anchor=None):return[r for r in rs if r['asset']==asset and(fee is None or r['fee_scenario']==fee)and(anchor is None or r.get('label_anchor')==anchor)]
text='''# A_BASE只读行情状态与未平仓归因

**结论：不建议进入动态杠杆回放。** BTC/ETH的顺势及range归一化收益方向不同，BTC两阶段出现符号翻转；BTC range的账面优势显著依赖2024唯一一笔未平赢家。逆势单边两锚点均无样本，不能排名。以下只读描述既有成交选择后的分布，不是状态的因果收益、未来预期或新策略验证。

## 配置与时间口径

- 源分支codex/a-exit-regime-sizing-20261115，锁定060e12a18bc745a7c98e5270f2e37b0c759cc5ff；仅A_BASE fixed/LADDER_CAP=5，ZERO与MAKER_002_SIDE。没有导入回放器、创建账户或修改策略/账本。
- **本次归因ER为24h/120h、阈值0.20/0.10，与实际入场12h/120h、约0.28284271247461906/0.10不同。** 使用work/backtest_squeeze_short.py的原hourly_regimes函数原样AST提取，不执行该模块的回测入口。
- `signal_close_ms`是信号K线收盘/决策时刻，并非实际提交时间。实际下单原定为+10秒；trade_details.csv另保留scheduled_submission_us、effective_submission_us和对应标签。全部1800条费用情景记录的信号与实际提交归属同一已闭小时，主表依用户指定以signal_close_ms冻结；不把成交后标签用于订单数量。
- 第二锚点FILL使用opened_us的当时最后已闭小时，只作事后归因。每个锚点独立汇总同一批交易，不能将两锚点或两费用情景当作独立样本相加。两费用成交键和开平时间一致：每费用895笔已平、5笔独立年度期末未平。
- 组合归一化均值直接合并两币逐笔记录等权计算，不先平均币种均值；组合金额为实际USDT贡献相加。
- 每根小时由4根完整15m聚合，信号/成交均取已闭小时，整点包含刚收盘小时；未知/缺失标签会中止而不默认range。未来小时扰动测试不影响过去标签。
- 顺势：多/up或空/down；逆势：多/down或空/up；range：双周期均无方向；transition：其余不同方向状态。原入场暂停的是12h/120h transition，故本次24h/120h出现transition不等于原规则违规。120h与原入场相同，信号时刻逆势零样本也有入场选择的结构性原因。
- r1000不是年化收益，未按持仓时长调整；长期未平与短线已平需结合时长和两种口径阅读，不能仅凭均值比较资本效率。
- 已平净额沿原账本，含已发生手续费和退出滑点。未平浮盈沿原期末mark，**账户贡献=已平净额+未平浮盈−未平已付入场费**。不假设平仓、不补未来退出费用。未平不计入已平胜率。持仓时长截至各自区间结束，不是实际平仓时长。
- r1000为逐笔`1000*净额/初始实际成交名义`，单位为每1000USDT初始名义的USDT损益；均值是逐笔等权算术平均，中位数也是逐笔分布。含未平的主口径先扣已付入场费，CSV另列不扣该费的浮盈口径，不用总盈亏/总名义替代平均。
- 2020仅02-16起、2026仅1—10月，按原北京时间年度边界独立起算，每币500；不把期末持仓跨年串起来。15m信号+1m OHLC假设执行，零资金费，原0.02%退出滑点。0.02%费用仅为原账本假设，不是实际Maker费率验证。已反复查看的年份仅做描述性阶段切分，不称新样本外。

'''
for asset,title in [('BTC','BTC单独表'),('ETH','ETH单独表'),('COMBINED','BTC＋ETH组合汇总表')]:
 text+='## '+title+'\n\n### 信号时刻标签：已平与期末未平贡献\n\n'
 for fee in FEES:
  text+='**'+fee+'**\n\n|状态|已平N／胜率%|已平净额|未平N／浮盈|未平入场费|未平持仓h均值／中位|账户总贡献|\n|---|---:|---:|---:|---:|---:|---:|\n'
  for r in sel(ss,asset,fee,'SIGNAL_CLOSE'):text+=f"|{r['state']}|{r['closed_count']} / {f(r['closed_win_rate_pct'])}|{f(r['closed_net_USDT'])}|{r['open_count']} / {f(r['open_unrealized_USDT'])}|{f(r['open_entry_fee_USDT'],4)}|{f(r['open_holding_hours_mean'])} / {f(r['open_holding_hours_median'])}|{f(r['total_account_contribution_USDT'])}|\n"
 text+='\n### 逐笔归一化：均值与中位数\n\n每1000初始名义USDT，含未平主口径已扣未平入场费。N=0不估计期望，不强行排名；少量样本详见CSV原始N。\n\n|费用|状态|已平N|已平r均／中位|含未平N|含未平r均／中位|\n|---|---|---:|---:|---:|---:|\n'
 for fee in FEES:
  for r in sel(ss,asset,fee,'SIGNAL_CLOSE'):text+=f"|{fee}|{r['state']}|{r['closed_count']}|{f(r['closed_r1000_mean'])} / {f(r['closed_r1000_median'])}|{r['all_record_count']}|{f(r['all_marked_net_r1000_mean'])} / {f(r['all_marked_net_r1000_median'])}|\n"
 text+='\n### 2020—2026逐年均值\n\n每格为“已平逐笔均值 / 含未平逐笔均值（已平N＋未平N）”。逆势无样本用—，不是零收益。完整逐年中位数、金额和持仓时长见yearly_state.csv。\n\n'
 for fee in FEES:
  text+='**'+fee+'：SIGNAL_CLOSE**\n\n|年|顺势单边|逆势单边|range|transition|\n|---|---:|---:|---:|---:|\n'
  for y in range(2020,2027):
   ix={r['state']:r for r in sel(yy,asset,fee,'SIGNAL_CLOSE')if r['year']==str(y)};cells=[]
   for state in STATES:
    r=ix[state];cells.append(f"{f(r['closed_r1000_mean'])} / {f(r['all_marked_net_r1000_mean'])} ({r['closed_count']}+{r['open_count']})")
   text+='|'+str(y)+'|'+'|'.join(cells)+'|\n'
 text+='\n### 两阶段描述性对比\n\n|费用|阶段|状态|已平N|已平r均／中位|含未平N|含未平r均／中位|\n|---|---|---|---:|---:|---:|---:|\n'
 for fee in FEES:
  for stage in ['2020_2022','2023_2026']:
   for r in sel(st,asset,fee,'SIGNAL_CLOSE'):
    if r['stage']==stage:text+=f"|{fee}|{stage}|{r['state']}|{r['closed_count']}|{f(r['closed_r1000_mean'])} / {f(r['closed_r1000_median'])}|{r['all_record_count']}|{f(r['all_marked_net_r1000_mean'])} / {f(r['all_marked_net_r1000_median'])}|\n"
 text+='\n### 实际成交时刻标签（只作事后对照）\n\n|费用|状态|已平N／胜率%|已平净额|未平N／浮盈|账户总贡献|已平r均／中位|含未平r均／中位|\n|---|---|---:|---:|---:|---:|---:|---:|\n'
 for fee in FEES:
  for r in sel(ss,asset,fee,'FILL'):text+=f"|{fee}|{r['state']}|{r['closed_count']} / {f(r['closed_win_rate_pct'])}|{f(r['closed_net_USDT'])}|{r['open_count']} / {f(r['open_unrealized_USDT'])}|{f(r['total_account_contribution_USDT'])}|{f(r['closed_r1000_mean'])} / {f(r['closed_r1000_median'])}|{f(r['all_marked_net_r1000_mean'])} / {f(r['all_marked_net_r1000_median'])}|\n"
 text+='\n成交标签的逐年与阶段完整表也已在yearly_state.csv、stage_comparison.csv中输出label_anchor=FILL，不把它回填到signal标签。未平持仓均/中位时长等完整字段见state_summary.csv。\n\n'
text+='''## 未平大单与集中度

2024 BTC多单在信号与成交时刻均为range，期末浮盈1799.04，持有7896.36小时（约329.01天），r1000约1213.64。不能因其后来长期上涨就把入场时状态改标为顺势。BTC range已平逐笔r均值仅0.99，含这笔未平后升至6.74；它显著抬高了range的账面优势。

BTC信号时顺势已平USDT为+236.90，但逐笔等名义r均值为-0.68：账户余额和仓位路径使USDT总额与等名义均值方向不同，不能混为同一结论。ETH顺势的已平r均值为+3.26，故“顺势统一放大”缺乏双币重现证据。

BTC顺势早/晚阶段r均值为-1.86/+0.42；BTC transition为-4.42/+2.57；ETH range为-2.87/+1.08，均出现阶段符号翻转。ETH顺势为+4.64/+2.62，6/7个年度已平均值为正，但2023均值-6.33且有32笔，不能由ETH单边现象推成双币统一稳定优势。ETH transition两阶段负，BTC同类后阶段却正；同样不支持统一调权。

两锚点逆势单边均为0样本，无法比较该状态收益。信号到成交状态变化：ZERO BTC16笔、ETH15笔，共31笔；MAKER相同。用成交标签选择下单杠杆会使用提交之后才知道的信息，禁止这样解释本统计。

concentration.csv提供最大单笔/最大年份占总正收益份额，以及移除最大正归一化观察值的只读均值敏感性。只读剔除某笔交易仅作一阶归因参考，不代表顺序占仓下的真实重放结果；未生成任何过滤、杠杆或加仓策略。

## 本轮判断与交付

四状态之间没有得到跨BTC/ETH、跨阶段一致且可据此调杠杆的期望差异。少数未平大单、资产差异和年度反转影响显著；只基于当前统计，**不建议进入动态杠杆回放**。保留原策略与原账户，不据此放大ETH或压低range，不搜索新ER阈值。

- trade_details.csv：每笔双时刻标签、真实模型时间字段、已闭小时、ER24/ER120、归一化收益、持仓时长与源账本SHA；另存actual_submission标签。
- state_summary.csv：BTC、ETH、COMBINED，分别按两费用/两锚点/四状态汇总。
- yearly_state.csv：逐年N、金额、胜率、均值、中位数及未平贡献。
- stage_comparison.csv、consistency.csv：固定两阶段与逐年正负样本计数，不做选参。
- label_transition.csv：信号→成交标签迁移，不重复相加样本。
- concentration.csv：大单/年份集中度和只读描述性敏感性。
- account_reconciliation.csv：28个账户逐一闭合：已平净额+未平浮盈−未平入场费=期末权益−500。
- CONFIG.json、CHECKS.json、input_provenance.csv：配置差异、时间/未来数据核对与缓存来源。

复跑仅统计：`python outputs/a_base_regime_attribution/analyze.py`，再`robustness.py`，再`report.py`。不运行任何回测账户入口，不重新下载行情，不改main或策略。
'''
(O/'CONCLUSION.md').write_text(text);print('Report written, bytes',len(text.encode()))
