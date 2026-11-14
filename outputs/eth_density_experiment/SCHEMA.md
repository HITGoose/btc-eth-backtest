# 输出口径

## 场景

A/B=.25，C/D=.30，E/F=.35；奇数组A/C/E原出场，B/D/F为V2。只有ETH历史96根最小带宽改变。ZERO=0手续费；ASSUMED_005_SIDE=每边0.0005，即0.05%，明确假设，非用户账户费率。资金费未计。

period=2020为02-16至年底，2026为1—10月，NOV为11-01至13日08:00北京时间，NOV独立500起算；2021—2025完整年。2019未验证。每个区间每币500，不能将USDT合计当跨年复利收益。相同策略不同费用/出场组不是独立样本。

## 指标与对账

- return_pct / ending_equity：完整账户现金+未平仓剩余数量按实际截止价估值；组合初始1000，单币500。
- direction=LONG/SHORT：该方向现金和浮盈亏归因曲线，使用相同初始资本分母，不是另一个独立可交易方向账户；ALL为真实模拟账户路径。
- max_drawdown_pct：同一分钟末组合或单币权益，含期初资本；不代表分钟内最坏回撤。
- worst_month_return_pct：相邻月末收益，partial_month标起止不完整月；2020首月及NOV不冒充完整月。
- closed/open/pending：已平仓/年末持仓/年末挂单数量；未平仓不计胜负。
- gross_winning_trade_net=Σmax(整笔净收益,0)，gross_losing_trade_net=-Σmin(整笔净收益,0)。是净交易正负值的总额，不是手续费前收益。
- profit_factor：上两者比值，无亏损时留空并配标志，不伪造有限数；无交易方向胜率亦空。
- fees_paid_USDT：实际入口/部分退出/剩余退出名义额×场景费率，和stats及余额校验；不含资金费。
- max_loss_per_1000_initial_notional：按同1000USDT初始名义归因的最差单笔，非可执行另一个账户。

## 逐笔归因

按资产、side、signal_close_ms匹配。不存在的键保持ADDED或DISAPPEARED；同键但开平时刻/价格/数量或部分退出实际量价时刻不同为CHANGED；其余RETAINED。部分退出全局stage编号变化不误判经济行为变化。

actual_USDT_delta是本组真实余额累积下的差额；old/new_contribution包括已平仓净额或年末持仓贡献。年度全部contribution之和必须=期末权益-500；类别差额之和必须=实验-基准权益。

normalized_1000_delta及matched_normalized_1000_delta用单笔contribution÷初始开仓名义额×1000，含费用、取整和减仓比例差异，只用于归因；不能作为重新执行的独立账户或新增单叠加到旧收益。

占用原因BLOCKED_POSITION/BLOCKED_PENDING_ORDER带有occupying/pending_signal_close_ms，可追溯对应前序交易；FUNDS_OR_MIN_NOTIONAL、ORDER_EXPIRED_UNFILLED、ORDER_PENDING_AT_END独立区分。账户实际place检查和历史事件重建时点分别标识。

## 只读诊断

conditions.csv.gz是移除历史带宽约束后的完整底层候选方向：≥5线同向、收盘位于六线外、MACD同向；最终6线及所有趋势过滤仍逐项列出。所有.25/.30/.35最终信号均断言包含在此候选集合。不是仅挑BTC盈利时刻，主程序不读取BTC独开样本作信号。

Probe在独立新状态中为候选生成gate，真实回踩状态不被诊断消费。距离/回踩等未计算项NOT_EVALUATED不算通过。diagnostics_区间_费用.csv.gz按资产/信号/组排序，保留所有候选，不按盈亏挑选。

2025放宽组的diagnostics_unverified只在真实已保存月末断点前有账户占用；其后account/cash明确NOT_EVALUATED，指标信号仍可从原生K线独立计算，但不是已验证订单或成交。incomplete_snapshots_2025为断点账本，仅部分时间，不能作全年收益。

## 同时持仓

exact_overlap_seconds从真实模拟成交/退出微秒时间交集计算。negative_cashflows_while_other_position_open包括另一币持仓时发生的负现金流及费用，不等于额外不可归因亏损。worst_combined_floating_PnL和risk统计采用分钟末同时持仓掩码，可能不含分钟内短暂重叠。

reference_stop_giveback是从当前估值价到已生效止损的参考回吐，不保证实际损失；跳价、成交代理、资金费/深度缺失仍有局限。

## 缺失与失败

availability和comparison_six_groups的UNVERIFIED是缺失，不是0。2025 C—F因同日官方原始逐笔冲突而无法跨越，日/月备份字节一致；详情ISSUES.md。七项结论只用可验证比较区间，不将2025基准填充放宽组，也不称全新样本外验证。
