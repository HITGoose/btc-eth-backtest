# ETH BTC确认与CORE优先：最终审查入口

**正式策略保留0.25%，不合并main。** G/I在已验证区间增加收益，但伴随总亏损、回撤和最差月代价；H在假设费用后低于B。I保存为独立研究结果，不把它当已证实的目标机器人原规则。

源提交：01937b2d4a1306ab211a9c1853bda285258c2853。独立分支：codex/eth-core-priority-btc-confirm-20261114。冻结财务代码提交：2292b8a2cfc7d802c639014cba1b8ae7d1ef917c。

B=.25 V2；D=.30 V2；G=仅EXTRA需同根BTC完整信号同向；H=CORE优先；I=两者。BTC始终.25 V2，原ER BASELINE。没有搜索更多阈值或逐年选组。

7个完整可验证独立区间，两费率、五组均完成；2025 B完成，D/G/H/I两费率各自实际尝试后均因官方8月29日冲突ID停止，UNVERIFIED。2019及NOV截止后的区间未验证。

相对B，各独立区间账户损益差额合计：G零费+197.07U／假设费+131.45U；H+160.43U／−81.02U；I+401.41U／+269.07U。**不是跨年复利收益，未计资金费，每边.05%是假设，未核实用户实际费率。**

- [中文结论与五组年度收益/回撤](outputs/eth_core_priority/CONCLUSION.md)
- [完整中文报告](outputs/eth_core_priority/report.md)
- [五组完整年度表](outputs/eth_core_priority/comparison_five_groups.csv)
- [分资产/方向指标](outputs/eth_core_priority/yearly_metrics.csv)
- [完整交易匹配归因](outputs/eth_core_priority/trade_attribution.csv)
- [实际优先替换事件](outputs/eth_core_priority/priority_events.csv)
- [CORE恢复及主动退出代价](outputs/eth_core_priority/priority_summary.csv)
- [BTC过滤逐候选审计](outputs/eth_core_priority/btc_filter_audit.csv)
- [信号来源CORE/EXTRA质量](outputs/eth_core_priority/signal_quality.csv)
- [独立逐笔影子诊断](outputs/eth_core_priority/shadow_summary.md)
- [原亏损扩大：仓位/部分比例与价格路径分开](outputs/eth_core_priority/loss_amplification.csv)
- [现金与期末权益对账](outputs/eth_core_priority/cash_reconciliation.csv)
- [检查结果](outputs/eth_core_priority/audit.json)
- [固定规则、执行排序及复跑命令](outputs/eth_core_priority/EXPERIMENT.md)
- [实际问题及恢复](outputs/eth_core_priority/ISSUES.md)
- [数据覆盖及校验](outputs/eth_core_priority/data_check.md)
- [字段解释](outputs/eth_core_priority/SCHEMA.md)
- [小报告包](outputs/eth_core_priority/artifacts/REPORTS_SMALL.zip)
- [全部派生交付包](outputs/eth_core_priority/artifacts/ALL_DERIVED_RESULTS.zip)

107项金融/入场/归因/影子/边界/断点检查及46项存档引用检查通过；648条指标、10994条配对归因记录、72个组合情景144次资产账本核对、84次独立影子延续。配对记录、费用情景、复用BTC不是额外独立样本。

各年度账本、官方源URL/SHA、失败日志、配置和不完整前缀在artifacts/period_*_ledgers.zip。原始行情、equity.npy及自有pickle断点保留云端，不提交Git；不要把交付证据ZIP的status当可跳过的运行缓存。当前云端已全数组比较，新克隆缺旧NPY时replay.py从锁定存档JSON核对交易和期末权益，并明确注明缺少逐分钟参考，不冒充数组回归。所有新增订单仍读取官方原始逐笔。
