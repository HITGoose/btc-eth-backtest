# ETH历史密集阈值实验审查入口

源提交：0ad7902161b91e7cf5538c5c06195c4a39086c24。独立分支：codex/eth-density-025-030-035-20261114。原main及正式策略不替换。

当前建议保留0.25%。已验证部分中，新增ETH交易本身总体盈利，但挤掉原盈利单及后续仓位变化，使四个放宽对照的独立区间账户损益差额合计均为负；费用压力进一步变差。**不是完整19—26验证：2019及2025 C—F明确UNVERIFIED**。2025缺失是官方原始逐笔档案冲突，不是用差收益提前停止。

- [中文结论及七项答复](outputs/eth_density_experiment/report.md)
- [六组逐年表（含费用、缺失状态）](outputs/eth_density_experiment/comparison_six_groups.csv)
- [完整指标：资产／方向／最差月／尾部／费用](outputs/eth_density_experiment/yearly_metrics.csv)
- [新增亏损、旧盈利消失与归一化差额](outputs/eth_density_experiment/impact.csv)
- [逐笔全部匹配分类](outputs/eth_density_experiment/trade_attribution.csv)
- [同时持仓风险](outputs/eth_density_experiment/overlap_risk.csv)
- [盈利集中度](outputs/eth_density_experiment/concentration.csv)
- [检查结果及缺失边界](outputs/eth_density_experiment/audit.json)
- [实际数据问题和处置](outputs/eth_density_experiment/ISSUES.md)
- [固定规则、命令与恢复方法](outputs/eth_density_experiment/EXPERIMENT.md)
- [字段解释](outputs/eth_density_experiment/SCHEMA.md)

核心代码strategy.py隔离参数化底层候选和overlay；worker.py保持锁定逐笔引擎及出场，交替执行零费和明确假设每边0.05%的现金路径。原32测试、全链/未来截断6项、费用/断点8项、归因8项通过；2024/25四项原ER/V2基准逐笔与权益复现。执行代码SHA在frozen_config和audit中核对。

全部区间都尝试：2020仅02-16至年底，2021—2025全年，2026仅1—10月，NOV独立起算至11-13 08:00北京时间。2025 A/B恢复完成，C/D/E/F因8月29日原始逐笔3个冲突ID无法完成；日/月同市场备份相同，未删行、猜价、换平台或用OHLC代替。

各期artifacts/period_*_ledgers.zip提供结果、账户现金流水、源URL/SHA、配置及运行日志。diagnostics_*.csv.gz提供完整只读候选诊断；未验证组的断点后账户状态标NOT_EVALUATED。原始行情、equity.npy、pickle断点未提交，需按命令恢复才能重跑；不能用旧成交结果替代新订单行情路径。

费用压力不是用户实际费率，资金费未计，不称真实净收益；触价全额成交仍为逐笔价格上的模拟代理，非实盘成交保证。各年度已反复查看，不称样本外，没有逐年选组或搜索其他参数。
