# 字段与比较口径

- comparison_five_groups：同区间每币500，BTC+ETH权益收益及分钟末回撤；ZERO/ASSUMED_005_SIDE为独立现金路径。UNVERIFIED空值不得当0。2020部分年、2026 Jan—Oct、NOV独立截止11-13 08:00。
- yearly_metrics：按资产与方向列收益、权益、回撤、最差月、连续亏损、盈亏总额、最大单亏、胜率、盈利因子和费用。LONG/SHORT只是同账户方向损益归因，并非另有资金的账户。
- trade_attribution：6个配对G/D、H/D、I/D、G/B、H/B、I/B，每资产/方向/原signal_close_ms匹配；RETAINED/ADDED/DISAPPEARED/CHANGED。不同配对、费用及同BTC版本不能作为独立样本相加。延迟CORE保持原信号，不从实际提交减10秒推断。
- actual_USDT_delta：完整账户余额累积下归因，含期末持仓fee/partial/MTM；各类合计严格等于最终权益差额。
- normalized_1000_delta：每笔按相同1000初始名义归一化归因，非另一条可执行账户。V2部分退出比例/step差异仍影响该值，不能称纯价格风险。
- priority_events：优先请求、撤单、主动退出、止损优先、提交及结果；time_us是UTC epoch微秒，显示中文报告为北京时间。exit_raw_sequence禁止同event再填，snapshot还保留官方raw ID用于独立影子。
- priority_summary：撤单、同向/反向提前退出、实际整笔net和最后一段现金credit、主动退出fee、CORE提交/填/过期、恢复B及仍丢失B。恢复只在B/D/变体均完成时统计。
- btc_filter_audit：每个EXTRA的同根BTC完整信号及通过状态；D是否成交与事后净盈亏只作描述，不参与过滤。G/I共享过滤条件只列一次，不双计。
- shadow_results：实际EXTRA主动退出前同状态复制，继续原V2和止损，不开CORE也不做后续入场。actual_minus_shadow>0表示相对此单影子避免损失，<0表示失去收益；不可直接加到完整账户收益。期末未平仓标OPEN_MTM。
- cash_reconciliation：closed_net＋open_fee_partial_and_MTM_contribution＝ending_equity−500。手续费也按真实数量和每次交易turnover核对。资金费未计。
- signal_execution_diagnostics.csv.gz：按同根完整CORE/EXTRA和BTC过滤结果、实际下单/持仓时序重建决策。未计算原因保留NO_ORDER_CHECK_EVENT_OR_PRIORITY_LOCK等，不把它默认为通过。原六线/ER只读全条件来自锁定的上轮conditions缓存（完整链信号本轮重新计算），不重复消费真实回踩。
- 原逐笔下载metadata保留url/bytes/SHA256/official_checksum_match；checksum证明下载一致而非独立保证市场档案完备。限价触达全量成交仍是模拟代理。

关闭事件的继承字段net_usdt沿用旧观察器口径，可能只含最后一段；完整整笔净额以trade.net及priority_position_closed.closed_net为准，费用按cash_events及stats.fees对账，不从旧事件字段相加。

CORE/EXTRA是信号当时的完整策略分类；ADDED等是两个实际账户的交易匹配分类，两者不是同一概念。ADDED也可能是基准当时被占用、而变体后来恢复的CORE，不能全部算EXTRA质量。signal_quality按前者，trade_attribution按后者。loss_amplification另区分同价格/时点仅仓位或部分比例变化、V2部分路径变化、以及入出场路径也改变。
