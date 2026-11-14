# Astra审查入口：原ER + 自适应减仓V2

用户已授权同步。当前修正版在 **codex/adaptive-v2-astra-20261114** 分支，原main保留；原策略work文件未改。目标是复刻参考机器人，不做自动参数寻优。

1. [当前策略完整文档](handoff/astra_20261114/STRATEGY_CURRENT.md)：真实运行的入场、ER、2%绝对距离、执行、V2减仓及未验证规则。
2. [先读交接说明](handoff/astra_20261114/README_FIRST.md)：版本、数据口径、环境与限制。Git状态见同目录git_status.json，同步前检查保留git_status_before_sync.json。
3. 修正版主代码：[V2 worker](outputs/adaptive_risk_exit_v2/worker.py)、[原始逐笔执行引擎](outputs/binance_perpetual_raw_execution/engine.py)。跨outputs的Python依赖一并跟踪，不能只复制worker。
4. 结果：[2024/25](outputs/adaptive_risk_exit_v2/report.md)、[其他年份](outputs/adaptive_risk_exit_v2_extended/report.md)、[11月](outputs/nov9_today_simultaneous/report.md)。2019未验证，2020/2026区间限制详见报告。资金费未计。
5. 独开信号：[统计](outputs/cross_asset_entry_audit/summary.csv)、[全量价格明细分片](outputs/cross_asset_entry_audit/review_shards/trades)、[逐项条件分片](outputs/cross_asset_entry_audit/review_shards/conditions)、[分片行数与SHA索引](outputs/cross_asset_entry_audit/review_shards/index.json)。原ER与V2各931案例，分片保留全部1862行，不是新增交易样本。完整CSV/HTML/Excel可由原云端交接包取得或获取输入后生成。
6. 测试：[32项合成结果](outputs/adaptive_risk_exit_v2/test_results.json)、[2024/25审计](outputs/adaptive_risk_exit_v2/audit.json)、[扩展审计](outputs/adaptive_risk_exit_v2_extended/audit.json)、[独开审计](outputs/cross_asset_entry_audit/audit.json)。原85文件恢复SHA见outputs/retry_nov9_nov12/source_restore.json。

## 运行范围

Python3.12，根目录requirements.txt保持原样，Excel导出另外需要openpyxl。本分支没有上传原始行情、equity.npy、ZIP或大体积网页，不能直接运行依赖这些输入的collector并把缺文件当收益0。源码目前ROOT写死/workspace/btc-eth-backtest，存在跨模块导入和inspect源码补丁；恢复目录及输入后才重跑。先复现32项合成测试、保留原交易/权益回归，再做便携性整理。

V2：原ER入场不变；两根闭合15m均六线失去同向且MACD不支持时，按已实现余额3%的参考回吐预算计算减仓，每笔最多一次且≤初始25%；余仓保留原阶梯止损。不是保证账户损失≤3%。2%支撑阻力绝对距离不得更改。

优先检查：+10秒提交边界、回踩信号消费时序、整点水平确认边界、限价全量触达代理、K线与逐笔冲突和数据缺口。对目标机器人的匹配仍未完成；禁止将收益优化当作复刻证明。
